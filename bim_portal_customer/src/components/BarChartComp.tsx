"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface BarChartItem {
  obra: string;
  Materiales: number;
  Asistencias: number;
  "Asist. partner": number;
  Viajes: number;
  "Otros gastos": number;
}

interface BarChartCompProps {
  data: BarChartItem[];
}

const BARS = [
  { key: "Materiales", color: "#4fc3f7" },
  { key: "Asistencias", color: "#66bb6a" },
  { key: "Asist. partner", color: "#ef5350" },
  { key: "Viajes", color: "#ffa726" },
  { key: "Otros gastos", color: "#bdbdbd" },
];

export default function BarChartComp({ data }: BarChartCompProps) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-bold text-gray-700 uppercase tracking-wide">
          CC Origen por Obra
        </p>
        <div className="flex flex-wrap gap-3">
          {BARS.map((b) => (
            <div key={b.key} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: b.color }} />
              <span className="text-xs text-gray-500">{b.key}</span>
            </div>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="obra" tick={{ fontSize: 11, fill: "#9ca3af" }} />
          <YAxis
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
          />
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Tooltip
            formatter={(value: any) =>
              `${Number(value).toLocaleString("es-ES", { minimumFractionDigits: 2 })} €`
            }
          />
          {BARS.map((b) => (
            <Bar key={b.key} dataKey={b.key} fill={b.color} radius={[2, 2, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
