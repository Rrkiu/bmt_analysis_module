import React from "react";
export default function Card({
  className = "",
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...rest} className={`session-card animate-in ${className}`}>
      {children}
    </div>
  );
}
