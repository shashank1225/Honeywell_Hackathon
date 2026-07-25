import { useState } from "react";

export default function StrategyPanel() {
  const [objective, setObjective] = useState("energy_reduction");
  const [target, setTarget] = useState(10);
  const [plan, setPlan] = useState(null);
  const [llmUsed, setLlmUsed] = useState(false);
  const [error, setError] = useState("");

  async function createPlan(event) {
    event.preventDefault();
    setError("");
    const response = await fetch("/strategy/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, target_percent: Number(target) }),
    });
    if (!response.ok) {
      setError("Telemetry is still loading. Please try again in a few seconds.");
      return;
    }
    let job = await response.json();
    for (let attempt = 0; attempt < 70; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const jobResponse = await fetch(`/strategy/jobs/${job.id}`);
      job = await jobResponse.json();
      if (job.status === "completed") {
        setPlan(job.plan);
        setLlmUsed(job.llm_used);
        return;
      }
      if (job.status === "failed") break;
    }
    setError("Strategic LLM job did not complete. Check that Ollama is running.");
  }

  return (
    <section className="panel strategy-panel">
      <div className="panel-header"><h2>Strategic Planning</h2><span className="connection connected">slow loop</span></div>
      <form onSubmit={createPlan} className="strategy-form">
        <label htmlFor="goal">Goal</label>
        <select id="goal" value={objective} onChange={(event) => setObjective(event.target.value)}>
          <option value="energy_reduction">Reduce energy</option>
          <option value="comfort">Prioritize comfort</option>
          <option value="carbon_reduction">Reduce carbon</option>
        </select>
        <label htmlFor="target">Target (%)</label>
        <input id="target" type="number" min="1" max="50" value={target} onChange={(event) => setTarget(event.target.value)} />
        <button type="submit">Generate plan</button>
      </form>
      {error && <p className="error">{error}</p>}
      {plan && (
        <div className="strategy-result">
          <p><strong>{plan.selected_policy.replaceAll("_", " ")}</strong> · {Math.round(plan.confidence * 100)}% confidence</p>
          <p className="message">{llmUsed ? "Local Llama 3.2 generated this policy." : "Deterministic safety fallback generated this policy."}</p>
          <p>Proposed: {plan.proposed_setpoints.hvac_temperature_c} °C · {plan.proposed_setpoints.ventilation_rate_pct}% ventilation</p>
          <p className="timestamp">{plan.explanation[0]}</p>
        </div>
      )}
    </section>
  );
}
