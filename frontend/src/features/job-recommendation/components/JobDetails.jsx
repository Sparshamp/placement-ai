export default function JobDetails({ job, onClose, onTailor }) {
  if (!job) return null;

  return (
    <div className="card job-details">
      <div className="review-header">
        <div>
          <h2>{job.title}</h2>
          <p className="muted">
            {[job.company, job.location, job.workType].filter(Boolean).join(" · ")}
          </p>
        </div>
        <button type="button" className="subtle" onClick={onClose}>Close</button>
      </div>

      <div className="job-meta-row">
        {job.domain && <span className="muted">Area: {job.domain}</span>}
        {job.experienceLevel && <span className="muted">Level: {job.experienceLevel}</span>}
        {job.salary && job.salary !== "Not Disclosed" && (
          <span className="muted">Salary: {job.salary}</span>
        )}
      </div>

      {job.matchingSkills?.length > 0 && (
        <>
          <h3>Skills you already have</h3>
          <p>{job.matchingSkills.join(" · ")}</p>
        </>
      )}

      {job.skills?.length > 0 && (
        <>
          <h3>Role skills</h3>
          <p>{job.skills.join(" · ")}</p>
        </>
      )}

      {job.relevanceNote && (
        <>
          <h3>Why this may fit</h3>
          <p>{job.relevanceNote}</p>
        </>
      )}

      {job.description && (
        <>
          <h3>Job description</h3>
          <p className="job-description">{job.description}</p>
        </>
      )}

      <button type="button" className="primary" onClick={() => onTailor(job)}>
        Tailor Resume
      </button>
    </div>
  );
}
