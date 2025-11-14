import ReportForm from "../components/ReportForm";

export default function HomePage() {
  return (
    <div>
      <h1 className="section-title">Astrology Intelligence Dashboard</h1>
      <p className="subtitle">
        Provide your birth details to fetch real natal chart and current transit data from the
        Prokerala API. We will store the raw payloads for review and craft a concise interpretation
        using OpenAI, falling back to DeepSeek when necessary.
      </p>
      <ReportForm />
    </div>
  );
}
