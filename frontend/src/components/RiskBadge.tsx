/** Color-coded risk score badge. Red >70, Orange >40, Green <=40. */

import { clsx } from "clsx";

interface RiskBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

export function RiskBadge({ score, size = "md" }: RiskBadgeProps) {
  const color =
    score > 70
      ? "bg-red-100 text-red-800 border-red-200"
      : score > 40
        ? "bg-orange-100 text-orange-800 border-orange-200"
        : "bg-green-100 text-green-800 border-green-200";

  const sizeClasses = {
    sm: "text-xs px-1.5 py-0.5",
    md: "text-sm px-2 py-0.5",
    lg: "text-base px-3 py-1",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center font-semibold rounded-full border",
        color,
        sizeClasses[size]
      )}
    >
      {score}
    </span>
  );
}
