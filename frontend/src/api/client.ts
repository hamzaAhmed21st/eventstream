import type {
  EventsResponse,
  MetricName,
  MetricSummaryResponse,
  ReadinessResponse,
} from "../types/api";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? "";
const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");

interface RequestOptions {
  signal?: AbortSignal | undefined;
  acceptedErrorStatuses?: readonly number[];
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function createPath(
  path: string,
  params: Record<string, string | number | undefined> = {},
): string {
  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }

  const query = search.toString();
  return `${API_BASE_URL}${path}${query === "" ? "" : `?${query}`}`;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json();
    if (
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      return payload.detail;
    }
  } catch {
    // The status code remains the useful error if the response has no JSON body.
  }

  return `Request failed with status ${response.status}`;
}

async function requestJson<T>(
  path: string,
  params: Record<string, string | number | undefined>,
  options: RequestOptions = {},
): Promise<T> {
  const requestOptions: RequestInit = {
    method: "GET",
    headers: { Accept: "application/json" },
  };
  if (options.signal !== undefined) {
    requestOptions.signal = options.signal;
  }

  const response = await fetch(createPath(path, params), requestOptions);

  const acceptedError = options.acceptedErrorStatuses?.includes(response.status);
  if (!response.ok && !acceptedError) {
    throw new ApiError(await parseErrorMessage(response), response.status);
  }

  return (await response.json()) as T;
}

export function getReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return requestJson<ReadinessResponse>(
    "/health/ready",
    {},
    { signal, acceptedErrorStatuses: [503] },
  );
}

interface EventsParameters {
  page?: number;
  pageSize?: number;
  service?: string | undefined;
  signal?: AbortSignal | undefined;
}

export function getEvents({
  page = 1,
  pageSize = 10,
  service,
  signal,
}: EventsParameters = {}): Promise<EventsResponse> {
  return requestJson<EventsResponse>(
    "/api/v1/events",
    {
      page,
      page_size: pageSize,
      service,
    },
    { signal },
  );
}

interface SummaryParameters {
  metricName: MetricName;
  service?: string | undefined;
  signal?: AbortSignal | undefined;
}

export function getMetricSummary({
  metricName,
  service,
  signal,
}: SummaryParameters): Promise<MetricSummaryResponse> {
  return requestJson<MetricSummaryResponse>(
    "/api/v1/metrics/summary",
    {
      metric_name: metricName,
      service,
    },
    { signal },
  );
}
