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
  user: User | null;
  login: (token: string) => void;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

// We use persist middleware to save the token
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,

      login: (token: string) => {
        set({ token: token, user: null }); 
        get().fetchUser();
      },

      logout: () => {
        set({ token: null, user: null });
      },

      fetchUser: async () => {
        const token = get().token;
        if (!token) { 
           if (get().user !== null) {
               set({ user: null });
           }
           return; 
        }
        try {
          const response = await apiClient.get("/auth/me");
          if (response.data) {
            set({ user: response.data });
          } else {
            console.warn("AuthStore: fetchUser - No user data received despite success response.");
            get().logout();
          }
        } catch (error: any) {
          console.error("AuthStore: fetchUser - Failed to fetch user:", error.message);
          get().logout(); 
        }
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ token: state.token }),
      onRehydrateStorage: undefined,
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

// Optional: Trigger hydration check manually if needed outside component context
// This helps ensure the hydration process starts early.
// useAuthStore.getState().setHasHydrated(false); // Reset hydration state on initial script load if needed, though middleware handles it
