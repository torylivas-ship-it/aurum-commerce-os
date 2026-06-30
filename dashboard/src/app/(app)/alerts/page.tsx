"use client";

import { useEffect, useState } from "react";
import { api, type Alert } from "@/lib/api";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    api.alerts.list(false).then(setAlerts).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const resolve = async (id: string) => {
    await api.alerts.resolve(id);
    setAlerts(prev => prev.filter(a => a.id !== id));
  };

  const severityStyle: Record<string, string> = {
    critical: "border-red-500/40 bg-red-500/5",
    warning:  "border-orange-500/40 bg-orange-500/5",
    info:     "border-blue-500/40 bg-blue-500/5",
  };

  const severityBadge: Record<string, string> = {
    critical: "bg-red-500/20 text-red-400 border-red-400/30",
    warning:  "bg-orange-500/20 text-orange-400 border-orange-400/30",
    info:     "bg-blue-500/20 text-blue-400 border-blue-400/30",
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Risk Alerts</h1>
          <p className="text-sm text-gray-400">{alerts.length} unresolved alerts</p>
        </div>
      </div>

      {loading && <div className="animate-pulse h-32 bg-gray-900 rounded-lg border border-gray-800" />}

      {!loading && alerts.length === 0 && (
        <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-12 text-center">
          <p className="text-green-400 font-medium">All clear — no active risk alerts</p>
        </div>
      )}

      {alerts.map(alert => (
        <div key={alert.id} className={`rounded-lg border p-4 ${severityStyle[alert.severity] || ""}`}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className={`px-2 py-0.5 rounded border text-xs font-medium uppercase mt-0.5 ${severityBadge[alert.severity] || ""}`}>
                {alert.severity}
              </span>
              <div>
                <p className="text-white font-medium">{alert.title}</p>
                <p className="text-gray-400 text-sm mt-0.5">{alert.message}</p>
                <p className="text-gray-600 text-xs mt-1">{alert.alert_type} · {new Date(alert.created_at).toLocaleString()}</p>
              </div>
            </div>
            <button
              onClick={() => resolve(alert.id)}
              className="px-3 py-1 border border-gray-700 text-gray-400 text-xs rounded hover:border-gray-500 hover:text-gray-200 transition-colors flex-shrink-0"
            >
              Resolve
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
