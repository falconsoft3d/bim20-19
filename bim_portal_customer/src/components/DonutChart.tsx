"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface DataItem {
  name: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DataItem[];
}

const RADIAN = Math.PI / 180;

export default function DonutChart({ data }: DonutChartProps) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm">
      <p className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-4">
        Distribución CC
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={70}
            outerRadius={110}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Tooltip
            formatter={(value: any) =>
              `${Number(value).toLocaleString("es-ES", { minimumFractionDigits: 2 })} €`
            }
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Legend manual */}
      <div className="mt-2 space-y-1.5">
        {data.map((item) => (
          <div key={item.name} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-gray-600">{item.name}</span>
            </div>
            <span className="text-gray-800 font-medium">
              {item.value.toLocaleString("es-ES", { minimumFractionDigits: 2 })} €
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
