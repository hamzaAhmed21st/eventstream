import { useQuery } from "@tanstack/react-query";

import { getEvents, getMetricSummary, getReadiness } from "./client";
import type { MetricName } from "../types/api";

const DASHBOARD_POLL_INTERVAL_MS = 10_000;

export function useReadinessQuery() {
  return useQuery({
    queryKey: ["readiness"],
    queryFn: ({ signal }) => getReadiness(signal),
    refetchInterval: DASHBOARD_POLL_INTERVAL_MS,
  });
}

export function useEventsQuery(service: string) {
  return useQuery({
    queryKey: ["events", { page: 1, pageSize: 10, service }],
    queryFn: ({ signal }) =>
      getEvents({
        page: 1,
        pageSize: 10,
        service: service === "" ? undefined : service,
        signal,
      }),
    refetchInterval: DASHBOARD_POLL_INTERVAL_MS,
  });
}

export function useMetricSummaryQuery(
  metricName: MetricName,
  service: string,
) {
  return useQuery({
    queryKey: ["metric-summary", metricName, { service }],
    queryFn: ({ signal }) =>
      getMetricSummary({
        metricName,
        service: service === "" ? undefined : service,
        signal,
      }),
    refetchInterval: DASHBOARD_POLL_INTERVAL_MS,
  });
}
