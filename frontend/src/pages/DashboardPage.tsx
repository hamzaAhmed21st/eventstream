import { type FormEvent, useMemo, useState } from "react";

import {
  useEventsQuery,
  useMetricSummaryQuery,
  useReadinessQuery,
} from "../api/queries";
import { BrandMark } from "../components/BrandMark";
import { EventMixChart } from "../components/EventMixChart";
import { MetricCard, MetricCardSkeleton } from "../components/MetricCard";
import { ReadinessBadge } from "../components/ReadinessBadge";
import { RecentEventsTable } from "../components/RecentEventsTable";
import { METRIC_DISPLAY } from "../metrics";
import type { MetricSummaryResponse } from "../types/api";

const compactNumberFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const decimalNumberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

function summaryAverage(
  summary: MetricSummaryResponse | undefined,
  suffix = "",
): string | null {
  if (summary?.average_value === null || summary?.average_value === undefined) {
    return null;
  }
  return `${decimalNumberFormatter.format(summary.average_value)}${suffix}`;
}

function summarySum(summary: MetricSummaryResponse | undefined): string | null {
  if (summary?.sum_value === null || summary?.sum_value === undefined) {
    return null;
  }
  return compactNumberFormatter.format(summary.sum_value);
}

function observationDetail(
  summary: MetricSummaryResponse | undefined,
  description: string,
): string {
  const count = summary?.event_count;
  if (count === undefined) {
    return `All retained history · ${description}`;
  }
  return (
    `${decimalNumberFormatter.format(count)} observations · ` +
    `all retained history · ${description}`
  );
}

function messageFromError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "The API returned an unexpected error.";
}

