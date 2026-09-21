const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";
const PREFIX = "/api/auth";

async function handle(resp) {
  if (resp.ok) return resp.status === 204 ? null : resp.json();
  let detail = resp.statusText;
  try {
    const body = await resp.json();
    detail = body.detail ?? detail;
  } catch { /* not JSON */ }
  const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  err.status = resp.status;
  throw err;
}

export const authApi = {
  signup: (email, password, displayName) =>
    fetch(`${API_BASE}${PREFIX}/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName }),
    }).then(handle),

  login: (email, password) =>
    fetch(`${API_BASE}${PREFIX}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then(handle),

  refresh: (refreshToken) =>
    fetch(`${API_BASE}${PREFIX}/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).then(handle),

  logout: (refreshToken) =>
    fetch(`${API_BASE}${PREFIX}/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).then(handle),

  me: (accessToken) =>
    fetch(`${API_BASE}${PREFIX}/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(handle),
};