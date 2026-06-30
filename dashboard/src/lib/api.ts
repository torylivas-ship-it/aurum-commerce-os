const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  dashboard: {
    summary: () => apiFetch<DashboardSummary>("/api/v1/dashboard/summary"),
  },
  products: {
    list: (params?: Record<string, string | number>) => {
      const qs = params ? "?" + new URLSearchParams(params as Record<string, string>).toString() : "";
      return apiFetch<Product[]>(`/api/v1/products${qs}`);
    },
    get: (id: string) => apiFetch<Product>(`/api/v1/products/${id}`),
    discover: (niches?: string[]) =>
      apiFetch("/api/v1/products/discover", {
        method: "POST",
        body: JSON.stringify(niches),
      }),
  },
  approvals: {
    list: (status = "pending") => apiFetch<Approval[]>(`/api/v1/approvals?status=${status}`),
    decide: (id: string, decision: "approve" | "reject", reason?: string) =>
      apiFetch(`/api/v1/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision, reason, approved_by: "admin" }),
      }),
  },
  alerts: {
    list: (resolved = false) => apiFetch<Alert[]>(`/api/v1/alerts?resolved=${resolved}`),
    resolve: (id: string) =>
      apiFetch(`/api/v1/alerts/${id}/resolve`, { method: "PATCH" }),
  },
  briefs: {
    latest: () => apiFetch<Brief>("/api/v1/briefs/latest"),
    list: () => apiFetch<BriefSummary[]>("/api/v1/briefs"),
    generate: () => apiFetch("/api/v1/briefs/generate", { method: "POST" }),
  },
  agents: {
    runs: (agent?: string) =>
      apiFetch<AgentRun[]>(`/api/v1/agents/runs${agent ? `?agent_name=${agent}` : ""}`),
    trigger: (name: string) =>
      apiFetch(`/api/v1/agents/trigger/${name}`, { method: "POST" }),
  },
  stores: {
    list: () => apiFetch<Store[]>("/api/v1/stores"),
  },
};

// ── Types ────────────────────────────────────────────────────────────────────
export interface DashboardSummary {
  timestamp: string;
  portfolio: { total_stores: number; products: Record<string, number>; total_products: number };
  pipeline: { discovered: number; pending_approval: number; approved: number; launched: number; scaling: number };
  alerts: { critical: number; warning: number; total_unresolved: number };
  top_opportunities: Product[];
  agents: { recent_runs: AgentRun[] };
  latest_brief: { date: string; confidence_score: number; products_to_launch: number; revenue_projection: number } | null;
}

export interface Product {
  id: string;
  name: string;
  category?: string;
  status: string;
  opportunity_score?: number;
  confidence_score?: number;
  risk_score?: number;
  gross_margin?: number;
  selling_price?: number;
  supplier_cost?: number;
  shipping_cost?: number;
  lifecycle?: string;
  supplier_name?: string;
  shipping_days?: number;
  source_platform?: string;
  image_url?: string;
  score_breakdown?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
}

export interface Approval {
  id: string;
  request_type: string;
  title: string;
  description?: string;
  status: string;
  data?: Record<string, unknown>;
  impact?: string;
  confidence_score?: number;
  risk_assessment?: string;
  created_at: string;
}

export interface Alert {
  id: string;
  severity: "info" | "warning" | "critical";
  alert_type: string;
  title: string;
  message: string;
  is_resolved: boolean;
  product_id?: string;
  created_at: string;
}

export interface Brief {
  id: string;
  date: string;
  content: string;
  structured_data: Record<string, unknown>;
  products_to_launch: unknown[];
  products_to_retire: unknown[];
  revenue_projection?: number;
  confidence_score?: number;
}

export interface BriefSummary {
  id: string;
  date: string;
  products_to_launch: number;
  products_to_retire: number;
  revenue_projection?: number;
  confidence_score?: number;
}

export interface AgentRun {
  id: string;
  agent_name: string;
  status: string;
  duration_seconds?: number;
  created_at: string;
  error?: string;
}

export interface Store {
  id: string;
  name: string;
  niche?: string;
  platform: string;
  status: string;
}
