import { useAuthStore } from "../store/authStore";

function HomePage() {
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  return (
    <div>
      <h1>Home Page (Protected)</h1>
      <p>
        Welcome, {user?.name || "User"} ({user?.email})!
      </p>
      <p>This page should only be visible after login.</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

export default HomePage;
