import { createTheme } from "@mui/material/styles";

// Define primary and secondary colors
const primaryGreen = "#4CAF50"; // A standard green
const secondaryGreen = "#81C784"; // A lighter green
const healingBlueGreen = "#00897B"; // A teal variant
const lightBackground = "#FFFFFF";
const darkText = "#333333";

// Create the theme instance
const theme = createTheme({
  palette: {
    mode: "light", // Use light mode as base
    primary: {
      main: primaryGreen,
      // contrastText: '#ffffff', // MUI calculates this often
    },
    secondary: {
      main: healingBlueGreen,
      // contrastText: '#ffffff',
    },
    background: {
      default: lightBackground,
      paper: lightBackground, // Background for elements like Card, Paper
    },
    text: {
      primary: darkText,
      secondary: "#555555", // Slightly lighter grey for secondary text
    },
    // Add error, warning, info, success colors if needed
    // error: { main: '#f44336' },
    // warning: { main: '#ff9800' },
  },
  typography: {
    fontFamily: "Nunito, Arial, sans-serif", // Use Nunito font
    h1: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600, // Make Sign in bolder
    },
    // Define other typography variants if needed
  },
  shape: {
    borderRadius: 8, // Slightly rounder corners for components
  },
  components: {
    // Example: Customize Button appearance
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none", // Avoid ALL CAPS buttons
          // Add more default styles if needed
        },
        containedPrimary: {
          // Specific styles for contained primary buttons
        },
      },
    },
    // Customize other components like TextField, AppBar, etc.
    MuiTextField: {
      styleOverrides: {
        root: {
          // Add styles if default look isn't quite right
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 6, // Match theme shape
        },
      },
    },
  },
});

export default theme;
