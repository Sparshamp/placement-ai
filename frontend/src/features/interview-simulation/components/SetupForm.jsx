// src/features/interview-simulation/components/SetupForm.jsx
import { useState } from "react";

export default function SetupForm({ onSubmit, loading }) {
  const [resumeFile, setResumeFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [domain, setDomain] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!resumeFile || !jobDescription || !domain) return;
    onSubmit(resumeFile, jobDescription, domain);
  };

  return (
    <form className="setup-form" onSubmit={handleSubmit}>
      <h1>Mock Interview</h1>
      <p className="subhead">Upload your resume and the job details to begin.</p>

      <div className="field">
        <label>Resume (PDF, DOCX, or TXT)</label>
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <div className="field">
        <label>Role title</label>
        <input
          type="text"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Job description</label>
        <textarea
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
        />
      </div>

      <button className="btn-primary" type="submit" disabled={loading}>
        {loading ? "Starting..." : "Start Interview"}
      </button>
    </form>
  );
}