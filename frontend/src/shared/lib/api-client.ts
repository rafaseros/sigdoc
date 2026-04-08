import axios from "axios";
import { QUOTA_EXCEEDED_EVENT } from "@/features/subscription/components/QuotaExceededDialog";

const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const body = error.response?.data;

    // On 401 from non-auth endpoints, clear tokens and redirect to login
    const isAuthEndpoint = error.config?.url?.startsWith("/auth/");
    if (status === 401 && !isAuthEndpoint) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.replace("/login");
      return Promise.reject(error);
    }

    // On 429 with error="quota_exceeded", show the QuotaExceededDialog
    // Regular rate-limit 429s (no error field or different error) pass through silently
    if (status === 429 && body?.error === "quota_exceeded") {
      window.dispatchEvent(
        new CustomEvent(QUOTA_EXCEEDED_EVENT, { detail: body })
      );
    }

    return Promise.reject(error);
  }
);

export { apiClient };
