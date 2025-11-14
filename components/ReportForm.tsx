"use client";

import { useState } from "react";

type ApiResponse = {
  natalChart: unknown;
  transitPositions: unknown;
  insight?: string | null;
  prompt: string;
};

type ErrorResponse = {
  error: string;
  details?: unknown;
};

const houseSystems = [
  "placidus",
  "koch",
  "whole-sign",
  "equal",
  "regiomontanus",
  "campanus",
];

const orbOptions = [
  { value: "default", label: "Default" },
  { value: "exact", label: "Exact" },
];

export default function ReportForm() {
  const [formState, setFormState] = useState({
    name: "",
    birthDate: "",
    birthTime: "",
    timezoneOffset: "+00:00",
    birthLatitude: "",
    birthLongitude: "",
    currentLatitude: "",
    currentLongitude: "",
    transitDateTime: "",
    houseSystem: "placidus",
    orb: "default",
    ayanamsa: "0",
    language: "en",
    openaiModel: "gpt-4o-mini",
    deepseekModel: "deepseek-chat",
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = event.target;
    setFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const payload = {
        name: formState.name || undefined,
        birthDate: formState.birthDate,
        birthTime: formState.birthTime,
        timezoneOffset: formState.timezoneOffset,
        birthLatitude: formState.birthLatitude ? Number(formState.birthLatitude) : undefined,
        birthLongitude: formState.birthLongitude ? Number(formState.birthLongitude) : undefined,
        currentLatitude: formState.currentLatitude ? Number(formState.currentLatitude) : undefined,
        currentLongitude: formState.currentLongitude ? Number(formState.currentLongitude) : undefined,
        transitDateTime: formState.transitDateTime || undefined,
        houseSystem: formState.houseSystem,
        orb: formState.orb,
        ayanamsa: formState.ayanamsa ? Number(formState.ayanamsa) : undefined,
        language: formState.language || undefined,
        openaiModel: formState.openaiModel || undefined,
        deepseekModel: formState.deepseekModel || undefined,
      };

      const response = await fetch("/api/report", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data: ErrorResponse = await response.json();
        throw new Error(data.error || "Failed to generate report");
      }

      const data: ApiResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error occurred");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Birth Profile</legend>
          <label>
            Name (optional)
            <input name="name" value={formState.name} onChange={handleChange} placeholder="Alex" />
          </label>
          <label>
            Birth date
            <input name="birthDate" type="date" value={formState.birthDate} onChange={handleChange} required />
          </label>
          <label>
            Birth time
            <input name="birthTime" type="time" value={formState.birthTime} onChange={handleChange} required />
          </label>
          <label>
            Timezone offset
            <input
              name="timezoneOffset"
              value={formState.timezoneOffset}
              onChange={handleChange}
              placeholder="+05:30"
              required
            />
            <small className="field-hint">Use the offset for the birth location, e.g. -04:00.</small>
          </label>
          <label>
            Birth latitude
            <input
              name="birthLatitude"
              type="number"
              step="0.000001"
              value={formState.birthLatitude}
              onChange={handleChange}
              required
            />
          </label>
          <label>
            Birth longitude
            <input
              name="birthLongitude"
              type="number"
              step="0.000001"
              value={formState.birthLongitude}
              onChange={handleChange}
              required
            />
          </label>
        </fieldset>

        <fieldset>
          <legend>Current Transit Settings</legend>
          <label>
            Transit datetime (optional)
            <input
              name="transitDateTime"
              type="datetime-local"
              value={formState.transitDateTime}
              onChange={handleChange}
            />
            <small className="field-hint">Defaults to the current UTC time if left empty.</small>
          </label>
          <label>
            Current latitude (optional)
            <input
              name="currentLatitude"
              type="number"
              step="0.000001"
              value={formState.currentLatitude}
              onChange={handleChange}
            />
          </label>
          <label>
            Current longitude (optional)
            <input
              name="currentLongitude"
              type="number"
              step="0.000001"
              value={formState.currentLongitude}
              onChange={handleChange}
            />
          </label>
        </fieldset>

        <fieldset>
          <legend>Chart Preferences</legend>
          <label>
            House system
            <select name="houseSystem" value={formState.houseSystem} onChange={handleChange}>
              {houseSystems.map((system) => (
                <option key={system} value={system}>
                  {system}
                </option>
              ))}
            </select>
          </label>
          <label>
            Orb preference
            <select name="orb" value={formState.orb} onChange={handleChange}>
              {orbOptions.map((orb) => (
                <option key={orb.value} value={orb.value}>
                  {orb.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ayanamsa
            <select name="ayanamsa" value={formState.ayanamsa} onChange={handleChange}>
              <option value="0">0 - Tropical</option>
              <option value="1">1 - Lahiri</option>
              <option value="3">3 - Raman</option>
              <option value="5">5 - KP</option>
            </select>
          </label>
          <label>
            Language code
            <input name="language" value={formState.language} onChange={handleChange} />
          </label>
          <label>
            OpenAI model
            <input name="openaiModel" value={formState.openaiModel} onChange={handleChange} />
          </label>
          <label>
            DeepSeek model
            <input name="deepseekModel" value={formState.deepseekModel} onChange={handleChange} />
          </label>
        </fieldset>

        <button type="submit" disabled={submitting}>
          {submitting ? "Generating report…" : "Generate report"}
        </button>
      </form>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="output-grid">
          <section>
            <h2>Natal chart payload</h2>
            <pre>{JSON.stringify(result.natalChart, null, 2)}</pre>
          </section>
          <section>
            <h2>Transit data payload</h2>
            <pre>{JSON.stringify(result.transitPositions, null, 2)}</pre>
          </section>
          <section style={{ gridColumn: "1 / -1" }}>
            <h2>AI insight</h2>
            {result.insight ? (
              <div className="alert success">
                <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{result.insight}</p>
              </div>
            ) : (
              <p>No AI insight was generated. Check your API keys.</p>
            )}
            <details>
              <summary>Prompt sent to AI</summary>
              <pre>{result.prompt}</pre>
            </details>
          </section>
        </div>
      )}
    </div>
  );
}
