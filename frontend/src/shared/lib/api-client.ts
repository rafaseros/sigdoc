import axios from "axios";

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

    // On 401 from non-auth endpoints, clear tokens and redirect to login
    const isAuthEndpoint = error.config?.url?.startsWith("/auth/");
    if (status === 401 && !isAuthEndpoint) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.replace("/login");
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

export { apiClient };
