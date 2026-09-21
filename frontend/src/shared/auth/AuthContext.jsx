import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi } from "./authApi";
import * as tokenStorage from "./tokenStorage";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [student, setStudent] = useState(tokenStorage.getStoredStudent());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const accessToken = tokenStorage.getAccessToken();
    if (!accessToken) {
      setLoading(false);
      return;
    }
    // Confirm the stored token is still valid rather than trusting
    // whatever's cached in localStorage from a previous visit.
    authApi.me(accessToken)
      .then(setStudent)
      .catch(() => {
        tokenStorage.clearSession();
        setStudent(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const result = await authApi.login(email, password);
    tokenStorage.setSession(result);
    setStudent(result.student);
    return result.student;
  }, []);

  const signup = useCallback(async (email, password, displayName) => {
    const result = await authApi.signup(email, password, displayName);
    tokenStorage.setSession(result);
    setStudent(result.student);
    return result.student;
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = tokenStorage.getRefreshToken();
    if (refreshToken) await authApi.logout(refreshToken).catch(() => {}); // best-effort revoke
    tokenStorage.clearSession();
    setStudent(null);
  }, []);

  return (
    <AuthContext.Provider value={{ student, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}