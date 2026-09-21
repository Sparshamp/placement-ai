function percent(ratio) {
  return `${Math.round((ratio || 0) * 100)}%`;
}

export default function SkillGapAnalysis({ analysis, onClose }) {
  if (!analysis) return null;

  const { focusTrack, learningPath, repeatedGaps, closestRoles, jobBreakdown, explanation } = analysis;
  const noteBySkill = Object.fromEntries((learningPath || []).map((step) => [step.skill, step]));
  const sequence = explanation?.strategicLearningSequence?.length
    ? explanation.strategicLearningSequence
    : (learningPath || []).map((step) => step.skill);

  return (
    <div className="card skill-gap">
      <div className="review-header">
        <div>
          <h2>Skill gap analysis</h2>
          <p className="muted">
            Based on your top {jobBreakdown?.length || 0} recommended role
            {jobBreakdown?.length === 1 ? "" : "s"}
          </p>
        </div>
        <button type="button" className="subtle" onClick={onClose}>Close</button>
      </div>

      {explanation?.headline && <p className="skill-gap-headline">{explanation.headline}</p>}
      {explanation?.summary && <p className="skill-gap-summary">{explanation.summary}</p>}

      {focusTrack && (
        <p className="skill-gap-focus">
          <span className="skill-chip">{focusTrack.category}</span>
          <span>{focusTrack.reason}</span>
        </p>
      )}

      {explanation?.jobAdvice?.length > 0 && (
        <>
          <h3>Coach notes for each role</h3>
          <div className="skill-gap-advice">
            {explanation.jobAdvice.map((item) => (
              <article key={item.title} className="skill-gap-advice-card">
                <h4>{item.title}</h4>
                <p>{item.advice}</p>
              </article>
            ))}
          </div>
        </>
      )}

      {sequence.length > 0 && (
        <>
          <h3>Suggested learning path</h3>
          <ol className="skill-gap-path">
            {sequence.map((skill) => {
              const step = noteBySkill[skill];
              return (
                <li key={skill}>
                  <div className="skill-gap-path-title">
                    <strong>{skill}</strong>
                    {step?.category && <span className="faint"> · {step.category}</span>}
                    {step?.readiness && (
                      <span className={`readiness readiness--${step.readiness}`}>
                        {step.readiness.replace("_", " ")}
                      </span>
                    )}
                  </div>
                  {step?.note && <p className="muted">{step.note}</p>}
                </li>
              );
            })}
          </ol>
        </>
      )}

      {repeatedGaps?.length > 0 && (
        <>
          <h3>Skills blocking multiple roles</h3>
          <ul className="skill-gap-chips">
            {repeatedGaps.map((gap) => (
              <li key={gap.skill}>
                <strong>{gap.skill}</strong>
                <span className="faint">
                  {" "}blocks {gap.blocksRoles} role{gap.blocksRoles === 1 ? "" : "s"}
                  {gap.roles?.length > 0 ? ` · ${gap.roles.join(", ")}` : ""}
                </span>
              </li>
            ))}
          </ul>
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
                <span className="faint"> — {percent(role.matchRatio)} skill match</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {explanation?.closing && <p className="skill-gap-closing">{explanation.closing}</p>}

      {explanation && (
        <p className="faint skill-gap-source">
          {explanation.usedLlm
            ? "Coaching copy was written from your resume and these matches."
            : "This explanation was generated locally from your matched skills, not by an AI model."}
        </p>
      )}
    </div>
  );
}
