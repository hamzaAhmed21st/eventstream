import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | null;
  detail: string;
  glyph: ReactNode;
  tone: "blue" | "cyan" | "green" | "amber" | "violet" | "rose";
}

export function MetricCard({
  label,
  value,
  detail,
  glyph,
  tone,
}: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__topline">
        <p>{label}</p>
        <span className="metric-card__glyph" aria-hidden="true">
          {glyph}
        </span>
      </div>
      <p className="metric-card__value">
        {value ?? <span aria-label="No matching data">—</span>}
      </p>
      <p className="metric-card__detail">{value === null ? "No matching events" : detail}</p>
    </article>
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="metric-card metric-card--skeleton" aria-hidden="true">
      <span className="skeleton skeleton--label" />
      <span className="skeleton skeleton--value" />
      <span className="skeleton skeleton--detail" />
    </div>
  );
}
