"use client";

import { useEffect, useState } from "react";
import { api, type Approval } from "@/lib/api";
import { ScoreBadge } from "@/components/ui/ScoreBadge";

type LaunchResult = { launched: boolean; shopify_admin_url?: string; store?: string; reason?: string };

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [launched, setLaunched] = useState<Record<string, LaunchResult>>({});

  const load = () => {
    api.approvals.list("pending").then(setApprovals).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const decide = async (id: string, decision: "approve" | "reject") => {
    setDeciding(id);
    try {
      const result = await api.approvals.decide(id, decision) as { launch?: LaunchResult };
      if (decision === "approve" && result?.launch) {
        setLaunched(prev => ({ ...prev, [id]: result.launch! }));
        setTimeout(() => setApprovals(prev => prev.filter(a => a.id !== id)), 3000);
      } else {
        setApprovals(prev => prev.filter(a => a.id !== id));
      }
    } finally {
      setDeciding(null);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Pending Approvals</h1>
          <p className="text-sm text-gray-400">Human-in-the-loop gate — no action executes without your approval</p>
        </div>
        <span className="px-3 py-1 bg-yellow-400/10 border border-yellow-400/30 rounded text-yellow-400 text-sm font-medium">
          {approvals.length} pending
        </span>
      </div>

      {loading && <div className="animate-pulse h-32 bg-gray-900 rounded-lg border border-gray-800" />}

      {!loading && approvals.length === 0 && (
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-12 text-center">
          <p className="text-green-400 font-medium">All caught up!</p>
          <p className="text-gray-500 text-sm mt-1">No pending approvals.</p>
        </div>
      )}

      {approvals.map(approval => {
        const data = approval.data as Record<string, number> || {};
        return (
          <div key={approval.id} className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-5 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wider">{approval.request_type}</span>
                <h3 className="text-white font-semibold mt-0.5">{approval.title}</h3>
              </div>
              <div className="flex gap-2 flex-shrink-0">
                <ScoreBadge score={approval.confidence_score} label="conf" />
              </div>
            </div>

            {approval.description && (
              <p className="text-gray-400 text-sm leading-relaxed">{approval.description}</p>
            )}

            {/* Financials */}
            {data.gross_margin && (
              <div className="grid grid-cols-4 gap-3 p-3 bg-gray-800/40 rounded-lg">
                <Metric label="Opportunity Score" value={`${data.opportunity_score?.toFixed(0)}/100`} highlight />
                <Metric label="Gross Margin" value={`${((data.gross_margin || 0) * 100).toFixed(1)}%`} highlight />
                <Metric label="Selling Price" value={`$${data.selling_price?.toFixed(2)}`} />
                <Metric label="Profit/Unit" value={`$${data.profit_per_unit?.toFixed(2)}`} highlight />
              </div>
            )}

            {approval.impact && (
              <p className="text-xs text-gray-500">Impact: {approval.impact}</p>
            )}

            {approval.risk_assessment && (
              <p className="text-xs text-orange-400/70">Risk: {approval.risk_assessment}</p>
            )}

            {launched[approval.id] && (
              <div className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded ${
                launched[approval.id].launched
                  ? "bg-green-500/10 border border-green-500/30 text-green-400"
                  : "bg-orange-500/10 border border-orange-500/30 text-orange-400"
              }`}>
                {launched[approval.id].launched ? (
                  <>
                    ✓ Launched to Shopify ({launched[approval.id].store})
                    {launched[approval.id].shopify_admin_url && (
                      <a href={launched[approval.id].shopify_admin_url} target="_blank" rel="noreferrer"
                        className="underline ml-1">View →</a>
                    )}
                  </>
                ) : (
                  <>Approved · {launched[approval.id].reason === "store_not_connected"
                    ? "Connect a store to auto-launch"
                    : launched[approval.id].reason}</>
                )}
              </div>
            )}

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={() => decide(approval.id, "approve")}
                disabled={deciding === approval.id || !!launched[approval.id]}
                className="px-4 py-1.5 bg-green-500/10 border border-green-500/30 text-green-400 text-sm rounded hover:bg-green-500/20 transition-colors disabled:opacity-50"
              >
                {deciding === approval.id ? "Launching…" : "Approve & Launch"}
              </button>
              <button
                onClick={() => decide(approval.id, "reject")}
                disabled={deciding === approval.id || !!launched[approval.id]}
                className="px-4 py-1.5 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded hover:bg-red-500/20 transition-colors disabled:opacity-50"
              >
                Reject
              </button>
              <span className="text-xs text-gray-600 ml-auto">
                {new Date(approval.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-sm font-mono font-semibold ${highlight ? "text-yellow-400" : "text-white"}`}>{value}</p>
    </div>
  );
}
