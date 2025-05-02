import React, { useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { Box, CircularProgress } from "@mui/material";

const ProtectedRoute: React.FC = () => {
  // Get state and actions from the store
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const fetchUser = useAuthStore((state) => state.fetchUser);

  // Fetch user data on mount if a token exists but user data doesn't
  useEffect(() => {
    if (token && !user) {
      fetchUser();
    }
  }, [token, fetchUser, user]);

  // Determine states based on token and user
  const isAuthenticated = token !== null && user !== null;
  const isLoading = token !== null && user === null;

  // Show loading indicator while fetching user data
  if (isLoading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Once loading is done, navigate or render Outlet
  if (isAuthenticated) {
    return <Outlet />;
  } else {
    return <Navigate to="/login" replace />;
  }
};

export default ProtectedRoute;
