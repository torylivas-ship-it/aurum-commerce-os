"use client";

import { useEffect, useState } from "react";
import { api, type Store } from "@/lib/api";

export default function StoresPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New store form
  const [form, setForm] = useState({
    name: "",
    niche: "",
    shopify_store_url: "",
    shopify_access_token: "",
  });

  const load = () =>
    api.stores.list().then(setStores).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const createStore = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setConnecting("new");
    try {
      await api.stores.create({
        name: form.name,
        niche: form.niche || undefined,
        shopify_store_url: form.shopify_store_url || undefined,
        shopify_access_token: form.shopify_access_token || undefined,
      });
      setForm({ name: "", niche: "", shopify_store_url: "", shopify_access_token: "" });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add store");
    } finally {
      setConnecting(null);
    }
  };

  const connectShopify = async (store: Store, token: string, url: string) => {
    setError(null);
    setConnecting(store.id);
    try {
      const updated = await api.stores.connect(store.id, url, token);
      setStores(prev => prev.map(s => s.id === store.id ? { ...s, ...updated } : s));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Shopify connection failed");
    } finally {
      setConnecting(null);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Store Portfolio</h1>
          <p className="text-sm text-gray-400">Manage your Shopify stores — approved products launch here automatically</p>
        </div>
        <button
          onClick={() => { setShowAdd(v => !v); setError(null); }}
          className="px-4 py-2 bg-yellow-400/10 border border-yellow-400/30 text-yellow-400 text-sm rounded hover:bg-yellow-400/20 transition-colors"
        >
          {showAdd ? "Cancel" : "+ Add Store"}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Add store form */}
      {showAdd && (
        <form onSubmit={createStore} className="rounded-lg border border-yellow-400/20 bg-gray-900/60 p-5 space-y-4">
          <h2 className="text-white font-medium text-sm">Connect a Shopify Store</h2>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Store Name *" value={form.name} onChange={v => setForm(f => ({ ...f, name: v }))} placeholder="My Fitness Store" required />
            <Field label="Niche" value={form.niche} onChange={v => setForm(f => ({ ...f, niche: v }))} placeholder="fitness, home decor…" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Shopify Store URL *"
              value={form.shopify_store_url}
              onChange={v => setForm(f => ({ ...f, shopify_store_url: v }))}
              placeholder="mystore.myshopify.com"
              required
            />
            <Field
              label="Admin API Access Token *"
              value={form.shopify_access_token}
              onChange={v => setForm(f => ({ ...f, shopify_access_token: v }))}
              placeholder="shpat_xxxxxxxxxxxxxxxx"
              secret
              required
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={connecting === "new"}
              className="px-5 py-2 bg-yellow-400 text-gray-900 text-sm font-semibold rounded hover:bg-yellow-300 transition-colors disabled:opacity-50"
            >
              {connecting === "new" ? "Connecting…" : "Connect Store"}
            </button>
            <p className="text-xs text-gray-500">
              Get your token: Shopify Admin → Settings → Apps → Develop apps → Admin API
            </p>
          </div>
        </form>
      )}

      {loading && <div className="animate-pulse h-32 bg-gray-900 rounded-lg border border-gray-800" />}

      {!loading && stores.length === 0 && (
        <EmptyState onAdd={() => setShowAdd(true)} />
      )}

      <div className="grid gap-3">
        {stores.map(store => (
          <StoreCard
            key={store.id}
            store={store}
            connecting={connecting === store.id}
            onConnect={connectShopify}
          />
        ))}
      </div>
    </div>
  );
}

function StoreCard({
  store,
  connecting,
  onConnect,
}: {
  store: Store;
  connecting: boolean;
  onConnect: (store: Store, token: string, url: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [token, setToken] = useState("");
  const [url, setUrl] = useState(store.shopify_store_url || "");

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white font-medium">{store.name}</p>
          <p className="text-gray-500 text-xs capitalize">
            {store.platform} · {store.niche || "General"}
            {store.shopify_store_url && (
              <span className="ml-2 text-gray-600">{store.shopify_store_url}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded border text-xs ${
            store.connected
              ? "text-green-400 border-green-400/30 bg-green-400/10"
              : "text-orange-400 border-orange-400/30 bg-orange-400/10"
          }`}>
            {store.connected ? "✓ Connected" : "Not connected"}
          </span>
          {!store.connected && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="text-xs text-yellow-400 hover:text-yellow-300 transition-colors"
            >
              {expanded ? "Cancel" : "Connect →"}
            </button>
          )}
        </div>
      </div>

      {expanded && !store.connected && (
        <div className="space-y-2 pt-1 border-t border-gray-800">
          <Field
            label="Shopify Store URL"
            value={url}
            onChange={setUrl}
            placeholder="mystore.myshopify.com"
          />
          <Field
            label="Admin API Access Token"
            value={token}
            onChange={setToken}
            placeholder="shpat_xxxxxxxxxxxxxxxx"
            secret
          />
          <button
            onClick={() => onConnect(store, token, url)}
            disabled={connecting || !token || !url}
            className="px-4 py-1.5 bg-yellow-400 text-gray-900 text-xs font-semibold rounded hover:bg-yellow-300 transition-colors disabled:opacity-50"
          >
            {connecting ? "Verifying…" : "Save & Verify"}
          </button>
        </div>
      )}
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, secret, required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  secret?: boolean;
  required?: boolean;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-gray-400">{label}</label>
      <input
        type={secret ? "password" : "text"}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-yellow-400/50"
      />
    </div>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-700 bg-gray-900/30 p-12 text-center space-y-3">
      <p className="text-gray-300 font-medium">No stores connected</p>
      <p className="text-gray-600 text-sm max-w-md mx-auto">
        Connect a Shopify store to start auto-launching approved products.
        You need a Shopify Admin API access token with <code className="text-gray-400">write_products</code> scope.
      </p>
      <button
        onClick={onAdd}
        className="mt-2 px-5 py-2 bg-yellow-400 text-gray-900 text-sm font-semibold rounded hover:bg-yellow-300 transition-colors"
      >
        Connect First Store
      </button>
    </div>
  );
}
