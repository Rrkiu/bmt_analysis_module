import React from "react";
import NavBar from "./NavBar";
import BottomNav from "./BottomNav";

export default function MobileShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="app-container">
      <NavBar />
      <div className="main-content">{children}</div>
      <BottomNav />
      {/* <button
        className="fab"
        onClick={() => window.dispatchEvent(new CustomEvent("open-quick-reg"))}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
        >
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button> */}
    </div>
  );
}
