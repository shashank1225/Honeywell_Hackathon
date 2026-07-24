import { useState } from "react";

export default function SetpointPanel({ setpoints, onUpdated }) {
  const [temperature, setTemperature] = useState(22);
  const [ventilation, setVentilation] = useState(50);
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
      </div>

      {setpoints && (
        <p className="current-setpoints">
          Active setpoints: {setpoints.hvac_temperature_c} °C ·{" "}
          {setpoints.ventilation_rate_pct}% ventilation
        </p>
      )}
      {message && <p className="message">{message}</p>}
    </section>
  );
}
