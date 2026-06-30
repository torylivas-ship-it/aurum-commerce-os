"use client";

import { useEffect, useState } from "react";
import { api, type Product } from "@/lib/api";
import { ScoreBadge } from "@/components/ui/ScoreBadge";

const STATUS_FILTERS = ["all", "discovered", "approved", "launched", "scaling", "rejected"];

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [discovering, setDiscovering] = useState(false);

  const load = (status?: string) => {
    setLoading(true);
    const params = status && status !== "all" ? { status } : {};
    api.products.list(params).then(setProducts).finally(() => setLoading(false));
  };

  useEffect(() => { load(statusFilter); }, [statusFilter]);

  const triggerDiscovery = async () => {
    setDiscovering(true);
    try { await api.products.discover(); }
    finally { setDiscovering(false); }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Products</h1>
          <p className="text-sm text-gray-400">{products.length} products · Sorted by Opportunity Score</p>
        </div>
        <button
          onClick={triggerDiscovery}
          disabled={discovering}
          className="px-4 py-2 bg-yellow-400/10 border border-yellow-400/30 text-yellow-400 text-sm rounded hover:bg-yellow-400/20 transition-colors disabled:opacity-50"
        >
          {discovering ? "Queued..." : "Run Discovery"}
        </button>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 flex-wrap">
        {STATUS_FILTERS.map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors capitalize ${
              statusFilter === s
                ? "bg-yellow-400/20 border-yellow-400/50 text-yellow-300"
                : "border-gray-700 text-gray-400 hover:border-gray-600"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-900/50 rounded-lg border border-gray-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-gray-800 bg-gray-900/20 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase bg-gray-900/40">
                <th className="text-left px-4 py-2.5 font-medium">Product</th>
                <th className="text-left px-4 py-2.5 font-medium">Source</th>
                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                <th className="text-center px-4 py-2.5 font-medium">Score</th>
                <th className="text-center px-4 py-2.5 font-medium">Conf</th>
                <th className="text-center px-4 py-2.5 font-medium">Risk</th>
                <th className="text-right px-4 py-2.5 font-medium">Margin</th>
                <th className="text-right px-4 py-2.5 font-medium">Price</th>
                <th className="text-right px-4 py-2.5 font-medium">Ship</th>
              </tr>
            </thead>
            <tbody>
              {products.map(p => (
                <tr key={p.id} className="border-b border-gray-800/40 hover:bg-gray-800/20 transition-colors">
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-white font-medium truncate">{p.name}</p>
                    {p.category && <p className="text-xs text-gray-500">{p.category}</p>}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{p.source_platform || "—"}</td>
                  <td className="px-4 py-3">
                    <StatusChip status={p.status} />
                  </td>
                  <td className="px-4 py-3 text-center"><ScoreBadge score={p.opportunity_score} /></td>
                  <td className="px-4 py-3 text-center"><ScoreBadge score={p.confidence_score} /></td>
                  <td className="px-4 py-3 text-center"><ScoreBadge score={p.risk_score} /></td>
                  <td className="px-4 py-3 text-right font-mono text-green-400">
                    {p.gross_margin ? `${(p.gross_margin * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-white">
                    {p.selling_price ? `$${p.selling_price.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400">
                    {p.shipping_days ? `${p.shipping_days}d` : "—"}
                  </td>
                </tr>
              ))}
              {products.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-gray-600">
                    No products found. Run a discovery scan to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const colors: Record<string, string> = {
    discovered:  "bg-blue-400/10 text-blue-400 border-blue-400/20",
    evaluating:  "bg-purple-400/10 text-purple-400 border-purple-400/20",
    approved:    "bg-green-400/10 text-green-400 border-green-400/20",
    rejected:    "bg-red-400/10 text-red-400 border-red-400/20",
    launched:    "bg-teal-400/10 text-teal-400 border-teal-400/20",
    scaling:     "bg-yellow-400/10 text-yellow-400 border-yellow-400/20",
    maintaining: "bg-gray-400/10 text-gray-400 border-gray-400/20",
    retiring:    "bg-orange-400/10 text-orange-400 border-orange-400/20",
  };
  return (
    <span className={`px-2 py-0.5 rounded border text-xs capitalize ${colors[status] || "text-gray-400 border-gray-600"}`}>
      {status}
    </span>
  );
}
