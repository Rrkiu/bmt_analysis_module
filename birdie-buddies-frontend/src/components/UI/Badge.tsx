import React from "react";
export default function Badge({
  className = "",
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <span className={`participant-count ${className}`}>{children}</span>;
}
