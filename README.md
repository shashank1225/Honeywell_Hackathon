# AABOS — Autonomous Adaptive Building Operating System

AABOS is a closed-loop building controller that uses an EnergyPlus digital twin, Kafka telemetry, a local open-source LLM, MCP, and deterministic safety controls to optimize energy while protecting comfort.

## What runs in the demo

```text
EnergyPlus → Kafka → rolling telemetry window → four live agents
                                             ↓
                           Decision Engine → Safety Sentinel → generated IDF → next EnergyPlus cycle

AGMS / operator goal → asynchronous local Ollama LLM → policy handoff → Safety Sentinel → next cycle
```

The fast path never waits for an LLM, database, Kafka consumer, or network call. Every EnergyPlus telemetry cycle is evaluated immediately by the Comfort, Energy, Occupancy, and Carbon agents; their selected high-level policy is sent through the deterministic Safety Sentinel before the next `modified.idf` is generated and run.

The local `llama3.2:3b` model is a strategic supervisor only. It receives compact Kafka sliding-window aggregates, can recommend a named policy, and its handoff is safety-validated on the following cycle. It never emits actuator commands or writes EnergyPlus models directly.

## Components implemented

- **AGMS and Goal Negotiation:** human and proactive goals, feasibility evidence, prioritization, and conflicting lower-priority goals marked for negotiation.
- **Strategic Reasoning:** the LLM operates as an event-driven cognitive reasoning layer. It is invoked whenever significant building-state changes occur (occupancy, weather-influenced demand, energy spikes, comfort degradation, or new goals) and also performs periodic strategic reviews. Rather than issuing low-level actuator commands, it recommends policy updates and optimization strategies that the Decision Engine translates into safety-validated control actions.
- **APEE and Automation Memory:** each observed control cycle stores a bounded reward, comfort, energy, confidence, telemetry state, and counterfactual comparison. PostgreSQL persistence occurs on a background worker.
- **Counterfactual Automation:** read-only projections compare the selected policy against all alternatives; realized savings remain based on actual measured EnergyPlus power.
- **Safety Sentinel:** bounds HVAC, ventilation, and lighting changes; rejects rapid reversals; every REST, MCP, autonomous, LLM, and recovery proposal uses the same gateway.
- **MCP Server:** exposes telemetry and current setpoints as resources and safety-gated HVAC, ventilation, and lighting schedule tools.
- **Runtime models:** [`energyplus/baseline.idf`](energyplus/baseline.idf) remains the source model. A safety-approved policy writes [`energyplus/generated/modified.idf`](energyplus/generated/modified.idf), including thermostat and lighting schedule updates, before the next EnergyPlus cycle.

## Prompt-latency and log management

EnergyPlus output is never fed to the LLM verbatim. Kafka telemetry is reduced to a fixed rolling window containing average/min/max temperature, humidity, occupancy, power, peak demand, and estimated energy. The prompt is bounded and requests JSON only.

Ollama is warmed in a background thread at startup, held for 30 minutes, constrained to a 2,048-token context and 80 generated tokens, and called only from the slow strategic worker. If it is unavailable, that worker produces a deterministic plan while the fast control loop continues unchanged.

## Demo run

Start Docker services, Ollama, the backend, then the frontend:

```bash
docker compose up -d
ollama serve
```

In a separate terminal:

```bash
SIMULATION_ENABLED=true \
LLM_ENABLED=true \
LLM_MODEL=llama3.2:3b \
ENERGYPLUS_EXECUTABLE=/usr/local/bin/energyplus \
ENERGYPLUS_IDF_PATH=/Applications/EnergyPlus-26-1-0/ExampleFiles/RefBldgSmallOfficeNew2004_Chicago.idf \
ENERGYPLUS_WEATHER_PATH=/Applications/EnergyPlus-26-1-0/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw \
ENERGYPLUS_OUTPUT_DIR=var/energyplus \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Show live telemetry, four-agent arbitration, generated-IDF setpoints, counterfactual evidence, captured baseline savings, proactive AGMS goals, and self-healing fallback. Use **Refine with local LLM** to demonstrate the optional slow strategic path.

## Verification

```bash
.venv/bin/pytest -q
cd frontend && npm run build
```
