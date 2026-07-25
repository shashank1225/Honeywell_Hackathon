import { useEffect, useState } from "react";

export default function EnergySavingsPanel() {
  const [report, setReport] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const response = await fetch("/energy/savings");
    if (response.ok) setReport(await response.json());
  }

  async function captureBaseline() {
    const response = await fetch("/energy/baseline", { method: "POST" });
    if (!response.ok) {
      setError("Telemetry is still loading, so a baseline cannot be captured yet.");
      return;
    }
    const captured = await response.json();
    setReport(captured);
    setError("");
    setMessage(`Baseline captured at ${captured.baseline_power_kw.toFixed(2)} kW. Live savings will update on the next telemetry cycles.`);
  }

  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id); }, []);
  return (
    <section className="panel">
      <div className="panel-header"><h2>Measured Energy Savings</h2><span className="connection connected">baseline</span></div>
      <p className="metric-value">{report ? `${report.energy_savings_pct}%` : "--"}</p>
      <p className="timestamp">Baseline {report?.baseline_energy_kwh ?? 0} kWh · Actual {report?.actual_energy_kwh ?? 0} kWh</p>
      <button onClick={captureBaseline}>Capture current baseline</button>
      {message && <p className="message">{message}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
