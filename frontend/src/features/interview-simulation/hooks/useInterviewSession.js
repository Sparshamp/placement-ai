// src/features/interview-simulation/hooks/useInterviewSession.js
import { useState, useCallback } from "react";
import { interviewApi } from "../api";

export function useInterviewSession() {
  const [sessionId, setSessionId] = useState(null);
  const [intro, setIntro] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [lastFeedback, setLastFeedback] = useState(null);
  const [emotion, setEmotion] = useState(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  const start = useCallback(async (resumeFile, jobDescription, domain) => {
    setLoading(true);
    const res = await interviewApi.start(resumeFile, jobDescription, domain);
    setSessionId(res.sessionId);
    setIntro(res.intro);
    setPrompt(res.question);
    setLoading(false);
  }, []);

  const answer = useCallback(async (blob) => {
    if (!sessionId) return null;
    setLoading(true);
    const res = await interviewApi.submitAnswer(sessionId, blob);
    setEmotion(res.emotion);

    if (res.isFollowup) {
      setPrompt(res.feedback);
      setLastFeedback(null);
    } else {
      setLastFeedback(res.feedback);
      setPrompt(res.nextQuestion);
      setDone(res.done);
    }
    setLoading(false);
    return res;
  }, [sessionId]);

  const fetchReport = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    const res = await interviewApi.getReport(sessionId);
    setReport(res);
    setLoading(false);
  }, [sessionId]);

  // NEW — ends the session on the backend and resets all local state
  const endInterview = useCallback(async () => {
    if (sessionId) {
      await interviewApi.endSession(sessionId).catch(() => {});
    }
    setSessionId(null);
    setIntro(null);
    setPrompt(null);
    setLastFeedback(null);
    setEmotion(null);
    setDone(false);
    setLoading(false);
    setReport(null);
  }, [sessionId]);

  return {
    sessionId, intro, prompt, lastFeedback, emotion, done, loading, report,
    start, answer, fetchReport, endInterview,
  };
}