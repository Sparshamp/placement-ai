import { useState, useEffect } from "react";
import { apiGet, ApiError } from "./api";
import { useAuth } from "../../shared/auth/AuthContext";

export default function Dashboard() {
  const { student } = useAuth();
  const studentId = student?.student_id;
  const [summary, setSummary] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [skills, setSkills] = useState(null);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!studentId) return;
    setError(null);
    apiGet(`/student/${studentId}/summary`)
      .then(setSummary)
      .catch((e) => setError(e instanceof ApiError ? e.detail : e.message));
    apiGet(`/student/${studentId}/history`, { n: 20 })
      .then((data) => setHistory(data.history))
      .catch(() => setHistory([]));
  }, [studentId]);

  useEffect(() => {
    if (!selectedSubject) {
      setSkills(null);
      return;
    }
    apiGet(`/student/${studentId}/skills`, { subject: selectedSubject })
      .then(setSkills)
      .catch((e) => setError(e instanceof ApiError ? e.detail : e.message));
  }, [selectedSubject, studentId]);

  const activeSubjects = summary ? summary.subjects.filter((s) => s.concepts_seen > 0) : [];
  const rows = showAll ? summary?.subjects ?? [] : activeSubjects;
  const sortedRows = [...rows].sort((a, b) => b.avg_mastery - a.avg_mastery);

  const totalMastered = rows.reduce((sum, s) => sum + s.mastered_count, 0);
  const totalAttempts = rows.reduce((sum, s) => sum + s.total_attempts, 0);

  return (
    <div className="page-wide">
      <h2>📊 Student Dashboard</h2>

            <p className="muted">Showing progress for {student?.display_name}</p>

      {error && <p className="warning-text">{error}</p>}

      {rows.length === 0 ? (
        <p className="muted" style={{ marginTop: "1rem" }}>
          No activity yet for this student. Go answer some questions in Practice Session first.
        </p>
      ) : (
        <>
          <div className="summary-stats" style={{ marginTop: "1rem" }}>
            <div className="stat card"><span className="stat-value">{activeSubjects.length}</span><span className="muted">Subjects touched</span></div>
            <div className="stat card"><span className="stat-value">{totalMastered}</span><span className="muted">Concepts mastered</span></div>
            <div className="stat card"><span className="stat-value">{totalAttempts}</span><span className="muted">Total attempts</span></div>
          </div>

          <label className="muted" style={{ display: "block", margin: "1rem 0" }}>
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            {" "}Show subjects with no activity yet
          </label>

          <h3>Mastery by subject</h3>
          <div className="bar-chart">
            {sortedRows.map((s) => (
              <div key={s.subject} className="bar-row">
                <span className="bar-label muted">{s.subject}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${s.avg_mastery * 100}%` }} />
                </div>
                <span className="bar-value mono">{s.avg_mastery.toFixed(2)}</span>
              </div>
            ))}
          </div>

          <table className="data-table" style={{ marginTop: "1rem" }}>
            <thead>
              <tr><th>Subject</th><th>Concepts seen</th><th>Avg mastery</th><th>Mastered</th><th>Attempts</th><th>Accuracy</th></tr>
            </thead>
            <tbody>
              {sortedRows.map((s) => (
                <tr key={s.subject}>
                  <td>{s.subject}</td>
                  <td>{s.concepts_seen}</td>
                  <td className="mono">{s.avg_mastery.toFixed(2)}</td>
                  <td>{s.mastered_count}</td>
                  <td>{s.total_attempts}</td>
                  <td>{(s.accuracy * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 style={{ marginTop: "1.6rem" }}>Drill into a subject</h3>
          <div className="category-grid">
            {activeSubjects.map((s) => (
              <button
                key={s.subject}
                className={selectedSubject === s.subject ? "primary" : ""}
                onClick={() => setSelectedSubject((cur) => (cur === s.subject ? null : s.subject))}
              >
                {s.subject}
              </button>
            ))}
          </div>

          {skills && (
            <>
              <div className="summary-stats" style={{ marginTop: "1rem" }}>
                <div className="stat card">
                  <span className="stat-value">{skills.coverage.coverage_pct}%</span>
                  <span className="muted">{skills.coverage.concepts_seen} of {skills.coverage.total_concepts} concepts</span>
                </div>
                <div className="stat card">
                  <span className="stat-value">{skills.coverage.mastery_pct}%</span>
                  <span className="muted">{skills.coverage.concepts_mastered} mastered</span>
                </div>
              </div>
              <table className="data-table" style={{ marginTop: "1rem" }}>
                <thead>
                  <tr><th>Concept</th><th>Topic</th><th>Subtopic</th><th>Skill</th><th>Attempts</th></tr>
                </thead>
                <tbody>
                  {skills.skills.map((sk) => (
                    <tr key={sk.concept_id}>
                      <td className="mono faint">{sk.concept_id}</td>
                      <td>{sk.topic}</td>
                      <td>{sk.subtopic}</td>
                      <td className="mono">{sk.skill_score.toFixed(2)}</td>
                      <td>{sk.attempts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <h3 style={{ marginTop: "1.6rem" }}>Recent activity</h3>
          {history && history.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr><th>When</th><th>Subject</th><th>Topic</th><th>Difficulty</th><th>Result</th></tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i}>
                    <td className="mono faint">{new Date(h.timestamp).toLocaleString()}</td>
                    <td>{h.subject}</td>
                    <td>{h.topic}</td>
                    <td>{h.difficulty}</td>
                    <td>{h.correct ? "✅" : "❌"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="faint">No recent history.</p>
          )}
        </>
      )}
    </div>
  );
}
