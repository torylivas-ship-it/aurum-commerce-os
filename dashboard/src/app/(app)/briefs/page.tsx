"use client";

import { useEffect, useState } from "react";
import { api, type Brief } from "@/lib/api";

export default function BriefsPage() {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.briefs.latest()
      .then(setBrief)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const generate = async () => {
    setGenerating(true);
    try {
      await api.briefs.generate();
      setTimeout(() => {
        api.briefs.latest().then(setBrief).catch(() => {});
        setGenerating(false);
      }, 5000);
    } catch {
      setGenerating(false);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Daily Executive Brief</h1>
          <p className="text-sm text-gray-400">Generated every morning at 7:00 AM CT</p>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="px-4 py-2 bg-yellow-400/10 border border-yellow-400/30 text-yellow-400 text-sm rounded hover:bg-yellow-400/20 transition-colors disabled:opacity-50"
        >
          {generating ? "Generating..." : "Generate Now"}
        </button>
      </div>

      {loading && <div className="animate-pulse h-96 bg-gray-900 rounded-lg border border-gray-800" />}

      {error && !brief && (
        <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-12 text-center">
          <p className="text-gray-400">No brief generated yet.</p>
          <p className="text-gray-600 text-sm mt-1">Click &quot;Generate Now&quot; to create your first executive brief.</p>
        </div>
      )}

      {brief && (
        <div className="rounded-lg border border-gray-700/50 bg-gray-900/30">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
            <div className="flex items-center gap-3">
              <span className="text-yellow-400 text-lg">◉</span>
              <div>
                <p className="text-white font-medium text-sm">
                  {new Date(brief.date).toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
                </p>
                <p className="text-xs text-gray-500">
                  Confidence: {brief.confidence_score?.toFixed(0)}% ·
                  {brief.products_to_launch.length} to launch ·
                  {brief.products_to_retire.length} to retire
                  {brief.revenue_projection && ` · $${brief.revenue_projection.toLocaleString()} projected`}
                </p>
              </div>
            </div>
          </div>
          <div className="p-5">
            <pre className="whitespace-pre-wrap text-gray-300 text-sm leading-relaxed font-sans">
              {brief.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
