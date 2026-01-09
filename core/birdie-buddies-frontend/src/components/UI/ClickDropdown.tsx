import React from "react";
import { createPortal } from "react-dom";

export type Option = { label: string; value: string };

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

export default function ClickDropdown({
  value,
  valueLabel,
  placeholder = "Select…",
  options,
  onSelect,
  className = "",
  widthPx = 300, // assumed panel width for positioning math
  visibleCount = 4,
}: {
  value?: string;
  valueLabel?: string; // shown in the input; pass if you already have it
  placeholder?: string;
  options: Option[];
  onSelect: (val: string) => void;
  className?: string;
  widthPx?: number;
  visibleCount?: number;
}) {
  const [open, setOpen] = React.useState(false);
  const [pt, setPt] = React.useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const inputRef = React.useRef<HTMLButtonElement | null>(null);

  const label =
    valueLabel ??
    options.find((o) => o.value === value)?.label ??
    (value ? value : "");

  const onTriggerClick = (e: React.MouseEvent) => {
    // Where the user clicked (viewport coords)
    const x = (e as React.MouseEvent).clientX;
    const y = (e as React.MouseEvent).clientY;
    // Keep panel within the viewport horizontally
    const left = clamp(x, 8, window.innerWidth - widthPx - 8);
    const top = clamp(y + 8, 8, window.innerHeight - 8);
    setPt({ x: left, y: top });
    setOpen(true);
  };

  // Close on outside click / ESC
  React.useEffect(() => {
    if (!open) return;
    const onDown = (ev: MouseEvent) => {
      const target = ev.target as Node;
      if (inputRef.current && inputRef.current.contains(target)) return;
      const panel = document.getElementById("click-dd-panel");
      if (panel && panel.contains(target)) return;
      setOpen(false);
    };
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Simple portal target (body)
  const portal = (node: React.ReactNode) => createPortal(node, document.body);

  return (
    <>
      <button
        type="button"
        ref={inputRef}
        className={`form-input click-input ${className}`}
        onClick={onTriggerClick}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className={`click-input-text ${label ? "" : "placeholder"}`}>
          {label || placeholder}
        </span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          aria-hidden
          style={{ opacity: 0.8 }}
        >
          <path fill="currentColor" d="M7 10l5 5 5-5z" />
        </svg>
      </button>

      {open &&
        portal(
          <div
            id="click-dd-panel"
            className="click-dd-panel animate-in"
            role="listbox"
            style={{
              position: "fixed",
              top: pt.y,
              left: pt.x,
              maxWidth: "92vw",
              width: `${widthPx}px`,
              zIndex: 1000,
            }}
          >
            <div
              className="click-dd-list"
              style={
                {
                  ["--dd-visible-count" as any]: visibleCount,
                } as React.CSSProperties
              }
            >
              {options.map((opt) => {
                const active = opt.value === value;
                return (
                  <button
                    type="button"
                    key={opt.value}
                    role="option"
                    aria-selected={active}
                    className={`click-dd-item ${active ? "active" : ""}`}
                    onClick={() => {
                      onSelect(opt.value);
                      setOpen(false);
                      // restore focus to trigger
                      setTimeout(() => inputRef.current?.focus(), 0);
                    }}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
    </>
  );
}
