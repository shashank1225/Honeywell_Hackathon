import { useState } from "react";

export default function GoalsPanel() {
  const [objective, setObjective] = useState("energy_reduction");
  const [target, setTarget] = useState(15);
  const [goal, setGoal] = useState(null);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    const response = await fetch("/goals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, target_percent: Number(target), priority: 75 }),
    });
    if (!response.ok) {
      setError("Telemetry is still loading. Please try again in a few seconds.");
      return;
    }
    setGoal(await response.json());
    setError("");
  }

  return (
    <section className="panel">
      <div className="panel-header"><h2>Goal Management</h2><span className="connection connected">AGMS</span></div>
      <form onSubmit={submit} className="strategy-form">
        <label htmlFor="managed-goal">Objective
          <select id="managed-goal" value={objective} onChange={(event) => setObjective(event.target.value)}>
            <option value="energy_reduction">Reduce energy</option>
            <option value="comfort">Improve comfort</option>
            <option value="carbon_reduction">Reduce carbon</option>
          </select>
        </label>
        <label htmlFor="goal-target">Target (%)<input id="goal-target" type="number" min="1" max="50" value={target} onChange={(event) => setTarget(event.target.value)} /></label>
        <button type="submit">Negotiate goal</button>
      </form>
      {error && <p className="error">{error}</p>}
      {goal && <div className="strategy-result"><p><strong>{goal.status}</strong> · expected reduction {goal.assessment.expected_reduction_percent}%</p><p className="timestamp">{goal.assessment.rationale}</p></div>}
    </section>
  );
}
