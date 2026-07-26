# AABOS System Architecture

## 1. Objective

AABOS (Autonomous Adaptive Building Operating System) is a closed-loop building-control proof of concept. It uses EnergyPlus as the physics-based digital twin, a local open-source LLM (`llama3.2:3b` through Ollama) for strategic reasoning, Kafka for telemetry decoupling, FastAPI for the control/API layer, and FastMCP tools for governed LLM access to runtime evidence.

The design keeps fast, safety-critical control deterministic while allowing slower LLM reasoning to improve policy selection without blocking EnergyPlus telemetry.

```text
EnergyPlus → telemetry → Kafka → rolling window → four fast agents
     ↑                                                ↓
generated modified.idf ← Safety Sentinel ← Decision Engine

AGMS / operator goal → asynchronous local LLM → MCP inspection tools
                                             ↓
                               queued policy → Safety Sentinel → next cycle
```

## 2. Closed-Loop Control Path

1. `EnergyPlusSubprocessBackend` writes the current approved setpoints into `energyplus/generated/modified.idf` and runs EnergyPlus.
2. It extracts zone temperature, humidity, occupancy, and electrical power from EnergyPlus outputs and publishes telemetry.
3. Kafka carries telemetry to the consumer; if Kafka is unavailable, the runner directly publishes to the shared building state so control continues.
4. A rolling telemetry aggregator retains a bounded window of recent values for strategic reasoning.
5. The deterministic Decision Engine invokes four specialized agents on every telemetry cycle: Comfort, Energy, Occupancy, and Carbon.
6. The selected policy is translated to HVAC, ventilation, and lighting setpoints. The Safety Sentinel validates limits and rate-of-change constraints before the common control gateway applies them.
7. The next EnergyPlus cycle consumes the newly generated IDF. Baseline and actual EnergyPlus power are accumulated to calculate realized savings.

For a responsive demo, the runner uses a representative occupied warm-period EnergyPlus frame for the comparison rather than an overnight winter startup frame. Both baseline and AI-controlled cases are evaluated against the same simulated conditions. A verified run produced 22.04 kW baseline power and 17.50 kW under Energy Saver, a 20.6% reduction.

## 3. Tool-Calling and MCP Architecture

FastMCP exposes building state as resources and controlled operations as tools.

**Resources**

- `building://telemetry/current` — latest simulated building telemetry.
- `building://setpoints/current` — active approved setpoints.

**Reasoning tools used by the LLM**

- `inspect_building_runtime` — composite read-only tool that returns current building context, generated-IDF evidence, and a bounded EnergyPlus error-log tail.
- `queue_policy_recommendation` — queues only a high-level policy for next-cycle Safety Sentinel validation; it never commands actuators directly.

**Additional governed tools**

- `get_building_context`, `inspect_generated_model`, and `read_energyplus_runtime_errors` support transparent runtime inspection.
- `set_hvac_temperature`, `adjust_ventilation`, and `adjust_lighting` are safety-gated through the same control gateway as all other inputs.

The strategic LLM call has a mandatory tool-call contract: it must invoke `inspect_building_runtime` before returning a policy. The worker records the tools actually used in the strategic-job audit shown on the dashboard. The LLM can recommend `balanced`, `energy_saver`, `comfort_first`, or `carbon_aware`, but cannot bypass the Decision Engine, Safety Sentinel, or generated-IDF writer.

## 4. Prompt Engineering Strategy

The local LLM is a strategic supervisor, not a low-level controller. Its prompt:

- states that it must not issue actuator commands or edit an IDF directly;
- requires the MCP runtime-inspection tool before policy reasoning;
- provides only compact rolling-window telemetry: average/min/max temperature, humidity, occupancy, average/peak power, and estimated energy;
- specifies fixed safety envelopes and the available policy enum;
- requests a short, schema-constrained JSON response containing `policy` and `rationale`.

This design reduces hallucinated control actions, keeps outputs machine-readable, and makes the deterministic safety layer the final authority.

## 5. Prompt-Latency Management

The system has two separate horizons.

- **Fast control horizon:** EnergyPlus telemetry, four agents, Decision Engine, and Safety Sentinel run every control cycle. This path never waits for Ollama, the database, or a network call.
- **Strategic horizon:** AGMS events, operator goals, and periodic reviews are sent to a background strategic work queue. Ollama runs in that worker, not in the telemetry callback. The model is warmed asynchronously at startup, retained for 30 minutes, limited to a 2,048-token context and 120 generated tokens, and uses a compact MCP evidence call.

If Ollama is unavailable or times out, the worker produces a deterministic strategy plan while the live control loop continues. A dashboard reconnect strategy also recovers the telemetry display after a backend/WebSocket interruption.

## 6. Long Simulation-Log Management

AABOS never sends raw EnergyPlus logs to the LLM.

- Kafka telemetry is summarized in a fixed sliding window rather than forwarded as raw output files.
- The generated IDF is inspected only as bounded header/metadata evidence.
- Runtime errors are read only through a bounded tail; the composite MCP tool limits this to 600 characters.
- Full EnergyPlus outputs remain local artifacts for diagnosis and are not placed in the LLM context window.

This preserves the evidence needed for reasoning and error awareness while preventing excessive prompt size or control-loop latency.

## 7. Safety, Recovery, and Observability

The Safety Sentinel enforces HVAC, ventilation, lighting, and rapid-reversal limits for REST, MCP, autonomous, LLM, and recovery proposals. When observed comfort materially misses the expected result, the Self-Healing Loop records the failed policy, requests a safe corrective fallback, and continues the loop automatically.

The dashboard exposes live telemetry, active setpoints, autonomous agent recommendations, Savings versus baseline, LLM/MCP audit evidence, counterfactual comparisons, and self-healing status. `energyplus/baseline.idf` remains immutable; each approved runtime action creates or updates `energyplus/generated/modified.idf`.

## 8. Demonstration Evidence

The demo visibly proves the following sequence:

1. EnergyPlus produces changing telemetry.
2. Specialized agents make an autonomous policy decision.
3. The Safety Sentinel validates the policy and the runtime IDF updates.
4. The next EnergyPlus evaluation returns changed energy and comfort metrics.
5. The local LLM performs MCP inspection and queues a safety-governed strategic policy.
6. A comfort shortfall triggers automatic self-correction/fallback without source-code modification.
