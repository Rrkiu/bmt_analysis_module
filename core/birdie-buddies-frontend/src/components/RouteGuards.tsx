import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

// --- Route guards (inline for convenience) ---
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
export function RequireGuest({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/sessions" replace />;
  return children;
}
export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) return <Navigate to="/sessions" replace />;
  return children;
}
