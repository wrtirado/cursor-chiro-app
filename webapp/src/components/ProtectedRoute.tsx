import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

const ProtectedRoute: React.FC = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // You might want to add a loading state here while the store is rehydrating
  // const hasHydrated = useAuthStore((state) => state._hasHydrated); // Assuming you add _hasHydrated to store
  // if (!hasHydrated) {
  //   return <div>Loading...</div>; // Or a spinner
  // }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
