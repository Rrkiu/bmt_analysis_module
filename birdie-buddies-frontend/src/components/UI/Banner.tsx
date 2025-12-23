import React, { useEffect } from "react";

export default function Banner({
  kind = "success",
  children,
  onClose,
  timeoutMs = 3000,
}: {
  kind?: "success" | "error" | "info" | "warning";
  children: React.ReactNode;
  onClose?: () => void;
  timeoutMs?: number;
}) {
  useEffect(() => {
    if (!timeoutMs) return;
    const id = setTimeout(() => onClose?.(), timeoutMs);
    return () => clearTimeout(id);
  }, [timeoutMs, onClose]);

  return (
    <div className={`banner banner-${kind} animate-in`}>
      <span className="banner-icon" aria-hidden>
        {kind === "success" ? "✓" : kind === "error" ? "!" : "ℹ︎"}
      </span>
      <span className="banner-text">{children}</span>
      <button className="banner-close" onClick={onClose} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
