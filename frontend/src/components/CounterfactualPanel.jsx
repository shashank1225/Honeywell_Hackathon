import { useEffect, useState } from "react";

export default function CounterfactualPanel() {
  const [evaluation, setEvaluation] = useState(null);

  useEffect(() => {
    async function refresh() {
      const response = await fetch("/counterfactuals/current");
      if (response.ok) setEvaluation(await response.json());
    }
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="panel">
      <div className="panel-header"><h2>Counterfactual Evidence</h2><span className="connection connected">advisory</span></div>
      {!evaluation && <p className="timestamp">Waiting for telemetry…</p>}
      {evaluation && (
        <>
          <p className="message">Selected: <strong>{evaluation.selected_policy.replaceAll("_", " ")}</strong> · {evaluation.selected_outcome.projected_power_kw} kW projected · {evaluation.selected_outcome.projected_comfort_pct}% projected comfort</p>
          <div className="agent-list">
            {evaluation.alternatives.map((outcome) => (
              <p className="timestamp" key={outcome.policy}>
                <strong>{outcome.policy.replaceAll("_", " ")}</strong>: {outcome.projected_power_kw} kW · {outcome.projected_comfort_pct}% comfort
                <br />
                {outcome.energy_delta_pct > 0 ? "+" : ""}{outcome.energy_delta_pct}% energy · {outcome.comfort_delta_pct > 0 ? "+" : ""}{outcome.comfort_delta_pct}% comfort
              </p>
            ))}
          </div>
          <p className="timestamp">{evaluation.rationale}</p>
        </>
      )}
    </section>
  );
}
