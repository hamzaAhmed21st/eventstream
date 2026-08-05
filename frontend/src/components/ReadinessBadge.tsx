import type { ReadinessResponse } from "../types/api";

interface ReadinessBadgeProps {
  data: ReadinessResponse | undefined;
  isError: boolean;
  isPending: boolean;
}

export function ReadinessBadge({
  data,
  isError,
  isPending,
}: ReadinessBadgeProps) {
  if (isPending) {
    return (
      <span className="readiness readiness--checking" role="status">
        <span className="readiness__dot" />
        Checking dependencies
      </span>
    );
  }

  if (isError || data === undefined) {
    return (
      <span className="readiness readiness--down" role="status">
        <span className="readiness__dot" />
        Readiness unavailable
      </span>
    );
  }

  const ready = data.status === "ready";
  const details = `Database: ${data.checks.database}; Redis: ${data.checks.redis}`;

  return (
    <span
      className={`readiness ${ready ? "readiness--ready" : "readiness--down"}`}
      role="status"
      title={details}
    >
      <span className="readiness__dot" />
      {ready ? "Dependencies ready" : "Dependencies unavailable"}
    </span>
  );
}
