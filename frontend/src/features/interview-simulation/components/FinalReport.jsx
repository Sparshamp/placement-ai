// src/features/interview-simulation/components/FinalReport.jsx
export default function FinalReport({ report }) {
  if (!report) return null;
  return (
    <div className="final-report">
      <h2>Final Report</h2>
      <div className="report-body">{report.finalReport}</div>
      <p className="emotion-summary">
        Overall dominant emotion: {report.emotionSummary?.overall_dominant ?? "N/A"}
      </p>
    </div>
  );
}