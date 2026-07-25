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
      <p className="timestamp">Cycles: {status?.cycles ?? 0} · Measured comfort: {status?.comfort_pct ?? "--"}% · Agent confidence: {status ? Math.round(status.decision_confidence * 100) : "--"}%</p>
      <p className={status?.fallback_activated ? "healing-alert" : "message"}>{status?.last_action ?? "Waiting for first EnergyPlus cycle"}</p>
      <p className="timestamp">Strategic layer: {status?.strategic_update ?? "Waiting for an active goal"}</p>
      <div className="agent-list">
        {(status?.agent_recommendations ?? []).map((agent) => (
          <p className="timestamp" key={agent.agent}>
            <strong>{agent.agent}</strong>: {agent.policy.replaceAll("_", " ")} ({Math.round(agent.score * 100)}%)
          </p>
        ))}
      </div>
    </section>
  );
}
