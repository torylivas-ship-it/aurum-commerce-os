"use client";

import { useEffect, useState } from "react";
import { api, type DashboardSummary } from "@/lib/api";
import { StatCard } from "@/components/ui/StatCard";
import { ScoreBadge } from "@/components/ui/ScoreBadge";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard.summary()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));

    const interval = setInterval(() => {
      api.dashboard.summary().then(setData).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <LoadingState />;
  if (error)   return <ErrorState message={error} />;
  if (!data)   return null;

  const { portfolio, pipeline, alerts, top_opportunities, agents, latest_brief } = data;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Executive Dashboard</h1>
          <p className="text-sm text-gray-400">
            {new Date(data.timestamp).toLocaleString("en-US", { timeZone: "America/Chicago" })}
          </p>
        </div>
        <div className="flex gap-2">
          {alerts.critical > 0 && (
            <span className="px-2 py-1 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs font-medium">
              {alerts.critical} CRITICAL
            </span>
          )}
          {alerts.warning > 0 && (
            <span className="px-2 py-1 bg-orange-500/10 border border-orange-500/30 rounded text-orange-400 text-xs font-medium">
              {alerts.warning} WARNING
            </span>
          )}
        </div>
      </div>

      {/* Pipeline Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard title="Discovered"      value={pipeline.discovered}       color="blue"    />
        <StatCard title="Pending Approval" value={pipeline.pending_approval} color="yellow"  />
        <StatCard title="Approved"        value={pipeline.approved}          color="green"   />
        <StatCard title="Launched"        value={pipeline.launched}          color="green"   />
        <StatCard title="Scaling"         value={pipeline.scaling}           color="default" />
      </div>

      {/* Portfolio + Brief */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Total Stores"    value={portfolio.total_stores}  color="default" />
        <StatCard title="Total Products"  value={portfolio.total_products} color="default" />
        {latest_brief ? (
          <StatCard
            title="Latest Brief"
            value={new Date(latest_brief.date).toLocaleDateString()}
            subtitle={`${latest_brief.products_to_launch} to launch · ${latest_brief.confidence_score?.toFixed(0)}% confidence`}
            color="yellow"
          />
        ) : (
          <StatCard title="Latest Brief" value="None yet" color="default" />
        )}
      </div>

      {/* Top Opportunities */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          Top Opportunities
        </h2>
        {top_opportunities.length === 0 ? (
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-6 text-center">
            <p className="text-gray-500 text-sm">No products discovered yet.</p>
            <TriggerDiscoveryButton />
          </div>
        ) : (
          <div className="rounded-lg border border-gray-800 bg-gray-900/30 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                  <th className="text-left px-4 py-2 font-medium">Product</th>
                  <th className="text-left px-4 py-2 font-medium">Category</th>
                  <th className="text-center px-4 py-2 font-medium">Score</th>
                  <th className="text-center px-4 py-2 font-medium">Confidence</th>
                  <th className="text-right px-4 py-2 font-medium">Margin</th>
                  <th className="text-right px-4 py-2 font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {top_opportunities.map((p, i) => (
                  <tr
                    key={p.id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3 text-white font-medium max-w-xs truncate">{p.name}</td>
                    <td className="px-4 py-3 text-gray-400">{p.category || "—"}</td>
                    <td className="px-4 py-3 text-center">
                      <ScoreBadge score={p.opportunity_score} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ScoreBadge score={p.confidence_score} />
                    </td>
                    <td className="px-4 py-3 text-right text-green-400 font-mono">
                      {p.gross_margin ? `${(p.gross_margin * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-white font-mono">
                      {p.selling_price ? `$${p.selling_price.toFixed(2)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Recent Agent Activity */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
          Agent Activity
        </h2>
        <div className="grid gap-2">
          {agents.recent_runs.slice(0, 6).map((run, i) => (
            <div
              key={i}
              className="flex items-center justify-between px-4 py-2 rounded-lg bg-gray-900/40 border border-gray-800/60"
            >
              <div className="flex items-center gap-3">
                <StatusDot status={run.status} />
                <span className="text-sm text-white font-medium">{run.agent_name}</span>
                <span className="text-xs text-gray-500">{run.status}</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                {run.duration_seconds && (
                  <span>{run.duration_seconds.toFixed(1)}s</span>
                )}
                <span>{run.created_at ? new Date(run.created_at).toLocaleTimeString() : ""}</span>
              </div>
            </div>
          ))}
          {agents.recent_runs.length === 0 && (
            <p className="text-gray-600 text-sm text-center py-4">No agent runs yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "success" ? "bg-green-400" :
    status === "running" ? "bg-yellow-400 animate-pulse" :
    status === "failed"  ? "bg-red-400" :
    "bg-gray-500";
  return <span className={`w-2 h-2 rounded-full ${color}`} />;
}

function TriggerDiscoveryButton() {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const trigger = async () => {
    setLoading(true);
    try {
      await api.products.discover();
      setDone(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={trigger}
      disabled={loading || done}
      className="mt-3 px-4 py-2 bg-yellow-400/10 border border-yellow-400/30 text-yellow-400 text-sm rounded hover:bg-yellow-400/20 transition-colors disabled:opacity-50"
    >
      {done ? "Discovery queued!" : loading ? "Queuing..." : "Run Product Discovery"}
    </button>
  );
}

function LoadingState() {
  return (
    <div className="p-6 space-y-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="h-24 bg-gray-900/50 rounded-lg border border-gray-800 animate-pulse" />
      ))}
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="p-6">
      <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6">
        <p className="text-red-400 font-medium">Failed to load dashboard</p>
        <p className="text-red-400/70 text-sm mt-1">{message}</p>
        <p className="text-gray-500 text-xs mt-2">Ensure the API is running at localhost:8000</p>
      </div>
    </div>
  );
}
