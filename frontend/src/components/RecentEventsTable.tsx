import type { MetricEvent, MetricName } from "../types/api";

const METRIC_LABELS: Record<MetricName, string> = {
  latency_ms: "Latency",
  request_count: "Requests",
  error_count: "Errors",
  cpu_usage: "CPU",
  memory_usage: "Memory",
};

const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateFormatter.format(parsed);
}

function renderTags(tags: Record<string, string>) {
  const entries = Object.entries(tags);
  if (entries.length === 0) {
    return <span className="muted-value">—</span>;
  }

  return (
    <span className="tag-list">
      {entries.slice(0, 2).map(([key, value]) => (
        <span className="tag" key={key} title={`${key}: ${value}`}>
          {key}: {value}
        </span>
      ))}
      {entries.length > 2 && (
        <span className="tag tag--more">+{entries.length - 2}</span>
      )}
    </span>
  );
}

interface RecentEventsTableProps {
  events: MetricEvent[];
  total: number;
}

export function RecentEventsTable({ events, total }: RecentEventsTableProps) {
  return (
    <section className="panel events-panel" aria-labelledby="recent-events-title">
      <div className="panel__heading">
        <div>
          <p className="eyebrow">PostgreSQL system of record</p>
          <h2 id="recent-events-title">Recent events</h2>
        </div>
        <span className="panel__meta">
          Showing {events.length} of {numberFormatter.format(total)}
        </span>
      </div>

      {events.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <h3>No persisted events yet</h3>
          <p>
            Send metric events to the ingestion API or clear the active service
            filter.
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Service</th>
                <th scope="col">Metric</th>
                <th scope="col" className="numeric-cell">Value</th>
                <th scope="col">Event time</th>
                <th scope="col">Tags</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.event_id}>
                  <td data-label="Service">
                    <span className="service-name">{event.service}</span>
                  </td>
                  <td data-label="Metric">
                    <span className={`metric-pill metric-pill--${event.metric_name}`}>
                      {METRIC_LABELS[event.metric_name]}
                    </span>
                  </td>
                  <td data-label="Value" className="numeric-cell event-value">
                    {numberFormatter.format(event.value)}
                  </td>
                  <td data-label="Event time">
                    <time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time>
                  </td>
                  <td data-label="Tags">{renderTags(event.tags)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
