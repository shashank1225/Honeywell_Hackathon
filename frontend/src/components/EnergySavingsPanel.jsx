import { useEffect, useState } from "react";

export default function EnergySavingsPanel() {
  const [report, setReport] = useState(null);

  async function refresh() {
    const response = await fetch("/energy/savings");
    if (response.ok) setReport(await response.json());
  }

  async function captureBaseline() {
    const response = await fetch("/energy/baseline", { method: "POST" });
    if (response.ok) setReport(await response.json());
  }

  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id); }, []);
  return (
    <section className="panel">
      <div className="panel-header"><h2>Measured Energy Savings</h2><span className="connection connected">baseline</span></div>
      <p className="metric-value">{report ? `${report.energy_savings_pct}%` : "--"}</p>
      <p className="timestamp">Baseline {report?.baseline_energy_kwh ?? 0} kWh · Actual {report?.actual_energy_kwh ?? 0} kWh</p>
      <button onClick={captureBaseline}>Capture balanced baseline</button>
    </section>
  );
}
