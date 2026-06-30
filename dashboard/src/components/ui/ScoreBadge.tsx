"use client";

interface ScoreBadgeProps {
  score: number | null | undefined;
  label?: string;
  size?: "sm" | "md" | "lg";
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-green-400 bg-green-400/10 border-green-400/30";
  if (score >= 70) return "text-lime-400 bg-lime-400/10 border-lime-400/30";
  if (score >= 60) return "text-yellow-400 bg-yellow-400/10 border-yellow-400/30";
  if (score >= 50) return "text-orange-400 bg-orange-400/10 border-orange-400/30";
  return "text-red-400 bg-red-400/10 border-red-400/30";
}

export function ScoreBadge({ score, label, size = "md" }: ScoreBadgeProps) {
  if (score == null) return <span className="text-gray-600 text-xs">—</span>;

  const color = scoreColor(score);
  const sizeClass = size === "sm" ? "text-xs px-1.5 py-0.5" : size === "lg" ? "text-lg px-3 py-1" : "text-sm px-2 py-0.5";

  return (
    <span className={`inline-flex items-center gap-1 rounded border font-mono font-semibold ${color} ${sizeClass}`}>
      {score.toFixed(0)}
      {label && <span className="font-normal opacity-70 text-xs">{label}</span>}
    </span>
  );
}
