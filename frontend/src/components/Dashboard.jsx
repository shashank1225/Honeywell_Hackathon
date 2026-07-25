import { useEffect, useState } from "react";
import MetricCard from "./MetricCard.jsx";
import SetpointPanel from "./SetpointPanel.jsx";
import StrategyPanel from "./StrategyPanel.jsx";
import SelfHealingPanel from "./SelfHealingPanel.jsx";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/telemetry/stream`;

function formatTimestamp(value) {
  if (!value) return "Waiting for data…";
  return new Date(value).toLocaleString();
}

export default function Dashboard() {
  const [telemetry, setTelemetry] = useState(null);
  const [setpoints, setSetpoints] = useState(null);
  const [connectionState, setConnectionState] = useState("connecting");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/setpoints")
      .then((response) => response.json())
      .then(setSetpoints)
      .catch(() => setError("Unable to load setpoints"));

    const socket = new WebSocket(WS_URL);

    socket.onopen = () => setConnectionState("connected");
    socket.onclose = () => setConnectionState("disconnected");
    socket.onerror = () => setError("Telemetry stream disconnected");
    socket.onmessage = (event) => {
      setTelemetry(JSON.parse(event.data));
      setError("");
    };

    return () => socket.close();
  }, []);

  async function refreshSetpoints() {
    const response = await fetch("/setpoints");
    setSetpoints(await response.json());
  }

  return (
    <main className="dashboard">
      <section className="panel">
        <div className="panel-header">
          <h2>Live Telemetry</h2>
          <span className={`connection ${connectionState}`}>{connectionState}</span>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="metric-grid">
          <MetricCard
            label="Temperature"
            value={telemetry ? `${telemetry.temperature_c} °C` : "--"}
            hint={`Zone: ${telemetry?.zone ?? "main"}`}
          />
          <MetricCard
            label="Humidity"
            value={telemetry ? `${telemetry.humidity_pct} %` : "--"}
            hint="Relative humidity"
          />
          <MetricCard
            label="Occupancy"
            value={telemetry ? `${telemetry.occupancy_pct} %` : "--"}
            hint="Estimated occupancy"
          />
          <MetricCard
            label="Power"
            value={telemetry ? `${telemetry.power_kw} kW` : "--"}
            hint="HVAC + plug load"
          />
        </div>
        <p className="timestamp">Last update: {formatTimestamp(telemetry?.timestamp)}</p>
      </section>

      <SetpointPanel setpoints={setpoints} onUpdated={refreshSetpoints} />
      <StrategyPanel />
      <SelfHealingPanel />
    </main>
  );
}
