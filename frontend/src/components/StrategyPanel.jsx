import { useEffect, useState } from "react";

export default function StrategyPanel() {
  const [objective, setObjective] = useState("energy_reduction");
  const [target, setTarget] = useState(10);
  const [plan, setPlan] = useState(null);
  const [llmUsed, setLlmUsed] = useState(false);
  const [mcpTools, setMcpTools] = useState([]);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!generating) {
      setElapsedSeconds(0);
      return undefined;
    }
    const timer = window.setInterval(() => setElapsedSeconds((seconds) => seconds + 1), 1000);
    return () => window.clearInterval(timer);
  }, [generating]);

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
    try {
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
        if (!jobResponse.ok) throw new Error("The backend stopped while the strategic job was running.");
        job = await jobResponse.json();
        if (job.status === "completed") {
          setPlan(job.plan);
          setLlmUsed(job.llm_used);
          setMcpTools(job.mcp_tools_used ?? []);
          return;
        }
        if (job.status === "failed") {
          setError(job.error || "Strategic planning failed before a policy was produced.");
          return;
        }
      }
      setError("Strategic planning is still queued. Live autonomous controls remain active; wait for the local LLM to finish, then try again.");
    } catch {
      setError("Backend connection was lost. Restart the backend; this LLM request was not applied.");
    } finally {
      setGenerating(false);
    }
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
          {generating ? `LLM inspecting through MCP… ${elapsedSeconds}s` : "Refine with local LLM"}
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
