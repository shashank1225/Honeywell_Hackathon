import { useState } from "react";

export default function SelfHealingPanel() {
  const [expected, setExpected] = useState(95);
  const [actual, setActual] = useState(89);
  const [status, setStatus] = useState(null);

  async function evaluate(event) {
    event.preventDefault();
    const response = await fetch("/self-healing/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_comfort: Number(expected), actual_comfort: Number(actual) }),
    });
    if (response.ok) setStatus(await response.json());
  }

  return (
    <section className="panel self-healing-panel">
      <div className="panel-header"><h2>Self-Healing Loop</h2><span className="connection connected">feedback</span></div>
      <form onSubmit={evaluate} className="strategy-form">
        <label htmlFor="expected-comfort">Expected comfort (%)<input id="expected-comfort" type="number" min="0" max="100" value={expected} onChange={(event) => setExpected(event.target.value)} /></label>
        <label htmlFor="actual-comfort">Actual comfort (%)<input id="actual-comfort" type="number" min="0" max="100" value={actual} onChange={(event) => setActual(event.target.value)} /></label>
        <button type="submit">Evaluate feedback</button>
      </form>
      {status && <p className={status.policy_failed ? "healing-alert" : "message"}>{status.message}</p>}
    </section>
  );
}
