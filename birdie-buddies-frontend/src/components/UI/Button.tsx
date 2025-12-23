import React from "react";
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
};
export default function Button({
  variant = "primary",
  className = "",
  ...rest
}: Props) {
  const base =
    "btn " +
    (variant === "primary"
      ? "btn-primary"
      : variant === "secondary"
      ? "btn-secondary"
      : "btn-danger");
  return <button {...rest} className={`${base} ${className}`} />;
}
