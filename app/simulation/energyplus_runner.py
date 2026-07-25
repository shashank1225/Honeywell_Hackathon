"""EnergyPlus simulation wrapper.

This runner launches a real EnergyPlus executable against a standard `.idf`
model and weather file, then reads the generated EnergyPlus output files back
into the shared telemetry state and Kafka stream.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.kafka.client import publish_telemetry_event
from app.schemas.telemetry import BuildingTelemetry, Setpoints
from app.simulation.idf_writer import RuntimeIDFWriter
from app.services.energy_efficiency import energy_efficiency_tracker
from app.services.telemetry_aggregation import telemetry_window_aggregator
from app.simulation.state import BuildingState, building_state

logger = logging.getLogger(__name__)


class EnergyPlusNotConfiguredError(RuntimeError):
    """Raised when EnergyPlus cannot be started with a real executable and inputs."""


@dataclass(slots=True)
class TelemetryFrame:
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    occupancy_pct: float
    power_kw: float

    def to_model(self, zone: str) -> BuildingTelemetry:
        return BuildingTelemetry(
            timestamp=self.timestamp,
            zone=zone,
            temperature_c=round(self.temperature_c, 2),
            humidity_pct=round(self.humidity_pct, 2),
            occupancy_pct=round(self.occupancy_pct, 2),
            power_kw=round(self.power_kw, 2),
        )


class EnergyPlusSubprocessBackend:
    """Launch EnergyPlus as a subprocess and load telemetry from its outputs."""

    def __init__(self, zone: str) -> None:
        settings = get_settings()
        self._zone = settings.energyplus_zone_name or zone
        self._executable = self._resolve_executable(settings.energyplus_executable)
        self._idf_path = settings.energyplus_idf_path or settings.energyplus_baseline_idf_path
        self._idf_writer = RuntimeIDFWriter(self._idf_path, settings.energyplus_generated_idf_path)
        self._runtime_idf_path = settings.energyplus_generated_idf_path
        self._weather_path = settings.energyplus_weather_path
        self._output_dir = settings.energyplus_output_dir
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._frames_ready = threading.Event()
        self._frames_lock = threading.Lock()
        self._frames: list[TelemetryFrame] = []
        self._frame_index = 0
        self._latest_frame: TelemetryFrame | None = None

    @staticmethod
    def _resolve_executable(configured_path: str | None) -> str:
        if configured_path:
            executable = Path(configured_path)
            if executable.exists():
                return str(executable)
            resolved = shutil.which(configured_path)
            if resolved:
                return resolved
            raise EnergyPlusNotConfiguredError(f"EnergyPlus executable not found: {configured_path}")

        resolved = shutil.which("energyplus")
        if resolved is None:
            raise EnergyPlusNotConfiguredError(
                "Set ENERGYPLUS_EXECUTABLE to a real EnergyPlus binary or install it on PATH."
            )
        return resolved

    def _validate_configuration(self) -> None:
        if self._idf_path is None:
            raise EnergyPlusNotConfiguredError("ENERGYPLUS_IDF_PATH must point to a real .idf model file.")
        if self._weather_path is None:
            raise EnergyPlusNotConfiguredError("ENERGYPLUS_WEATHER_PATH must point to a real .epw weather file.")
        if not self._idf_path.exists():
            raise FileNotFoundError(f"EnergyPlus IDF file not found: {self._idf_path}")
        if not self._weather_path.exists():
            raise FileNotFoundError(f"EnergyPlus weather file not found: {self._weather_path}")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _command(self) -> list[str]:
        return [
            self._executable,
            "-w",
            str(self._weather_path.resolve()),
            "-d",
            str(self._output_dir.resolve()),
            # The subprocess runs with the output directory as its cwd, so
            # relative repository paths would otherwise point inside that
            # directory and EnergyPlus would not find the generated model.
            str(self._runtime_idf_path.resolve()),
        ]

    def _drain_stream(self, stream, level: int) -> None:
        if stream is None:
            return
        for line in stream:
            line = line.rstrip()
            if line:
                logger.log(level, "EnergyPlus: %s", line)

    def _run_subprocess(self) -> None:
        command = self._command()
        logger.info("Starting EnergyPlus simulation: %s", " ".join(command))
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self._output_dir.resolve(),
        )
        stdout_thread = threading.Thread(target=self._drain_stream, args=(self._process.stdout, logging.INFO), daemon=True)
        stderr_thread = threading.Thread(target=self._drain_stream, args=(self._process.stderr, logging.WARNING), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        return_code = self._process.wait()
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        if return_code != 0:
            raise RuntimeError(f"EnergyPlus exited with code {return_code}")
        self._load_frames()

    def _load_frames(self) -> None:
        sql_path = self._output_dir / "eplusout.sql"
        csv_path = self._output_dir / "eplusout.csv"
        eso_path = self._output_dir / "eplusout.eso"
        meter_path = self._output_dir / "eplusout.mtr"

        frames = []
        if eso_path.exists():
            frames = list(self._load_frames_from_eso(eso_path, meter_path))
        elif sql_path.exists():
            frames = list(self._load_frames_from_sql(sql_path))
        elif csv_path.exists():
            frames = list(self._load_frames_from_csv(csv_path))

        if not frames:
            raise RuntimeError(
                "EnergyPlus completed but no telemetry output was found. Ensure the IDF requests "
                "the standard zone temperature, humidity, occupancy, and HVAC electricity outputs."
            )

        with self._frames_lock:
            self._frames = frames
            self._frame_index = 0
            self._latest_frame = frames[-1]
        self._frames_ready.set()

    def _load_frames_from_eso(self, eso_path: Path, meter_path: Path | None = None) -> Iterator[TelemetryFrame]:
        if not eso_path.exists():
            return

        with eso_path.open(encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]

        variable_lookup = self._parse_eso_dictionary(lines)
        meter_lookup = self._parse_mtr_dictionary(meter_path, lines) if meter_path is not None and meter_path.exists() else {}
        records = self._parse_eso_data_records(lines)
        meter_records = self._parse_meter_data_records(meter_path) if meter_path is not None and meter_path.exists() else []

        for index, (timestamp, values) in enumerate(records):
            temperature = self._value_for_candidates(values, variable_lookup, ["zone mean air temperature"])
            humidity = self._value_for_candidates(values, variable_lookup, ["zone air relative humidity", "zone mean air humidity ratio"])
            occupancy = self._value_for_candidates(values, variable_lookup, ["zone people occupant count", "people occupant count"])
            power = None
            if index < len(meter_records):
                meter_values = meter_records[index][1]
                power = self._value_for_candidates(meter_values, meter_lookup, ["energytransfer:facility", "exteriorlights:electricity", "electricity:facility", "energytransfer:building"])

            if temperature is None:
                continue

            if humidity is None:
                humidity = 50.0
            if occupancy is None:
                occupancy = 25.0
            if power is None:
                power = 0.0

            yield TelemetryFrame(
                timestamp=timestamp,
                temperature_c=float(temperature),
                humidity_pct=float(humidity),
                occupancy_pct=float(occupancy),
                power_kw=float(power) / 3_600_000.0,
            )

    def _parse_eso_dictionary(self, lines: list[str]) -> dict[str, float]:
        lookup: dict[str, float] = {}
        for line in lines:
            if line == "End of Data Dictionary":
                break
            if line.startswith("Program Version"):
                continue
            parts = line.split(",", 3)
            if len(parts) < 2:
                continue
            try:
                index = int(parts[0].strip())
            except ValueError:
                continue
            name = parts[-1].split(" !", 1)[0].strip()
            lookup[name.lower()] = float(index)
        return lookup

    def _parse_mtr_dictionary(self, meter_path: Path | None, lines: list[str]) -> dict[str, float]:
        if meter_path is None or not meter_path.exists():
            return {}
        lookup: dict[str, float] = {}
        with meter_path.open(encoding="utf-8") as handle:
            meter_lines = [line.strip() for line in handle if line.strip()]
        for line in meter_lines:
            if line == "End of Data Dictionary":
                break
            if line.startswith("Program Version"):
                continue
            parts = line.split(",", 3)
            if len(parts) < 2:
                continue
            try:
                index = int(parts[0].strip())
            except ValueError:
                continue
            name = parts[-1].split(" !", 1)[0].strip()
            lookup[name.lower()] = float(index)
        return lookup

    def _parse_eso_data_records(self, lines: list[str]) -> list[tuple[datetime, dict[float, float]]]:
        records: list[tuple[datetime, dict[float, float]]] = []
        in_data = False
        current_timestamp: datetime | None = None
        current_values: dict[float, float] = {}

        for line in lines:
            if line == "End of Data Dictionary":
                in_data = True
                continue
            if not in_data:
                continue
            if line.startswith("2,"):
                if current_timestamp is not None:
                    records.append((current_timestamp, current_values))
                current_timestamp = self._timestamp_from_eso_header(line)
                current_values = {}
                continue
            if current_timestamp is None:
                continue
            try:
                index_text, value_text = line.split(",", 1)
                index = float(index_text.strip())
                value = float(value_text.strip())
            except ValueError:
                continue
            current_values[index] = value

        if current_timestamp is not None:
            records.append((current_timestamp, current_values))
        return records

    def _parse_meter_data_records(self, meter_path: Path | None) -> list[tuple[datetime, dict[float, float]]]:
        if meter_path is None or not meter_path.exists():
            return []
        with meter_path.open(encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        records: list[tuple[datetime, dict[float, float]]] = []
        in_data = False
        current_timestamp: datetime | None = None
        current_values: dict[float, float] = {}

        for line in lines:
            if line == "End of Data Dictionary":
                in_data = True
                continue
            if not in_data:
                continue
            if line.startswith("2,"):
                if current_timestamp is not None:
                    records.append((current_timestamp, current_values))
                current_timestamp = self._timestamp_from_eso_header(line)
                current_values = {}
                continue
            if current_timestamp is None:
                continue
            try:
                index_text, value_text = line.split(",", 1)
                index = float(index_text.strip())
                value = float(value_text.strip())
            except ValueError:
                continue
            current_values[index] = value

        if current_timestamp is not None:
            records.append((current_timestamp, current_values))
        return records

    def _timestamp_from_eso_header(self, header: str) -> datetime:
        parts = [part.strip() for part in header.split(",")]
        if len(parts) < 6:
            return datetime.now(UTC)
        try:
            month = int(parts[2])
            day = int(parts[3])
            hour = int(parts[5])
        except ValueError:
            return datetime.now(UTC)
        now = datetime.now(UTC)
        return now.replace(month=month, day=day, hour=max(0, hour - 1), minute=0, second=0, microsecond=0)

    def _value_for_candidates(self, values: dict[float, float], lookup: dict[str, float], candidates: list[str]) -> float | None:
        if not lookup:
            return None
        for candidate in candidates:
            normalized_candidate = candidate.lower()
            for key, index in lookup.items():
                if normalized_candidate in key:
                    if index in values:
                        return values[index]
            for key, index in lookup.items():
                if normalized_candidate == key:
                    if index in values:
                        return values[index]
        return None

    def _load_frames_from_sql(self, sql_path: Path) -> Iterator[TelemetryFrame]:
        with sqlite3.connect(f"file:{sql_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            if not self._table_exists(conn, "ReportVariableData") or not self._table_exists(conn, "ReportMeterData"):
                return

            temperature_series = self._series_from_sql(
                conn,
                "ReportVariableData",
                "ReportVariableDataDictionary",
                "ReportVariableDataDictionaryIndex",
                "VariableValue",
                "Zone Mean Air Temperature",
                key_value=self._zone,
            )
            humidity_series = self._series_from_sql(
                conn,
                "ReportVariableData",
                "ReportVariableDataDictionary",
                "ReportVariableDataDictionaryIndex",
                "VariableValue",
                "Zone Air Relative Humidity",
                key_value=self._zone,
            )
            occupancy_series = self._series_from_sql(
                conn,
                "ReportVariableData",
                "ReportVariableDataDictionary",
                "ReportVariableDataDictionaryIndex",
                "VariableValue",
                "Zone People Occupant Count",
                key_value=self._zone,
            )
            power_series = self._series_from_sql(
                conn,
                "ReportMeterData",
                "ReportMeterDataDictionary",
                "ReportMeterDataDictionaryIndex",
                "MeterValue",
                "Electricity:HVAC",
                fallback_names=("Electricity:Facility",),
            )

            for time_index in sorted(set().union(temperature_series, humidity_series, occupancy_series, power_series)):
                temperature = temperature_series.get(time_index)
                humidity = humidity_series.get(time_index)
                occupancy = occupancy_series.get(time_index)
                power = power_series.get(time_index)
                if None in (temperature, humidity, occupancy, power):
                    continue
                yield TelemetryFrame(
                    timestamp=self._timestamp_from_sql(conn, time_index),
                    temperature_c=temperature,
                    humidity_pct=humidity,
                    occupancy_pct=occupancy,
                    power_kw=power / 1000.0,
                )

    def _load_frames_from_csv(self, csv_path: Path) -> Iterator[TelemetryFrame]:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        if not rows:
            return

        current_time = datetime.now(UTC)
        for index, row in enumerate(rows):
            temperature = self._float_from_row(row, [
                f"{self._zone}:Zone Mean Air Temperature [C](TimeStep)",
                "Zone Mean Air Temperature [C](TimeStep)",
            ])
            humidity = self._float_from_row(row, [
                f"{self._zone}:Zone Air Relative Humidity [%](TimeStep)",
                "Zone Air Relative Humidity [%](TimeStep)",
            ])
            occupancy = self._float_from_row(row, [
                f"{self._zone}:Zone People Occupant Count [](TimeStep)",
                "Zone People Occupant Count [](TimeStep)",
            ])
            power = self._float_from_row(row, [
                "Electricity:HVAC [J](TimeStep)",
                "Electricity:Facility [J](TimeStep)",
            ])
            if None in (temperature, humidity, occupancy, power):
                continue
            yield TelemetryFrame(
                timestamp=current_time + timedelta(seconds=index),
                temperature_c=temperature,
                humidity_pct=humidity,
                occupancy_pct=occupancy,
                power_kw=power / 1000.0,
            )

    def _series_from_sql(
        self,
        conn: sqlite3.Connection,
        data_table: str,
        dictionary_table: str,
        dictionary_index_column: str,
        value_column: str,
        target_name: str,
        fallback_names: tuple[str, ...] = (),
        key_value: str | None = None,
    ) -> dict[int, float]:
        names = (target_name, *fallback_names)
        for name in names:
            try:
                rows = conn.execute(
                    f"""
                    SELECT d.TimeIndex, d.{value_column}
                    FROM {data_table} AS d
                    JOIN {dictionary_table} AS dict
                      ON d.{dictionary_index_column} = dict.{dictionary_index_column}
                    WHERE dict.Name = ?
                      AND (? IS NULL OR dict.KeyValue = ?)
                    ORDER BY d.TimeIndex ASC
                    """,
                    (name, key_value, key_value),
                ).fetchall()
            except sqlite3.Error:
                rows = []
            if rows:
                return {int(row[0]): float(row[1]) for row in rows}
        return {}

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _float_from_row(row: dict[str, str], candidates: list[str]) -> float | None:
        for candidate in candidates:
            value = row.get(candidate)
            if value not in (None, "", "--"):
                try:
                    return float(value)
                except ValueError:
                    continue
        return None

    def _timestamp_from_sql(self, conn: sqlite3.Connection, time_index: int) -> datetime:
        try:
            row = conn.execute(
                "SELECT Month, Day, Hour, Minute FROM Time WHERE TimeIndex = ?",
                (time_index,),
            ).fetchone()
            if row is not None:
                year = datetime.now(UTC).year
                hour = max(0, int(row[2]) - 1)
                minute = int(row[3]) if row[3] is not None else 0
                return datetime(year, int(row[0]), int(row[1]), hour, minute, tzinfo=UTC)
        except sqlite3.Error:
            pass
        return datetime.now(UTC) + timedelta(seconds=time_index)

    def start(self) -> None:
        self._validate_configuration()
        self.publish_setpoints(Setpoints())

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=10)
            self._reader_thread = None

    def publish_setpoints(self, setpoints: Setpoints) -> None:
        self._runtime_idf_path = self._idf_writer.write(setpoints)

    def run_cycle(self, setpoints: Setpoints) -> BuildingTelemetry:
        """Run a fresh EnergyPlus cycle against the latest approved IDF."""
        self._validate_configuration()
        self.publish_setpoints(setpoints)
        self._frames_ready.clear()
        self._frames = []
        self._frame_index = 0
        self._latest_frame = None
        self._run_subprocess()
        telemetry = self.latest_telemetry()
        if telemetry is None:
            raise RuntimeError("EnergyPlus cycle completed without telemetry")
        return telemetry

    def wait_for_telemetry(self, timeout_seconds: float | None = None) -> BuildingTelemetry | None:
        if not self._frames_ready.wait(timeout_seconds):
            return None
        return self.latest_telemetry()

    def latest_telemetry(self) -> BuildingTelemetry | None:
        with self._frames_lock:
            if not self._frames:
                return None
            index = min(self._frame_index, len(self._frames) - 1)
            self._latest_frame = self._frames[index]
            if self._frame_index < len(self._frames) - 1:
                self._frame_index += 1
            return self._latest_frame.to_model(self._zone)


class EnergyPlusRunner:
    """EnergyPlus runner that publishes real simulation telemetry on a fixed interval."""

    def __init__(
        self,
        state: BuildingState | None = None,
        interval_seconds: float | None = None,
        zone: str = "main",
        backend: EnergyPlusSubprocessBackend | None = None,
    ) -> None:
        settings = get_settings()
        self._state = state or building_state
        self._interval_seconds = interval_seconds or settings.simulation_interval_seconds
        self._zone = zone
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._backend = backend or EnergyPlusSubprocessBackend(zone=zone)
        self._telemetry_handler = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def tick_once(self) -> BuildingTelemetry:
        """Fetch one telemetry sample from EnergyPlus and publish it to shared state and Kafka."""
        setpoints = self._state.get_setpoints()
        run_cycle = getattr(self._backend, "run_cycle", None)
        if callable(run_cycle):
            telemetry = run_cycle(setpoints)
        else:
            self._backend.publish_setpoints(setpoints)
            telemetry = self._backend.wait_for_telemetry(timeout_seconds=self._interval_seconds)
            if telemetry is None:
                telemetry = self._backend.latest_telemetry()
        if telemetry is None:
            raise RuntimeError(
                "EnergyPlus telemetry is unavailable. Configure ENERGYPLUS_EXECUTABLE, "
                "ENERGYPLUS_IDF_PATH, and ENERGYPLUS_WEATHER_PATH so the real simulation can run."
            )
        if not self._publish_to_kafka(telemetry):
            # Degraded-mode delivery preserves live controls if Kafka is down.
            self._state.publish_telemetry(telemetry)
            energy_efficiency_tracker.record(telemetry, self._interval_seconds)
            telemetry_window_aggregator.add(telemetry)
        if self._telemetry_handler is not None:
            self._telemetry_handler(telemetry)
        return telemetry

    def set_telemetry_handler(self, handler) -> None:
        """Attach an autonomous supervisory callback; never an actuator callback."""
        self._telemetry_handler = handler

    def _publish_to_kafka(self, telemetry: BuildingTelemetry) -> bool:
        payload = json.dumps(telemetry.model_dump(mode="json"))
        return publish_telemetry_event(payload)

    async def run_loop(self) -> None:
        """Background loop used by FastAPI lifespan startup.

        A failed EnergyPlus subprocess must not take down the autonomous
        service.  The next cycle retries with the current last-known-safe
        setpoints, which also lets the service recover if another local
        process briefly held the output directory.
        """
        self._running = True
        logger.info(
            "EnergyPlus simulation started (interval=%ss, zone=%s)",
            self._interval_seconds,
            self._zone,
        )
        try:
            while self._running:
                try:
                    await asyncio.to_thread(self.tick_once)
                    self._last_error = None
                except Exception as exc:
                    self._last_error = str(exc)
                    logger.exception(
                        "EnergyPlus simulation cycle failed; retrying in %ss: %s",
                        self._interval_seconds,
                        exc,
                    )
                await asyncio.sleep(self._interval_seconds)
        finally:
            logger.info("EnergyPlus simulation stopped")

    async def start(self) -> None:
        if self._running:
            return
        self._backend.start()
        self._task = asyncio.create_task(self.run_loop())

    async def stop(self) -> None:
        self._running = False
        self._backend.stop()
        if self._task is not None:
            await self._task
            self._task = None


_runner: EnergyPlusRunner | None = None


def get_energyplus_runner() -> EnergyPlusRunner:
    global _runner
    if _runner is None:
        _runner = EnergyPlusRunner()
    return _runner
