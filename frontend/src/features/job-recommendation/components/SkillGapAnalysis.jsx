export default function SkillGapAnalysis({ analysis, onClose }) {
  if (!analysis) return null;

  const { focusTrack, learningPath, repeatedGaps, closestRoles, jobBreakdown, explanation } = analysis;

  return (
    <div className="card skill-gap">
      <div className="review-header">
        <div>
          <h2>Skill gap analysis</h2>
          <p className="muted">
            Based on your top {jobBreakdown?.length || 0} recommended role{jobBreakdown?.length === 1 ? "" : "s"}
          </p>
        </div>
        <button type="button" className="subtle" onClick={onClose}>Close</button>
      </div>

      {explanation?.summary && <p>{explanation.summary}</p>}

      {focusTrack && (
        <p className="muted">
          Focus track: <strong>{focusTrack.category}</strong> — {focusTrack.reason}
        </p>
      )}

      {repeatedGaps?.length > 0 && (
        <>
          <h3>Skills blocking multiple roles</h3>
          <ul className="skill-gap-list">
            {repeatedGaps.map((gap) => (
              <li key={gap.skill}>
                <strong>{gap.skill}</strong> — blocks {gap.blocksRoles} role{gap.blocksRoles === 1 ? "" : "s"}
                {gap.roles?.length > 0 && (
                  <span className="faint"> ({gap.roles.join(", ")})</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {learningPath?.length > 0 && (
        <>
          <h3>Suggested learning path</h3>
          <ol className="skill-gap-list">
            {learningPath.map((step) => (
              <li key={step.skill}>
                <strong>{step.skill}</strong>
                <span className="faint"> · {step.category}</span>
                <p className="muted">{step.note}</p>
              </li>
            ))}
          </ol>
        </>
      )}

      {closestRoles?.length > 0 && (
        <>
          <h3>Closest-matching roles</h3>
          <ul className="skill-gap-list">
            {closestRoles.map((role) => (
              <li key={role.jobIndex}>
                <strong>{role.title}</strong>
                {role.company ? ` at ${role.company}` : ""}
                <span className="faint"> — {Math.round((role.matchRatio || 0) * 100)}% skill match</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {explanation && !explanation.usedLlm && (
        <p className="faint">
          This explanation was generated locally from your matched skills, not by an AI model.
        </p>
      )}
    </div>
  );
}