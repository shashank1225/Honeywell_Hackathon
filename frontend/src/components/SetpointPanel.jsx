import { useState } from "react";

export default function SetpointPanel({ setpoints, onUpdated }) {
  const [temperature, setTemperature] = useState(22);
  const [ventilation, setVentilation] = useState(50);
  const [lighting, setLighting] = useState(100);
  const [message, setMessage] = useState("");

  async function submitHvac(event) {
    event.preventDefault();
    const response = await fetch(`/setpoints/hvac?temperature_c=${temperature}`, {
      method: "PUT",
    });
    if (response.ok) {
      setMessage("HVAC setpoint updated");
      onUpdated();
    } else {
      setMessage("Failed to update HVAC setpoint");
    }
  }

  async function submitVentilation(event) {
    event.preventDefault();
    const response = await fetch(
      `/setpoints/ventilation?ventilation_rate_pct=${ventilation}`,
      { method: "PUT" },
    );
    if (response.ok) {
      setMessage("Ventilation setpoint updated");
      onUpdated();
    } else {
      setMessage("Failed to update ventilation setpoint");
    }
  }

  async function submitLighting(event) {
    event.preventDefault();
    const response = await fetch(`/setpoints/lighting?lighting_level_pct=${lighting}`, { method: "PUT" });
    if (response.ok) {
      setMessage("Lighting schedule updated");
      onUpdated();
    } else {
      setMessage("Failed to update lighting schedule");
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Control Setpoints</h2>
      </div>
      <div className="setpoint-grid">
        <form onSubmit={submitHvac} className="setpoint-form">
          <label htmlFor="hvac">HVAC Temperature (°C)</label>
          <input
            id="hvac"
            type="number"
            min="16"
            max="30"
            step="0.5"
            value={temperature}
            onChange={(event) => setTemperature(Number(event.target.value))}
          />
          <button type="submit">Apply HVAC</button>
        </form>

        <form onSubmit={submitVentilation} className="setpoint-form">
          <label htmlFor="ventilation">Ventilation Rate (%)</label>
          <input
            id="ventilation"
            type="number"
            min="0"
            max="100"
            step="1"
            value={ventilation}
            onChange={(event) => setVentilation(Number(event.target.value))}
          />
          <button type="submit">Apply Ventilation</button>
        </form>

        <form onSubmit={submitLighting} className="setpoint-form">
          <label htmlFor="lighting">Lighting Level (%)</label>
          <input
            id="lighting"
            type="number"
            min="0"
            max="100"
            step="1"
            value={lighting}
            onChange={(event) => setLighting(Number(event.target.value))}
          />
          <button type="submit">Apply Lighting</button>
        </form>
      </div>

      {setpoints && (
        <p className="current-setpoints">
          Active setpoints: {setpoints.hvac_temperature_c} °C ·{" "}
          {setpoints.ventilation_rate_pct}% ventilation · {setpoints.lighting_level_pct}% lighting
        </p>
      )}
      {message && <p className="message">{message}</p>}
    </section>
  );
}
