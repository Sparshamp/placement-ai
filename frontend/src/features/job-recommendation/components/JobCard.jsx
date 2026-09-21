export default function JobCard({ job, onViewDetails, onTailor }) {
  const skills = job.matchingSkills?.length ? job.matchingSkills : job.skills;

  return (
    <article className="card job-card">
      <div className="job-card-top">
        <div>
          <h3>{job.title}</h3>
          <p className="muted">
            {[job.company, job.location].filter(Boolean).join(" · ")}
          </p>
        </div>
        {typeof job.relevancePercent === "number" && (
          <span className="job-match muted">{job.relevancePercent}% match</span>
        )}
      </div>

      {skills?.length > 0 && (
        <p className="job-skills">
          <span className="faint">Relevant skills: </span>
          {skills.join(" · ")}
        </p>
      )}

      {job.summary && <p>{job.summary}</p>}

      <div className="job-card-actions">
        <button type="button" onClick={() => onViewDetails(job)}>View Details</button>
        <button type="button" className="primary" onClick={() => onTailor(job)}>
          Tailor Resume
        </button>
      </div>
    </article>
  );
}
