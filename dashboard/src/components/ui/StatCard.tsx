"use client";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: "default" | "green" | "yellow" | "red" | "blue";
  icon?: React.ReactNode;
}

const colorMap = {
  default: "border-gray-700/50 bg-gray-900/50",
  green:   "border-green-500/30 bg-green-500/5",
  yellow:  "border-yellow-500/30 bg-yellow-500/5",
  red:     "border-red-500/30 bg-red-500/5",
  blue:    "border-blue-500/30 bg-blue-500/5",
};

const valueColorMap = {
  default: "text-white",
  green:   "text-green-400",
  yellow:  "text-yellow-400",
  red:     "text-red-400",
  blue:    "text-blue-400",
};

export function StatCard({ title, value, subtitle, color = "default", icon }: StatCardProps) {
  return (
    <div className={`rounded-lg border p-4 ${colorMap[color]}`}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-gray-400 uppercase tracking-wider">{title}</p>
        {icon && <span className="text-gray-500">{icon}</span>}
      </div>
      <p className={`text-2xl font-bold font-mono ${valueColorMap[color]}`}>{value}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </div>
  );
}
