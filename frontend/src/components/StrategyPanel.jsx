import { useState } from "react";

export default function StrategyPanel() {
  const [objective, setObjective] = useState("energy_reduction");
  const [target, setTarget] = useState(10);
  const [plan, setPlan] = useState(null);
  const [llmUsed, setLlmUsed] = useState(false);
  const [mcpTools, setMcpTools] = useState([]);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);

  async function createFastPlan(event) {
    event.preventDefault();
    setError("");
    const response = await fetch("/strategy/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, target_percent: Number(target) }),
    });
    if (!response.ok) {
      setError("Telemetry is still loading. Please try again in a few seconds.");
      return;
    }
    setPlan(await response.json());
    setLlmUsed(false);
    setMcpTools([]);
  }

  async function requestLlmPlan() {
    setError("");
    setGenerating(true);
    const response = await fetch("/strategy/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, target_percent: Number(target) }),
    });
    if (!response.ok) {
      setGenerating(false);
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
        setMcpTools(job.mcp_tools_used ?? []);
        setGenerating(false);
        return;
      }
      if (job.status === "failed") {
        setError(job.error || "Strategic planning failed before a policy was produced.");
        setGenerating(false);
        return;
      }
    }
    setGenerating(false);
    setError("Strategic planning is still running. The local model may be loading; please wait and try again.");
  }

  return (
    <section className="panel strategy-panel">
      <div className="panel-header"><h2>Strategic Planning</h2><span className="connection connected">slow loop</span></div>
      <form onSubmit={createFastPlan} className="strategy-form">
        <label htmlFor="goal">Goal</label>
        <select id="goal" value={objective} onChange={(event) => setObjective(event.target.value)}>
          <option value="energy_reduction">Reduce energy</option>
          <option value="comfort">Prioritize comfort</option>
          <option value="carbon_reduction">Reduce carbon</option>
        </select>
        <label htmlFor="target">Target (%)</label>
        <input id="target" type="number" min="1" max="50" value={target} onChange={(event) => setTarget(event.target.value)} />
        <button type="submit">Generate fast plan</button>
        <button type="button" onClick={requestLlmPlan} disabled={generating}>
          {generating ? "Local LLM is thinking…" : "Refine with local LLM"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {plan && (
        <div className="strategy-result">
          <p><strong>{plan.selected_policy.replaceAll("_", " ")}</strong> · {Math.round(plan.confidence * 100)}% confidence</p>
          <p className="message">{llmUsed ? "Local Llama 3.2 generated this strategic policy." : "Live specialized agents generated this immediate policy."}</p>
          {llmUsed && <p className="timestamp">MCP tools used: {mcpTools.join(", ") || "awaiting tool audit"}</p>}
          <p>Proposed: {plan.proposed_setpoints.hvac_temperature_c} °C · {plan.proposed_setpoints.ventilation_rate_pct}% ventilation</p>
          <p className="timestamp">{plan.explanation[0]}</p>
        </div>
      )}
    </section>
  );
}
