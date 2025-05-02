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
    // Check if it's a 401 error
    if (error.response && error.response.status === 401) {
      // Check if the error came from the password update request
      const originalRequest = error.config;
      const isPasswordUpdateAttempt = 
        originalRequest.method === 'put' && 
        originalRequest.url === '/auth/me' && // Use relative path as configured in apiClient
        originalRequest.data && 
        JSON.parse(originalRequest.data).password; // Check if password field was being sent

      // Only trigger automatic logout for 401s that are NOT failed password updates
      if (!isPasswordUpdateAttempt) {
        console.error("Unauthorized access (401) detected. Logging out.", originalRequest.url);
        // Check if logout is already being processed to avoid loops
        if (useAuthStore.getState().isAuthenticated) {
          useAuthStore.getState().logout();
          // No need for manual redirect here as components reacting to
          // isAuthenticated changing should handle the redirect.
        }
      } else {
        // Log that we caught a 401 from password update but didn't auto-logout
        console.warn("Caught 401 from password update. Letting component handle error display.");
      }
    }
    // Always reject the promise so the component's catch block can handle the error
    return Promise.reject(error);
  }
);

export default apiClient;
