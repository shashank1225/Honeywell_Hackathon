import { useEffect, useState } from "react";

export default function AutonomyPanel() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    async function refresh() {
      const response = await fetch("/autonomy/status");
      if (response.ok) setStatus(await response.json());
    }
    refresh();
    const interval = setInterval(refresh, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="panel">
      <div className="panel-header"><h2>Autonomous Closed Loop</h2><span className="connection connected">active</span></div>
      <p className="metric-value">{status?.active_policy?.replaceAll("_", " ") ?? "waiting"}</p>
      <p className="timestamp">Cycles: {status?.cycles ?? 0} · Measured comfort: {status?.comfort_pct ?? "--"}%</p>
      <p className={status?.fallback_activated ? "healing-alert" : "message"}>{status?.last_action ?? "Waiting for first EnergyPlus cycle"}</p>
    </section>
  );
}
