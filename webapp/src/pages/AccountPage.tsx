// src/pages/AccountPage.tsx

import React, { useState, useEffect, FormEvent } from "react";
import { useAuthStore } from "../store/authStore";
import apiClient from "../lib/axios";
import {
  Container,
  Typography,
  Box,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Paper,
  Divider,
  Grid,
} from "@mui/material";

function AccountPage() {
  // Select individual state pieces for stability
  const user = useAuthStore((state) => state.user);
  const fetchUser = useAuthStore((state) => state.fetchUser);

  // State for profile update form
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);

  // State for password change form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  // Populate form fields when user data loads or changes
  // Only run when the user object reference changes
  useEffect(() => {
    if (user) {
      // Update local state only if it differs from store state
      if (name !== (user.name || "")) {
        setName(user.name || "");
      }
      if (email !== (user.email || "")) {
        setEmail(user.email || "");
      }
    } 
    // Removed the else block that called fetchUser()
    // Let the store's rehydration logic handle the initial fetch.
  }, [user]); // Only depend on the user object from the store

  const handleProfileSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setProfileLoading(true);
    setProfileError(null);
    setProfileSuccess(null);

    try {
      // Use PUT method and /auth/me endpoint, consistent with password update
      // The backend PUT /auth/me expects a UserUpdate schema, which can include name and email
      const response = await apiClient.put(`/auth/me`, { name, email });
      // Check for successful status codes (200 OK or 204 No Content)
      if (response.status === 200 || response.status === 204) {
         setProfileSuccess("Profile updated successfully!");
         // Re-fetch user data to update the store/UI
         // Ensure fetchUser correctly updates the Zustand store with the potentially new email/name
         fetchUser();
      } else {
          // Throw error if status is unexpected
          throw new Error(response.data?.detail || `Profile update failed with status: ${response.status}`);
      }
    } catch (err: any) {
      console.error("Profile update error:", err);
      setProfileError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to update profile."
      );
    } finally {
      setProfileLoading(false);
    }
  };

  const handlePasswordSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }
    setPasswordLoading(true);
    setPasswordError(null);
    setPasswordSuccess(null);

    try {
      // Update endpoint to PUT /auth/me
      // Send both current and new password for backend validation
      const response = await apiClient.put(`/auth/me`, {
        current_password: currentPassword, // Add current password
        password: newPassword, // This field represents the new password in UserUpdate schema
      });

      // Check for successful status codes (200 OK or 204 No Content often used for updates)
      if (response.status === 200 || response.status === 204) {
        setPasswordSuccess("Password changed successfully!");
        // Clear password fields after success
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
         // Throw error if status is unexpected, potentially using details from response
         throw new Error(response.data?.detail || `Password change failed with status: ${response.status}`);
      }
    } catch (err: any) {
      console.error("Password change error:", err);
      setPasswordError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to change password."
      );
    } finally {
      setPasswordLoading(false);
    }
  };

  if (!user) {
    // Still loading user data or user is not logged in (though protected route should prevent this)
    return (
      <Container>
        <Box sx={{ display: "flex", justifyContent: "center", mt: 5 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Account Management
      </Typography>

      {/* --- Profile Update Section --- */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Update Profile
        </Typography>
        <Box component="form" onSubmit={handleProfileSubmit} noValidate>
          {profileError && <Alert severity="error" sx={{ mb: 2 }}>{profileError}</Alert>}
          {profileSuccess && <Alert severity="success" sx={{ mb: 2 }}>{profileSuccess}</Alert>}
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                margin="normal"
                required
                fullWidth
                id="name"
                label="Full Name"
                name="name"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={profileLoading}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                margin="normal"
                required
                fullWidth
                id="email"
                label="Email Address"
                name="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={profileLoading}
              />
            </Grid>
          </Grid>
          <Button
            type="submit"
            variant="contained"
            sx={{ mt: 3 }}
            disabled={profileLoading}
          >
            {profileLoading ? <CircularProgress size={24} /> : "Update Profile"}
          </Button>
        </Box>
      </Paper>

      <Divider sx={{ mb: 4 }} />

      {/* --- Password Change Section --- */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Change Password
        </Typography>
        <Box component="form" onSubmit={handlePasswordSubmit} noValidate>
           {passwordError && <Alert severity="error" sx={{ mb: 2 }}>{passwordError}</Alert>}
          {passwordSuccess && <Alert severity="success" sx={{ mb: 2 }}>{passwordSuccess}</Alert>}
          <TextField
            margin="normal"
            required
            fullWidth
            name="currentPassword"
            label="Current Password"
            type="password"
            id="currentPassword"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            disabled={passwordLoading}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="newPassword"
            label="New Password"
            type="password"
            id="newPassword"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
             disabled={passwordLoading}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="confirmPassword"
            label="Confirm New Password"
            type="password"
            id="confirmPassword"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={passwordLoading}
            error={newPassword !== confirmPassword && confirmPassword !== ""} // Add error state if passwords don't match
            helperText={
              newPassword !== confirmPassword && confirmPassword !== ""
                ? "Passwords do not match"
                : ""
            }
          />
          <Button
            type="submit"
            variant="contained"
            sx={{ mt: 3 }}
            disabled={passwordLoading || newPassword !== confirmPassword || !newPassword}
          >
            {passwordLoading ? <CircularProgress size={24} /> : "Change Password"}
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}

export default AccountPage;
