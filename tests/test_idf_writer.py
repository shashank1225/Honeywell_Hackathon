from app.schemas.telemetry import Setpoints
from app.simulation.idf_writer import RuntimeIDFWriter


BASELINE = """Schedule:Compact,
  CLGSETP_SCH,
  Temperature,
  Through: 12/31,
  For: AllDays,
  Until: 24:00,24.0;
Schedule:Compact,
  HTGSETP_SCH,
  Temperature,
  Through: 12/31,
  For: AllDays,
  Until: 24:00,21.0;
"""


def test_runtime_writer_generates_modified_idf_with_setpoints(tmp_path):
    baseline = tmp_path / "baseline.idf"
    generated = tmp_path / "generated" / "modified.idf"
    baseline.write_text(BASELINE, encoding="utf-8")

    result = RuntimeIDFWriter(baseline, generated).write(Setpoints(hvac_temperature_c=23, ventilation_rate_pct=60))

    content = result.read_text(encoding="utf-8")
    assert result == generated
    assert "AABOS runtime-generated model" in content
    assert "Until: 24:00,23.0" in content
    assert "Until: 24:00,21.0" in content
    assert "ventilation target: 60.0%" in content
