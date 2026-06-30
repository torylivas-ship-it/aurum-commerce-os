"use client";

import { useEffect, useState } from "react";
import { api, type Store } from "@/lib/api";

export default function StoresPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.stores.list().then(setStores).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-white">Store Portfolio</h1>
        <p className="text-sm text-gray-400">Manage up to 20 stores from one dashboard</p>
      </div>

      {loading && <div className="animate-pulse h-32 bg-gray-900 rounded-lg border border-gray-800" />}

      {!loading && stores.length === 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-12 text-center">
          <p className="text-gray-400 font-medium">No stores connected yet</p>
          <p className="text-gray-600 text-sm mt-1">Add your Shopify store credentials in .env to get started</p>
        </div>
      )}

      <div className="grid gap-3">
        {stores.map(store => (
          <div key={store.id} className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4 flex items-center justify-between">
            <div>
              <p className="text-white font-medium">{store.name}</p>
              <p className="text-gray-500 text-xs capitalize">{store.platform} · {store.niche || "General"}</p>
            </div>
            <span className={`px-2 py-0.5 rounded border text-xs ${
              store.status === "active"
                ? "text-green-400 border-green-400/30 bg-green-400/10"
                : "text-gray-400 border-gray-600"
            }`}>
              {store.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
