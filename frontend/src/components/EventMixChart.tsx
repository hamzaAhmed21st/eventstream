import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { METRIC_NAMES, type MetricEvent, type MetricName } from "../types/api";

const METRIC_LABELS: Record<MetricName, string> = {
  latency_ms: "Latency",
  request_count: "Requests",
  error_count: "Errors",
  cpu_usage: "CPU",
  memory_usage: "Memory",
};

interface EventMixChartProps {
  events: MetricEvent[];
}

export function EventMixChart({ events }: EventMixChartProps) {
  const chartData = useMemo(
    () =>
      METRIC_NAMES.map((metricName) => ({
        metric: METRIC_LABELS[metricName],
        events: events.filter((event) => event.metric_name === metricName).length,
      })),
    [events],
  );

  return (
    <section className="panel chart-panel" aria-labelledby="event-mix-title">
      <div className="panel__heading">
        <div>
          <p className="eyebrow">Current page</p>
          <h2 id="event-mix-title">Recent metric mix</h2>
        </div>
        <span className="panel__meta">{events.length} persisted events</span>
      </div>

      {events.length === 0 ? (
        <div className="chart-empty">
          <p>No event mix is available for this filter.</p>
        </div>
      ) : (
        <div
          className="chart"
          role="img"
          aria-label="Bar chart showing the number of recent events for each metric"
        >
          <ResponsiveContainer
            width="100%"
            height="100%"
            initialDimension={{ width: 480, height: 280 }}
          >
            <BarChart data={chartData} margin={{ top: 12, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="#263445" strokeDasharray="3 6" vertical={false} />
              <XAxis
                axisLine={false}
                dataKey="metric"
                tick={{ fill: "#8fa1b5", fontSize: 12 }}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                axisLine={false}
                tick={{ fill: "#73869b", fontSize: 12 }}
                tickLine={false}
                width={36}
              />
              <Tooltip
                cursor={{ fill: "rgba(77, 166, 255, 0.08)" }}
                contentStyle={{
                  background: "#111c28",
                  border: "1px solid #2a3a4c",
                  borderRadius: "10px",
                  color: "#f4f8fc",
                }}
              />
              <Bar
                dataKey="events"
                fill="#4da6ff"
                name="Persisted events"
                radius={[5, 5, 1, 1]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
