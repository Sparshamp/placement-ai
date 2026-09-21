const ACCESS_KEY = "auth.accessToken";
const REFRESH_KEY = "auth.refreshToken";
const STUDENT_KEY = "auth.student";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function getStoredStudent() {
  const raw = localStorage.getItem(STUDENT_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSession({ access_token, refresh_token, student }) {
  localStorage.setItem(ACCESS_KEY, access_token);
  localStorage.setItem(REFRESH_KEY, refresh_token);
  localStorage.setItem(STUDENT_KEY, JSON.stringify(student));
}

export function clearSession() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(STUDENT_KEY);
}