import { httpClient } from "@shared/api/httpClient";

const BASE = "/api/job-recommendation";

function userMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (error?.code === "ERR_NETWORK" || !error?.response) {
    return "We can't reach the server right now. Please make sure it's running, then try again.";
  }
  return "Something went wrong. Please try again.";
}

export const jobsApi = {
  recommend: (resumeFile, topK = 12) => {
    const form = new FormData();
    form.append("resume", resumeFile);
    return httpClient
      .post(`${BASE}/sessions`, form, {
        params: { top_k: topK },
        timeout: 300000,
      })
      .then((r) => r.data);
  },

  getSession: (sessionId) =>
    httpClient.get(`${BASE}/sessions/${sessionId}`).then((r) => r.data),

  getJob: (sessionId, jobIndex) =>
    httpClient
      .get(`${BASE}/sessions/${sessionId}/jobs/${jobIndex}`)
      .then((r) => r.data),
    skillGapAnalysis: (sessionId, topN = 5) =>
    httpClient
      .get(`${BASE}/sessions/${sessionId}/skill-gap-analysis`, {
        params: { top_n: topN },
        timeout: 60000,
      })
      .then((r) => r.data),
  tailorResume: (sessionId, jobIndex) =>
    httpClient
      .post(`${BASE}/sessions/${sessionId}/jobs/${jobIndex}/tailored-resume`, null, {
        timeout: 180000,
      })
      .then((r) => r.data),

  tailoredDownloadUrl: (sessionId, jobIndex) => {
    const base = httpClient.defaults.baseURL || "";
    return `${base}${BASE}/sessions/${sessionId}/jobs/${jobIndex}/tailored-resume.docx`;
  },

  userMessage,
};
