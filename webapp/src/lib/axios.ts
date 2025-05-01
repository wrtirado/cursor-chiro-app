// src/lib/axios.ts
import axios from "axios";
import { useAuthStore } from "../store/authStore"; // Import the auth store

// Get API base URL from environment variables (Vite specific)
// Create a .env file in the webapp directory: VITE_API_BASE_URL=http://localhost:8000/api/v1
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add request interceptor to include the token
apiClient.interceptors.request.use(
  (config) => {
    // Get token directly from the store state
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling (e.g., 401 for logout)
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response && error.response.status === 401) {
      // Handle unauthorized access - trigger logout action from auth store
      console.error("Unauthorized access - 401. Logging out.");
      // Check if logout is already being processed to avoid loops
      if (useAuthStore.getState().isAuthenticated) {
        useAuthStore.getState().logout();
        // No need for manual redirect here as components reacting to
        // isAuthenticated changing should handle the redirect.
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
