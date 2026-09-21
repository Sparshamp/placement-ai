// src/features/interview-simulation/api.js
import { httpClient } from "@shared/api/httpClient";

const BASE = "/api/interview-simulation";

export const interviewApi = {
  start: (resumeFile, jobDescription, domain) => {
    const form = new FormData();
    form.append("resume", resumeFile);
    form.append("job_description", jobDescription);
    form.append("domain", domain);
    return httpClient.post(`${BASE}/sessions`, form).then((r) => r.data);
  },

  submitEmotionFrame: (sessionId, blob) => {
    const form = new FormData();
    form.append("frame", blob, "frame.jpg");
    return httpClient
      .post(`${BASE}/sessions/${sessionId}/emotion-frame`, form)
      .catch(() => {}); // best-effort — a dropped frame shouldn't break the interview
  },

  submitAnswer: (sessionId, audioBlob) => {
    const form = new FormData();
    form.append("audio", audioBlob, "answer.webm");
    return httpClient
      .post(`${BASE}/sessions/${sessionId}/answer`, form)
      .then((r) => r.data);
  },

  getReport: (sessionId) =>
    httpClient.get(`${BASE}/sessions/${sessionId}/report`).then((r) => r.data),

  // Uncomment this to use edge TTS for TTS
  /* synthesizeSpeech: (text) =>
    httpClient
      .post(`${BASE}/tts`, { text }, { responseType: "blob" })
      .then((r) => r.data),
  */

  endSession: (sessionId) => httpClient.delete(`${BASE}/sessions/${sessionId}`),
};