import { Routes, Route, Navigate } from "react-router-dom";

import SessionsPage from "./pages/SessionsPage";
import SessionDetailPage from "./pages/SessionDetailPage";
import WalletPage from "./pages/WalletPage";
import MyGamesPage from "./pages/MyGamesPage";
import AdminPage from "./pages/AdminPage";
// import ProfilePage from "./pages/ProfilePage"; // used as the login screen
import LoginPage from "./pages/LoginPage";
import {
  RequireAuth,
  RequireGuest,
  RequireAdmin,
} from "./components/RouteGuards";

export default function App() {
  return (
    <Routes>
      {/* Default to /login */}
      <Route path="/" element={<Navigate to="/login" replace />} />

      {/* Public (guest-only) */}
      <Route
        path="/login"
        element={
          <RequireGuest>
            <LoginPage />
          </RequireGuest>
        }
      />

      {/* Authenticated app */}
      <Route
        path="/sessions"
        element={
          <RequireAuth>
            <SessionsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/sessions/:id"
        element={
          <RequireAuth>
            <SessionDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/wallet"
        element={
          <RequireAuth>
            <WalletPage />
          </RequireAuth>
        }
      />
      <Route
        path="/my"
        element={
          <RequireAuth>
            <MyGamesPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminPage />
          </RequireAdmin>
        }
      />

      {/* Catch-all → /login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
