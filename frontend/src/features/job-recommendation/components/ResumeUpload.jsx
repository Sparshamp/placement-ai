import { useState } from "react";

export default function ResumeUpload({ onSubmit, loading }) {
  const [resumeFile, setResumeFile] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!resumeFile || loading) return;
    onSubmit(resumeFile);
  };

  return (
    <form className="card jobs-upload" onSubmit={handleSubmit}>
      <h1>Job Recommendations</h1>
      <p className="muted">
        Upload your resume. We'll match it to roles from our job dataset and let you
        tailor a version of your resume for each recommendation.
      </p>

      <div className="field">
        <label htmlFor="jobs-resume">Resume (PDF, DOCX, or TXT)</label>
        <input
          id="jobs-resume"
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
        />
        {resumeFile && <p className="faint">{resumeFile.name}</p>}
      </div>

      <button className="primary" type="submit" disabled={loading || !resumeFile}>
        {loading ? "Analyzing resume…" : "Analyze Resume"}
      </button>
    </form>
  );
}
