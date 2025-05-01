import { Routes, Route } from "react-router-dom";
import "./App.css";
import LoginPage from "./pages/LoginPage";
import ProtectedRoute from "./components/ProtectedRoute";
import AppLayout from "./components/AppLayout";

// Import page components
import HomePage from "./pages/HomePage";
import AccountPage from "./pages/AccountPage";
import TherapyPlanCreatePage from "./pages/TherapyPlanCreatePage";
import NotFoundPage from "./pages/NotFoundPage";

function App() {
  return (
    <Routes>
      {/* Public Route */}
      <Route path="/login" element={<LoginPage />} />

      {/* Wrap the layout in ProtectedRoute */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {" "}
          {/* AppLayout now contains the Outlet */}
          {/* Routes rendered within the AppLayout */}
          <Route path="/" element={<HomePage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/plans/create" element={<TherapyPlanCreatePage />} />
          {/* Add other protected routes here */}
        </Route>
      </Route>

      {/* Catch-all for 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default App;
