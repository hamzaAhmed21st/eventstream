import type { MetricName } from "./types/api";

interface MetricDisplay {
  label: string;
  unitSymbol: string;
}

export const METRIC_DISPLAY = {
  latency_ms: { label: "Latency", unitSymbol: "ms" },
  request_count: { label: "Requests", unitSymbol: "" },
  error_count: { label: "Errors", unitSymbol: "" },
  cpu_usage: { label: "CPU", unitSymbol: "%" },
  memory_usage: { label: "Memory", unitSymbol: "%" },
} satisfies Record<MetricName, MetricDisplay>;
