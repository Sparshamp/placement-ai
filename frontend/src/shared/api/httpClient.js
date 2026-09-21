import axios from "axios";
import { authApi } from "../auth/authApi";
import * as tokenStorage from "../auth/tokenStorage";

export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001",
});

httpClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshPromise = null;

httpClient.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const { config, response } = error;
    if (response?.status !== 401 || config._retried) throw error;

    const refreshToken = tokenStorage.getRefreshToken();
    if (!refreshToken) throw error;

    config._retried = true;
    try {
      // Share one in-flight refresh across requests that 401 at the same time.
      refreshPromise ??= authApi.refresh(refreshToken).finally(() => { refreshPromise = null; });
      const result = await refreshPromise;
      tokenStorage.setSession(result);
      config.headers.Authorization = `Bearer ${result.access_token}`;
      return httpClient(config);
    } catch (refreshError) {
      tokenStorage.clearSession();
      window.location.assign("/login");
      throw refreshError;
    }
  }
);