export default function TailoredResume({ result, downloadUrl, onClose }) {
  if (!result) return null;

  return (
    <div className="card tailored-resume">
      <div className="review-header">
        <div>
          <h2>Tailored resume</h2>
          <p className="muted">
            Prepared from your original resume for {result.title}
            {result.company ? ` at ${result.company}` : ""}.
          </p>
        </div>
        <button type="button" className="subtle" onClick={onClose}>Close</button>
      </div>

      <p>{result.summary}</p>
      <p className="faint">
        This version reorganizes and emphasizes information already in your resume.
        It does not add experience, skills, or credentials you did not provide.
      </p>

      {result.focus?.length > 0 && (
        <p className="muted">Emphasis: {result.focus.join(" · ")}</p>
      )}

      <pre className="mono tailored-preview">{result.resumeMarkdown}</pre>

      <div className="job-card-actions">
        {downloadUrl && (
          <a href={downloadUrl} className="button-link primary-link">Download Word document</a>
        )}
        <button type="button" onClick={onClose}>Back to jobs</button>
      </div>
    </div>
  );
}
