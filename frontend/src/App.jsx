import Dashboard from "./components/Dashboard.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <div>
          <p className="eyebrow">Honeywell Hackathon</p>
          <h1>AABOS Building Dashboard</h1>
          <p className="subtitle">
            Real-time telemetry from the EnergyPlus digital twin
          </p>
        </div>
        <div className="status-pill">Live Stream</div>
      </header>
      <Dashboard />
    </div>
  );
}