export function DashboardPage() {
  const [service, setService] = useState("");
  const [draftService, setDraftService] = useState("");

  const readiness = useReadinessQuery();
  const events = useEventsQuery(service);
  const latency = useMetricSummaryQuery("latency_ms", service);
  const requests = useMetricSummaryQuery("request_count", service);
  const errors = useMetricSummaryQuery("error_count", service);
  const cpu = useMetricSummaryQuery("cpu_usage", service);
  const memory = useMetricSummaryQuery("memory_usage", service);

  const dataQueries = [events, latency, requests, errors, cpu, memory];
  const isInitialLoading = dataQueries.some(
    (query) => query.isPending && query.data === undefined,
  );
  const failedQuery = dataQueries.find((query) => query.isError);

  const serviceSuggestions = useMemo(() => {
    const names = events.data?.items.map((event) => event.service) ?? [];
    if (service !== "") {
      names.push(service);
    }
    return [...new Set(names)].sort((left, right) => left.localeCompare(right));
  }, [events.data?.items, service]);

  const lastUpdatedAt = Math.max(
    events.dataUpdatedAt,
    latency.dataUpdatedAt,
    requests.dataUpdatedAt,
    errors.dataUpdatedAt,
    cpu.dataUpdatedAt,
    memory.dataUpdatedAt,
  );

  function applyServiceFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedService = draftService.trim().toLowerCase();
    setDraftService(normalizedService);
    setService(normalizedService);
  }

  function clearServiceFilter() {
    setDraftService("");
    setService("");
  }

  function refreshDashboard() {
    void Promise.all([
      readiness.refetch(),
      ...dataQueries.map((query) => query.refetch()),
    ]);
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient--one" aria-hidden="true" />
      <div className="ambient ambient--two" aria-hidden="true" />

      <header className="topbar">
        <a className="brand" href="#main-content" aria-label="EventStream dashboard home">
          <BrandMark />
          <span className="brand__name">EventStream</span>
          <span className="brand__env">MVP</span>
        </a>
        <ReadinessBadge
          data={readiness.data}
          isError={readiness.isError}
          isPending={readiness.isPending}
        />
      </header>

      <main id="main-content" className="dashboard">
        <section className="hero" aria-labelledby="dashboard-title">
          <div>
            <p className="eyebrow eyebrow--accent">Metrics operations</p>
            <h1 id="dashboard-title">Pipeline overview</h1>
            <p className="hero__copy">
              Persisted telemetry flowing through Redis Streams into PostgreSQL.
            </p>
          </div>

          <div className="hero__actions">
            <form className="service-filter" onSubmit={applyServiceFilter}>
              <label htmlFor="service-filter">Filter by service</label>
              <div className="service-filter__control">
                <span className="search-icon" aria-hidden="true" />
                <input
                  id="service-filter"
                  list="known-services"
                  onChange={(event) => setDraftService(event.target.value)}
                  placeholder="All services"
                  type="search"
                  value={draftService}
                />
                <datalist id="known-services">
                  {serviceSuggestions.map((name) => (
                    <option value={name} key={name} />
                  ))}
                </datalist>
                <button className="filter-button" type="submit">
                  Apply
                </button>
              </div>
            </form>
            <button
              className="refresh-button"
              type="button"
              onClick={refreshDashboard}
              disabled={dataQueries.some((query) => query.isFetching)}
            >
              <span className="refresh-button__icon" aria-hidden="true">↻</span>
              Refresh
            </button>
          </div>
        </section>

        <div className="scope-row" aria-live="polite">
          <p>
            <strong>All retained history</strong>
            {" · "}
            {service === "" ? (
              <>Showing telemetry across all services</>
            ) : (
              <>
                Service scope: <strong>{service}</strong>
                <button type="button" onClick={clearServiceFilter}>
                  Clear filter
                </button>
              </>
            )}
          </p>
          <p className="polling-note">
            <span aria-hidden="true" />
            Polling every 10 seconds
            {lastUpdatedAt > 0 && ` · Updated ${timeFormatter.format(lastUpdatedAt)}`}
          </p>
        </div>

        {isInitialLoading ? (
          <section aria-busy="true" aria-live="polite">
            <p
              aria-label="Loading dashboard metrics"
              className="sr-only"
              role="status"
            >
              Loading dashboard metrics…
            </p>
            <div className="metrics-grid">
              {Array.from({ length: 6 }, (_, index) => (
                <MetricCardSkeleton key={index} />
              ))}
            </div>
            <div className="content-grid content-grid--loading" aria-hidden="true">
              <div className="panel loading-panel"><span className="skeleton skeleton--panel" /></div>
              <div className="panel loading-panel"><span className="skeleton skeleton--panel" /></div>
            </div>
          </section>
        ) : failedQuery !== undefined ? (
          <section className="error-state" role="alert">
            <span className="error-state__mark" aria-hidden="true">!</span>
            <div>
              <p className="eyebrow">API request failed</p>
              <h2>Dashboard data couldn’t be loaded</h2>
              <p>{messageFromError(failedQuery.error)}</p>
              <button type="button" onClick={refreshDashboard}>Try again</button>
            </div>
          </section>
        ) : (
          <>
            <section className="metrics-grid" aria-label="Metric summaries">
              <MetricCard
                label="Total processed"
                value={
                  events.data === undefined
                    ? null
                    : compactNumberFormatter.format(events.data.total)
                }
                detail="All retained history in scope"
                glyph="Σ"
                tone="blue"
              />
              <MetricCard
                label="All-time average latency"
                value={summaryAverage(
                  latency.data,
                  ` ${METRIC_DISPLAY.latency_ms.unitSymbol}`,
                )}
                detail={observationDetail(latency.data, "mean latency")}
                glyph="↗"
                tone="cyan"
              />
              <MetricCard
                label="All-time request sum"
                value={summarySum(requests.data)}
                detail={observationDetail(requests.data, "summed request_count")}
                glyph="R"
                tone="green"
              />
              <MetricCard
                label="All-time error sum"
                value={summarySum(errors.data)}
                detail={observationDetail(errors.data, "summed error_count")}
                glyph="!"
                tone="rose"
              />
              <MetricCard
                label="All-time average CPU"
                value={summaryAverage(
                  cpu.data,
                  METRIC_DISPLAY.cpu_usage.unitSymbol,
                )}
                detail={observationDetail(cpu.data, "mean cpu_usage value")}
                glyph="C"
                tone="violet"
              />
              <MetricCard
                label="All-time average memory"
                value={summaryAverage(
                  memory.data,
                  METRIC_DISPLAY.memory_usage.unitSymbol,
                )}
                detail={observationDetail(memory.data, "mean memory_usage value")}
                glyph="M"
                tone="amber"
              />
            </section>

            <div className="content-grid">
              <EventMixChart events={events.data?.items ?? []} />
              <RecentEventsTable
                events={events.data?.items ?? []}
                total={events.data?.total ?? 0}
              />
            </div>
          </>
        )}
      </main>

      <footer>
        <p>
          Accepted events are asynchronous. Dashboard values reflect PostgreSQL
          persistence, not stream acceptance.
        </p>
      </footer>
    </div>
  );
}
