import { authApi } from "../../shared/auth/authApi";
import * as tokenStorage from "../../shared/auth/tokenStorage";

const DEFAULT_API_BASE = "http://localhost:8001";
const API_PREFIX = "/api/adaptive-aptitude";
const CONNECTION_CHECK_TTL_MS = 5000;

export function getApiBase() {
  return localStorage.getItem("apiBase") || DEFAULT_API_BASE;
}

export function setApiBase(url) {
  localStorage.setItem("apiBase", url.replace(/\/+$/, ""));
}

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders() {
  const token = tokenStorage.getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let refreshPromise = null;

async function withAuthRetry(makeRequest) {
  const resp = await makeRequest();
  if (resp.status !== 401) return resp;

  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) return resp;

  try {
    refreshPromise ??= authApi.refresh(refreshToken).finally(() => { refreshPromise = null; });
    const result = await refreshPromise;
    tokenStorage.setSession(result);
  } catch {
    tokenStorage.clearSession();
    window.location.assign("/login");
    return resp;
  }
  return makeRequest(); // retry once with the new token
}

async function handleResponse(resp) {
  if (resp.ok) return resp.json();
  let detail = resp.statusText;
  try {
    const body = await resp.json();
    detail = body.detail ?? detail;
  } catch { /* not JSON -- keep statusText */ }
  throw new ApiError(resp.status, detail);
}

export async function apiGet(path, params = {}) {
  const url = new URL(getApiBase() + API_PREFIX + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });
  const resp = await withAuthRetry(() => fetch(url, { headers: authHeaders() }));
  return handleResponse(resp);
}

export async function apiPost(path, body) {
  const resp = await withAuthRetry(() =>
    fetch(getApiBase() + API_PREFIX + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    })
  );
  return handleResponse(resp);
}

let cachedConnection = null;

export async function checkConnection() {
  const base = getApiBase();
  const now = Date.now();
  if (cachedConnection && cachedConnection.base === base && now - cachedConnection.at < CONNECTION_CHECK_TTL_MS) {
    return cachedConnection.ok;
  }
  let ok = false;
  try {
    const resp = await fetch(base + API_PREFIX + "/", { signal: AbortSignal.timeout(5000) });
    ok = resp.ok;
  } catch {
    ok = false;
  }
  cachedConnection = { base, at: now, ok };
  return ok;
}

export { ApiError };