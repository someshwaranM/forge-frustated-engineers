import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { cn } from "../../lib/utils";

interface TrendChartProps {
  type?: "bar" | "line";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  xKey: string;
  series: {
    key: string;
    label: string;
    color: string;
  }[];
  height?: number;
  className?: string;
  truncateXLength?: number;
  interval?: number | "preserveStart" | "preserveEnd" | "preserveStartEnd";
  xTickFormatter?: (value: any) => string;
}

export const TrendChart: React.FC<TrendChartProps> = ({
  type = "bar",
  data,
  xKey,
  series,
  height = 240,
  className,
  truncateXLength,
  interval,
  xTickFormatter,
}) => {
  const isDark = document.documentElement.classList.contains("dark");
  const gridColor = isDark ? "#334155" : "#e2e8f0";
  const axisTextColor = isDark ? "#94a3b8" : "#64748b";

  const formatTick = (val: any) => {
    if (xTickFormatter) return xTickFormatter(val);
    if (truncateXLength !== undefined && typeof val === "string" && val.length > truncateXLength) {
      return `${val.substring(0, truncateXLength)}...`;
    }
    return String(val ?? "");
  };

  const tooltipLabelFormatter = (label: any, payload: any) => {
    if (payload && payload.length > 0 && payload[0]?.payload) {
      return payload[0].payload[xKey] || label;
    }
    return label;
  };

  return (
    <div className={cn("w-full", className)}>
      <ResponsiveContainer width="100%" height={height}>
        {type === "bar" ? (
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
            <XAxis
              dataKey={xKey}
              stroke={axisTextColor}
              fontSize={11}
              tickLine={false}
              axisLine={false}
              interval={interval}
              tickFormatter={truncateXLength !== undefined || xTickFormatter ? formatTick : undefined}
            />
            <YAxis
              stroke={axisTextColor}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip
              labelFormatter={tooltipLabelFormatter}
              contentStyle={{
                backgroundColor: isDark ? "#0f172a" : "#ffffff",
                borderColor: isDark ? "#334155" : "#e2e8f0",
                borderRadius: "6px",
                fontSize: "12px",
                color: isDark ? "#f8fafc" : "#0f172a",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
            />
            {series.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.label}
                fill={s.color}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        ) : (
          <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
            <XAxis
              dataKey={xKey}
              stroke={axisTextColor}
              fontSize={11}
              tickLine={false}
              axisLine={false}
              interval={interval}
              tickFormatter={truncateXLength !== undefined || xTickFormatter ? formatTick : undefined}
            />
            <YAxis
              stroke={axisTextColor}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip
              labelFormatter={tooltipLabelFormatter}
              contentStyle={{
                backgroundColor: isDark ? "#0f172a" : "#ffffff",
                borderColor: isDark ? "#334155" : "#e2e8f0",
                borderRadius: "6px",
                fontSize: "12px",
                color: isDark ? "#f8fafc" : "#0f172a",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
            />
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={{ r: 3, fill: s.color }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
};
