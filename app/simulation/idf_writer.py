"""Generate a runtime EnergyPlus model with AABOS-approved setpoints."""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.telemetry import Setpoints


class RuntimeIDFWriter:
    """Copies a baseline IDF and updates its thermostat schedules deterministically."""

    def __init__(self, baseline_path: Path, generated_path: Path) -> None:
        self._baseline_path = baseline_path
        self._generated_path = generated_path

    @property
    def generated_path(self) -> Path:
        return self._generated_path

    def write(self, setpoints: Setpoints) -> Path:
        source = self._baseline_path.read_text(encoding="utf-8")
        heating_setpoint = max(16.0, setpoints.hvac_temperature_c - 2.0)
        modified = self._replace_schedule(source, "CLGSETP_SCH", setpoints.hvac_temperature_c)
        modified = self._replace_schedule(modified, "HTGSETP_SCH", heating_setpoint)
        modified = self._scale_schedule(modified, "BLDG_LIGHT_SCH", setpoints.lighting_level_pct / 100.0)
        header = (
            "! AABOS runtime-generated model; do not edit manually.\n"
            f"! HVAC target: {setpoints.hvac_temperature_c:.1f} C; "
            f"ventilation target: {setpoints.ventilation_rate_pct:.1f}%; "
            f"lighting target: {setpoints.lighting_level_pct:.1f}%.\n"
        )
        self._generated_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._generated_path.with_suffix(".idf.tmp")
        temporary_path.write_text(header + modified, encoding="utf-8")
        temporary_path.replace(self._generated_path)
        return self._generated_path

    @staticmethod
    def _replace_schedule(content: str, schedule_name: str, value: float) -> str:
        pattern = re.compile(
            rf"(Schedule:Compact\s*,\s*{re.escape(schedule_name)}\s*,.*?;)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(content)
        if match is None:
            raise ValueError(f"Thermostat schedule {schedule_name} was not found in the baseline IDF")

        block = re.sub(
            r"(Until:\s*[^,;]+,\s*)[-+]?\d+(?:\.\d+)?",
            rf"\g<1>{value:.1f}",
            match.group(1),
            flags=re.IGNORECASE,
        )
        return content[: match.start()] + block + content[match.end() :]

    @staticmethod
    def _scale_schedule(content: str, schedule_name: str, factor: float) -> str:
        pattern = re.compile(
            rf"(Schedule:Compact\s*,\s*{re.escape(schedule_name)}\s*,.*?;)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(content)
        if match is None:
            return content

        def scale_value(value_match: re.Match[str]) -> str:
            value = float(value_match.group(2))
            return f"{value_match.group(1)}{min(1.0, max(0.0, value * factor)):.3f}"

        block = re.sub(
            r"(Until:\s*[^,;]+,\s*)([-+]?\d+(?:\.\d+)?)",
            scale_value,
            match.group(1),
            flags=re.IGNORECASE,
        )
        return content[: match.start()] + block + content[match.end() :]
