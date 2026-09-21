// src/features/interview-simulation/InterviewPage.jsx
import { useEffect, useRef } from "react";
import { useInterviewSession } from "./hooks/useInterviewSession";
import { speak, stopSpeaking } from "./hooks/useSpeak";
import Header from "./components/Header";
import Hero from "./components/Hero";
import FeatureCard from "./components/FeatureCard";
import SetupForm from "./components/SetupForm";
import AnswerRecorder from "./components/AnswerRecorder";
import FeedbackPanel from "./components/FeedbackPanel";
import FinalReport from "./components/FinalReport";
import "./interview.css";

export default function InterviewPage() {
  const {
    sessionId, intro, prompt, lastFeedback, emotion, done, loading, report,
    start, answer, fetchReport, endInterview,
  } = useInterviewSession();

  const introSpokenRef = useRef(false);

  // Speaks the intro + first question exactly once, right after start()
  useEffect(() => {
    if (sessionId && prompt && !introSpokenRef.current) {
      introSpokenRef.current = true;
      if (intro) {
        speak(intro).then(() => speak(prompt));
      } else {
        speak(prompt);
      }
    }
  }, [sessionId, prompt, intro]);

  useEffect(() => { if (done) fetchReport(); }, [done, fetchReport]);
  useEffect(() => { if (report?.finalReport) speak(report.finalReport); }, [report]);

  // Every subsequent answer: speak feedback (if any) THEN the next thing, in strict order
  const handleSubmitAnswer = async (blob) => {
    const res = await answer(blob);
    if (!res) return;

    if (res.isFollowup) {
      await speak(res.feedback);          // the follow-up question itself
    } else {
      if (res.feedback) await speak(res.feedback);
      if (res.nextQuestion) await speak(res.nextQuestion);
    }
  };

  if (!sessionId) {
    return (
      <div className="landing">
        <Header />
        <Hero />
        <section className="features">
          <FeatureCard
            icon={<TargetIcon />}
            title="Realistic Practice"
            description="Questions generated from your resume and the actual job description."
          />
          <FeatureCard
            icon={<ChartIcon />}
            title="Detailed Feedback"
            description="Spoken, AI-generated feedback after every answer, plus a final summary."
          />
        </section>
        <section className="setup-section">
          <SetupForm loading={loading} onSubmit={start} />
        </section>
      </div>
    );
  }

  if (done && report) return <FinalReport report={report} />;

  const handleEndSession = () => {
    stopSpeaking?.(); // optional — see note below
    endInterview();
  };

  return (
    <div className="interview-page">
      <div className="question-card">
        <p className="eyebrow">Question</p>
        <p>{prompt}</p>
      </div>
      <AnswerRecorder sessionId={sessionId} onSubmitAnswer={handleSubmitAnswer} loading={loading} />
      <FeedbackPanel feedback={lastFeedback} emotion={emotion} />
      <button className="btn-end-session" onClick={handleEndSession}>
        End Session
      </button>
    </div>
  );
}

function TargetIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.3" fill="var(--accent)" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2">
      <path d="M4 20V10M12 20V4M20 20v-7" strokeLinecap="round" />
    </svg>
  );
}