import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { METRIC_DISPLAY } from "../metrics";
import type {
  EventsResponse,
  MetricEvent,
  MetricName,
  MetricSummaryResponse,
  ReadinessResponse,
} from "../types/api";

const readyResponse: ReadinessResponse = {
  status: "ready",
  checks: {
    database: "ok",
    redis: "ok",
  },
};

const recentEvents: MetricEvent[] = [
  {
    id: 42,
    event_id: "3b63522a-af74-4bad-aebb-4b2bca7306a0",
    service: "checkout",
    metric_name: "latency_ms",
    value: 128.4,
    timestamp: "2026-08-05T15:12:00Z",
    tags: { region: "us-central", route: "/checkout" },
    received_at: "2026-08-05T15:12:00.025Z",
    processed_at: "2026-08-05T15:12:00.041Z",
    schema_version: 1,
  },
  {
    id: 41,
    event_id: "0fc97e8f-acf1-43f2-9723-c52efdf0a180",
    service: "payments",
    metric_name: "request_count",
    value: 25,
    timestamp: "2026-08-05T15:11:55Z",
    tags: {},
    received_at: "2026-08-05T15:11:55.019Z",
    processed_at: "2026-08-05T15:11:55.033Z",
    schema_version: 1,
  },
];

const eventsResponse: EventsResponse = {
  items: recentEvents,
  page: 1,
  page_size: 10,
  total: 2481,
};

const summaries: Record<MetricName, MetricSummaryResponse> = {
  latency_ms: {
    event_count: 322,
    min_value: 18.2,
    max_value: 940.8,
    average_value: 128.4,
    sum_value: 41344.8,
    most_recent_value: 128.4,
    most_recent_timestamp: "2026-08-05T15:12:00Z",
  },
  request_count: {
    event_count: 1110,
    min_value: 1,
    max_value: 25,
    average_value: 11.26,
    sum_value: 12500,
    most_recent_value: 25,
    most_recent_timestamp: "2026-08-05T15:11:55Z",
  },
  error_count: {
    event_count: 28,
    min_value: 1,
    max_value: 4,
    average_value: 1.54,
    sum_value: 43,
    most_recent_value: 1,
    most_recent_timestamp: "2026-08-05T15:11:30Z",
  },
  cpu_usage: {
    event_count: 511,
    min_value: 12.5,
    max_value: 91.1,
    average_value: 48.31,
    sum_value: 24686.41,
    most_recent_value: 47.2,
    most_recent_timestamp: "2026-08-05T15:11:40Z",
  },
  memory_usage: {
    event_count: 510,
    min_value: 29.8,
    max_value: 88.4,
    average_value: 67.82,
    sum_value: 34588.2,
    most_recent_value: 68.1,
    most_recent_timestamp: "2026-08-05T15:11:35Z",
  },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function asUrl(input: RequestInfo | URL): URL {
  if (input instanceof Request) {
    return new URL(input.url);
  }
  return new URL(String(input), "http://eventstream.test");
}

type ApiHandler = (url: URL) => Response | Promise<Response>;

function installFetch(handler: ApiHandler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => handler(asUrl(input)));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function installSuccessfulApi(
  eventPayload: EventsResponse = eventsResponse,
) {
  return installFetch((url) => {
    if (url.pathname === "/health/ready") {
      return jsonResponse(readyResponse);
    }
    if (url.pathname === "/api/v1/events") {
      return jsonResponse(eventPayload);
    }
    if (url.pathname === "/api/v1/metrics/summary") {
      const metricName = url.searchParams.get("metric_name") as MetricName;
      return jsonResponse(summaries[metricName]);
    }
    return jsonResponse({ detail: "Not found" }, 404);
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("EventStream dashboard", () => {
  it("shows an accessible loading state while API requests are pending", () => {
    installFetch(() => new Promise<Response>(() => undefined));

    render(<App />);

    expect(
      screen.getByRole("status", { name: "Loading dashboard metrics" }),
    ).toBeInTheDocument();
  });

  it("shows the API error state instead of fallback values", async () => {
    installFetch((url) => {
      if (url.pathname === "/health/ready") {
        return jsonResponse(readyResponse);
      }
      return jsonResponse({ detail: "Metrics query unavailable" }, 500);
    });

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Dashboard data couldn’t be loaded")).toBeInTheDocument();
    expect(within(alert).getByText("Metrics query unavailable")).toBeInTheDocument();
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeEnabled();
  });

  it("renders aggregate cards from metric summary responses", async () => {
    installSuccessfulApi();

    render(<App />);

    expect(await screen.findByText("128.4 ms")).toBeInTheDocument();
    expect(screen.getByText("12.5K")).toBeInTheDocument();
    expect(screen.getByText("43")).toBeInTheDocument();
    expect(screen.getByText("48.31%")).toBeInTheDocument();
    expect(screen.getByText("67.82%")).toBeInTheDocument();
    expect(screen.getByText("All-time average latency")).toBeInTheDocument();
    expect(screen.getByText("All-time request sum")).toBeInTheDocument();
    expect(screen.getByText("All-time error sum")).toBeInTheDocument();
    expect(screen.getByText("All-time average CPU")).toBeInTheDocument();
    expect(screen.getByText("All-time average memory")).toBeInTheDocument();
    expect(
      screen.getByText("All retained history", {
        selector: ".scope-row strong",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("All retained history in scope")).toBeInTheDocument();
    expect(
      screen.getByText(
        "322 observations · all retained history · mean latency",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Dependencies ready")).toBeInTheDocument();
  });

  it("renders an empty event-table state when the event page is empty", async () => {
    installSuccessfulApi({
      items: [],
      page: 1,
      page_size: 10,
      total: 0,
    });

    render(<App />);

    expect(await screen.findByText("No persisted events yet")).toBeInTheDocument();
    expect(screen.getByText("No event mix is available for this filter.")).toBeInTheDocument();
    expect(screen.getByText("Showing 0 of 0")).toBeInTheDocument();
  });

  it("adds the normalized service filter to event and summary requests", async () => {
    const user = userEvent.setup();
    const fetchMock = installSuccessfulApi();

    render(<App />);
    await screen.findByText("checkout");

    const filter = screen.getByRole("combobox", { name: "Filter by service" });
    await user.type(filter, "  PAYments  ");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => {
      const filteredRequests = fetchMock.mock.calls
        .map(([input]) => asUrl(input))
        .filter((url) => url.searchParams.get("service") === "payments");
      expect(filteredRequests).toHaveLength(6);
    });
    expect(filter).toHaveValue("payments");
    expect(screen.getByText("payments", { selector: ".scope-row strong" })).toBeInTheDocument();
  });

  it("renders event fields from the documented API response shape", async () => {
    installSuccessfulApi();

    render(<App />);

    const table = await screen.findByRole("table");
    expect(within(table).getByText("checkout")).toBeInTheDocument();
    expect(
      within(table).getByText(METRIC_DISPLAY.latency_ms.label),
    ).toBeInTheDocument();
    expect(
      within(table).getByText(METRIC_DISPLAY.request_count.label),
    ).toBeInTheDocument();
    expect(within(table).getByText("128.4")).toBeInTheDocument();
    expect(within(table).getByText("region: us-central")).toBeInTheDocument();
    expect(screen.getByText("Showing 2 of 2,481")).toBeInTheDocument();
  });
});
