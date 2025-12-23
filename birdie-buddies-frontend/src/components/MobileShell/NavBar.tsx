import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../lib/auth";
import { getMyWallet, formatDollarsFromCents } from "../../lib/api"; // Import the utility

export default function NavBar() {
  const { user, signOut } = useAuth();
  const loc = useLocation();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  // Hide the whole top bar on the login screen
  if (loc.pathname === "/login") return null;

  // Fetch wallet summary for the signed-in user
  const wallet = useQuery({
    queryKey: ["wallet", user?.id], // <-- match the key you invalidate
    queryFn: getMyWallet,
    enabled: !!user,
  });
  //   const w = useQuery({ queryKey: ["wallet/me"], queryFn: getMyWallet });

  //   const dollars = (cents?: number) => Number(cents ?? 0).toFixed(2);

  const onSignOut = async () => {
    try {
      await signOut();
    } finally {
      nav("/login", { replace: true });
    }
  };

  return (
    <nav className="nav-container">
      <div className="nav-content">
        <div
          className="nav-brand"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
          }}
          onClick={() => nav("/sessions")}
        >
          <img src="/birdie2.svg" alt="BirdieBuddies" width={34} height={34} />
          <span>BirdieBuddies</span>
        </div>

        <div className="user-menu" style={{ position: "relative" }}>
          {/* Wallet badge shows available balance */}
          <div
            className="wallet-badge"
            title="Available balance - Click to view wallet"
            onClick={() => nav("/wallet")}
            style={{ cursor: "pointer" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 18v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v1h-9a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h9zm-9-2h10V8H12v8zm4-2.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z" />
            </svg>

            {wallet.isLoading
              ? "$…"
              : formatDollarsFromCents(wallet.data?.available_cents)}
          </div>

          {/* Avatar + menu */}
          <button
            className="user-avatar"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            {user?.name?.slice(1, 3).toUpperCase() ?? "??"}
          </button>

          {open && (
            <div className="user-info">
              <div style={{ padding: "8px 10px", opacity: 0.9 }}>
                <div style={{ fontWeight: 600 }}>{user?.name}</div>
                <div style={{ fontSize: 12 }}>{user?.email}</div>
              </div>
              <button
                onClick={onSignOut}
                className="action-btn danger"
                style={{ width: "100%", textAlign: "left" }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  style={{ marginRight: 6, verticalAlign: -2 }}
                >
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
