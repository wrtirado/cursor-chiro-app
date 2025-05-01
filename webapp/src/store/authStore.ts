import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import apiClient from "../lib/axios"; // Import the axios client

// Define the structure for user data (adjust based on API response)
interface User {
  user_id: number;
  email: string;
  name: string;
  role_id: number;
  office_id?: number;
  join_code?: string;
  // Add role name if available from API?
  // role_name?: string;
}

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  user: User | null;
  login: (token: string) => void;
  logout: () => void;
  fetchUser: () => Promise<void>; // Action to fetch user data
  // setUser: (user: User | null) => void; // Keep internal potentially
}

// We use persist middleware to save the token
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      isAuthenticated: false,
      user: null,

      login: (token: string) => {
        set({ token, isAuthenticated: true });
        // After setting token, fetch user details
        get().fetchUser();
      },

      logout: () => {
        set({ token: null, user: null, isAuthenticated: false });
        // Also remove from storage explicitly if needed, persist might handle it
        // localStorage.removeItem('authToken'); // Handled by persist middleware typically
        // Optionally clear axios header? Persist ensures it's removed on next load
      },

      // Action to fetch user data using the stored token
      fetchUser: async () => {
        const token = get().token;
        if (!token) return; // No token, cannot fetch user

        try {
          // Use the configured apiClient which includes the interceptor
          const response = await apiClient.get("/auth/me");
          if (response.data) {
            set({ user: response.data });
          } else {
            // Handle case where API returns success but no data?
            throw new Error("No user data received");
          }
        } catch (error) {
          console.error("Failed to fetch user:", error);
          // If fetching fails (e.g., token expired), log out
          get().logout();
        }
      },

      // setUser: (user: User | null) => set({ user }), // Can be used internally or exposed if needed
    }),
    {
      name: "auth-storage", // name of the item in storage
      storage: createJSONStorage(() => localStorage), // use localStorage
      partialize: (state) => ({ token: state.token }), // Only persist the token
      // Custom function to run on rehydration (when app loads)
      onRehydrateStorage: (state) => {
        console.log("Hydration finished");
        // Update isAuthenticated based on rehydrated token
        if (state?.token) {
          state.isAuthenticated = true;
          // Fetch user data upon rehydration if token exists
          useAuthStore.getState().fetchUser();
        }
        return (state, error) => {
          if (error) {
            console.log("An error happened during hydration", error);
          } else {
            // state.hasHydrated = true; // Could add a flag if needed
          }
        };
      },
    }
  )
);

// Initialize user fetch if token exists on initial load outside of rehydration (safety net)
// This might run before rehydration completes, fetchUser handles null token.
// const initialToken = (JSON.parse(localStorage.getItem('auth-storage') || '{}')?.state as any)?.token;
// if (initialToken) {
//    useAuthStore.setState({ token: initialToken, isAuthenticated: true });
//    useAuthStore.getState().fetchUser();
// }
