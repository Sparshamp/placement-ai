import { useState } from "react";
import ResumeUpload from "./components/ResumeUpload";
import JobCard from "./components/JobCard";
import JobDetails from "./components/JobDetails";
import TailoredResume from "./components/TailoredResume";
import { jobsApi } from "./api";
import "./jobs.css";
import SkillGapAnalysis from "./components/SkillGapAnalysis";

export default function JobsPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [tailored, setTailored] = useState(null);
  const [tailoring, setTailoring] = useState(false);
  const [skillGap, setSkillGap] = useState(null);
  const [loadingSkillGap, setLoadingSkillGap] = useState(false);

  const handleAnalyze = async (file) => {
    setLoading(true);
    setError(null);
    setSelectedJob(null);
    setTailored(null);
    try {
      const data = await jobsApi.recommend(file);
      setSessionId(data.sessionId);
      setProfile(data.profile);
      setJobs(data.jobs || []);
    } catch (err) {
      setError(jobsApi.userMessage(err));
      setSessionId(null);
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetails = async (job) => {
    setError(null);
    setTailored(null);
    try {
      const detail = await jobsApi.getJob(sessionId, job.jobIndex);
      setSelectedJob(detail);
    } catch (err) {
      setError(jobsApi.userMessage(err));
    }
  };

  const handleTailor = async (job) => {
    setError(null);
    setTailoring(true);
    try {
      const result = await jobsApi.tailorResume(sessionId, job.jobIndex);
      setTailored(result);
      setSelectedJob(null);
    } catch (err) {
      setError(jobsApi.userMessage(err));
    } finally {
      setTailoring(false);
    }
  };
    const handleSkillGap = async () => {
    setError(null);
    setLoadingSkillGap(true);
    try {
      const data = await jobsApi.skillGapAnalysis(sessionId);
      setSkillGap(data);
    } catch (err) {
      setError(jobsApi.userMessage(err));
    } finally {
      setLoadingSkillGap(false);
    }
  };

  const reset = () => {
    setSessionId(null);
    setProfile(null);
    setJobs([]);
    setSelectedJob(null);
    setTailored(null);
    setSkillGap(null);
    setError(null);
  };

  return (
    <div className="page-wide jobs-page">
      {!sessionId && (
        <ResumeUpload onSubmit={handleAnalyze} loading={loading} />
      )}

      {loading && (
        <p className="muted" style={{ marginTop: "1rem" }}>
          Reading your resume and finding matching roles. This can take a minute the first time.
        </p>
      )}

      {error && <p className="warning-text">{error}</p>}
      {tailoring && <p className="muted">Preparing a tailored resume from your original file…</p>}

            {sessionId && !tailored && !skillGap && (
        <>
          <div className="review-header">
            <div>
              <h2>Recommended jobs</h2>
              {profile?.name && <p className="muted">Based on {profile.name}'s resume</p>}
            </div>
            <div className="job-card-actions">
              <button type="button" onClick={handleSkillGap} disabled={loadingSkillGap}>
                {loadingSkillGap ? "Analyzing…" : "View Skill Gap Analysis"}
              </button>
              <button type="button" className="subtle" onClick={reset}>Use a different resume</button>
            </div>
          </div>

          {selectedJob ? (
            <JobDetails
              job={selectedJob}
              onClose={() => setSelectedJob(null)}
              onTailor={handleTailor}
            />
          ) : (
            <div className="job-list">
              {jobs.map((job) => (
                <JobCard
                  key={`${job.jobIndex}-${job.rank}`}
                  job={job}
                  onViewDetails={handleViewDetails}
                  onTailor={handleTailor}
                />
              ))}
            </div>
          )}
        </>
      )}

      {skillGap && (
        <SkillGapAnalysis analysis={skillGap} onClose={() => setSkillGap(null)} />
      )}
      {tailored && (
        <TailoredResume
          result={tailored}
          downloadUrl={jobsApi.tailoredDownloadUrl(sessionId, tailored.jobIndex)}
          onClose={() => setTailored(null)}
        />
      )}
    </div>
  );
}
