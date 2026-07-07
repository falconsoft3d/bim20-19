import { ChevronRight } from "lucide-react";

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  hasArrow?: boolean;
  colorVariant?: "default" | "green" | "teal" | "yellow";
}

const variantClasses: Record<string, string> = {
  default: "bg-white",
  green: "bg-green-50 border border-green-100",
  teal: "bg-teal-50 border border-teal-100",
  yellow: "bg-yellow-50 border border-yellow-100",
};

const valueClasses: Record<string, string> = {
  default: "text-gray-900",
  green: "text-green-600",
  teal: "text-teal-600",
  yellow: "text-yellow-600",
};

export default function KpiCard({
  title,
  value,
  subtitle,
  hasArrow = false,
  colorVariant = "default",
}: KpiCardProps) {
  return (
    <div className={`rounded-xl p-5 shadow-sm ${variantClasses[colorVariant]}`}>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{title}</p>
      <div className="flex items-center gap-2">
        <span className={`text-2xl font-bold ${valueClasses[colorVariant]}`}>{value}</span>
        {hasArrow && (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </div>
      {subtitle && (
        <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      )}
    </div>
  );
}
