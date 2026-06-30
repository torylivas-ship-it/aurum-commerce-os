"use client";

import { useEffect, useState } from "react";
import { api, type AgentRun } from "@/lib/api";

const AGENTS = [
  { name: "product_discovery",  label: "Product Discovery",  desc: "Scans 4+ platforms for trending products" },
  { name: "executive_advisor",  label: "Executive Advisor",  desc: "Generates daily business brief" },
  { name: "risk_intelligence",  label: "Risk Intelligence",  desc: "Monitors for business risks" },
  { name: "trend_intelligence", label: "Trend Intelligence", desc: "Tracks trend signals across platforms" },
  { name: "competitor_intel",   label: "Competitor Intel",   desc: "Monitors competitor activity" },
];

export default function AgentsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);

  useEffect(() => {
    api.agents.runs().then(setRuns).finally(() => setLoading(false));
    const interval = setInterval(() => {
      api.agents.runs().then(setRuns).catch(() => {});
    }, 15_000);
    return () => clearInterval(interval);
  }, []);

  const trigger = async (name: string) => {
    setTriggering(name);
    try { await api.agents.trigger(name); }
    finally { setTriggering(null); }
  };

  const lastRunFor = (name: string) => runs.find(r => r.agent_name === name);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Agent Control Panel</h1>
        <p className="text-sm text-gray-400">Trigger agents manually or monitor scheduled runs</p>
      </div>

      {/* Agent cards */}
      <div className="grid gap-3">
        {AGENTS.map(agent => {
          const last = lastRunFor(agent.name);
          return (
            <div key={agent.name} className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <StatusDot status={last?.status || "idle"} />
                <div>
                  <p className="text-white font-medium">{agent.label}</p>
                  <p className="text-gray-500 text-xs">{agent.desc}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {last && (
                  <div className="text-right text-xs text-gray-500">
                    <p>{last.status} · {last.duration_seconds?.toFixed(1)}s</p>
                    <p>{new Date(last.created_at).toLocaleTimeString()}</p>
                  </div>
                )}
                <button
                  onClick={() => trigger(agent.name)}
                  disabled={triggering === agent.name}
                  className="px-3 py-1.5 bg-yellow-400/10 border border-yellow-400/30 text-yellow-400 text-xs rounded hover:bg-yellow-400/20 transition-colors disabled:opacity-50 whitespace-nowrap"
                >
                  {triggering === agent.name ? "Queued" : "Run Now"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent run log */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Recent Run Log</h2>
        {loading ? (
          <div className="animate-pulse h-32 bg-gray-900 rounded-lg border border-gray-800" />
        ) : (
          <div className="rounded-lg border border-gray-800 bg-gray-900/20 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
                  <th className="text-left px-4 py-2 font-medium">Agent</th>
                  <th className="text-left px-4 py-2 font-medium">Status</th>
                  <th className="text-right px-4 py-2 font-medium">Duration</th>
                  <th className="text-right px-4 py-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.map(run => (
                  <tr key={run.id} className="border-b border-gray-800/40">
                    <td className="px-4 py-2.5 text-white">{run.agent_name}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs ${
                        run.status === "success" ? "text-green-400" :
                        run.status === "running" ? "text-yellow-400" :
                        run.status === "failed"  ? "text-red-400" : "text-gray-400"
                      }`}>{run.status}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-400 font-mono text-xs">
                      {run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-500 text-xs">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-600">
                      No agent runs yet. Trigger an agent to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const cls =
    status === "success" ? "bg-green-400" :
    status === "running" ? "bg-yellow-400 animate-pulse" :
    status === "failed"  ? "bg-red-400" :
    "bg-gray-600";
  return <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${cls}`} />;
}
