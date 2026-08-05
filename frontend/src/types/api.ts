export const METRIC_NAMES = [
  "latency_ms",
  "request_count",
  "error_count",
  "cpu_usage",
  "memory_usage",
] as const;

export type MetricName = (typeof METRIC_NAMES)[number];

export interface ReadinessResponse {
  status: "ready" | "not_ready";
  checks: {
    database: string;
    redis: string;
  };
}

export interface MetricEvent {
  id: number;
  event_id: string;
  service: string;
  metric_name: MetricName;
  value: number;
  timestamp: string;
  tags: Record<string, string>;
  received_at: string;
  processed_at: string;
  schema_version: number;
}

export interface EventsResponse {
  items: MetricEvent[];
  page: number;
  page_size: number;
  total: number;
}

export interface MetricSummaryResponse {
  event_count: number;
  min_value: number | null;
  max_value: number | null;
  average_value: number | null;
  sum_value: number | null;
  most_recent_value: number | null;
  most_recent_timestamp: string | null;
}
