"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createOrder,
  fetchOrders,
  fetchTiktokStatus,
  reserveOrderInventory,
  syncTiktokOrders,
  updateOrderStatus,
  type CreateOrderPayload,
  type Order,
  type OrderStatus,
  type TikTokConnectionStatus,
  type TikTokSyncResult,
} from "@/lib/api";
import OrderDetail from "@/components/OrderDetail";

// ---------------------------------------------------------------------------
// Agent status (derived, not a backend field) — a quick read of where an
// order sits in the automated pipeline without a second network call.
// ---------------------------------------------------------------------------

function agentStatusFor(order: Order): { label: string; bg: string; text: string } {
  if (order.source !== "TIKTOK") {
    return { label: "Manual", bg: "bg-gray-50", text: "text-gray-500" };
  }
  if (order.status === "cancelled") {
    return { label: "Cancelled", bg: "bg-red-50", text: "text-red-700" };
  }
  if (order.status === "delivered" || order.status === "shipped") {
    return { label: "Completed", bg: "bg-green-50", text: "text-green-700" };
  }
  if (order.inventory_reserved) {
    return { label: "Prepared — awaiting approval", bg: "bg-blue-50", text: "text-blue-700" };
  }
  return { label: "Processing", bg: "bg-yellow-50", text: "text-yellow-700" };
}

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const ORDER_STATUS_META: Record<
  OrderStatus,
  { label: string; dot: string; bg: string; text: string }
> = {
  pending: {
    label: "Pending",
    dot: "bg-yellow-400",
    bg: "bg-yellow-50",
    text: "text-yellow-700",
  },
  processing: {
    label: "Processing",
    dot: "bg-blue-400",
    bg: "bg-blue-50",
    text: "text-blue-700",
  },
  shipped: {
    label: "Shipped",
    dot: "bg-purple-400",
    bg: "bg-purple-50",
    text: "text-purple-700",
  },
  delivered: {
    label: "Delivered",
    dot: "bg-green-400",
    bg: "bg-green-50",
    text: "text-green-700",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-red-400",
    bg: "bg-red-50",
    text: "text-red-700",
  },
};

const ALL_ORDER_STATUSES: OrderStatus[] = [
  "pending",
  "processing",
  "shipped",
  "delivered",
  "cancelled",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrdersSection() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // TikTok connection + sync
  const [tiktokStatus, setTiktokStatus] = useState<TikTokConnectionStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<TikTokSyncResult | null>(null);

  // create form
  const [form, setForm] = useState<CreateOrderPayload>({
    customer_name: "",
    shipping_address: "",
    product_name: "",
    quantity: 1,
    sku: "",
    reserve_inventory: false,
  });
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // filter
  const [statusFilter, setStatusFilter] = useState<OrderStatus | undefined>(undefined);
  const [sourceFilter, setSourceFilter] = useState<Order["source"] | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // detail view
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  // debounced search
  function handleSearchChange(value: string) {
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setDebouncedSearch(value);
    }, 300);
  }

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, []);

  // ------------------------------------------------------------------
  // Load data
  // ------------------------------------------------------------------

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchOrders(1, 100, statusFilter, debouncedSearch || undefined, sourceFilter);
    if (result.ok) {
      setOrders(result.data.items);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [statusFilter, debouncedSearch, sourceFilter]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const loadTiktokStatus = useCallback(async () => {
    const result = await fetchTiktokStatus();
    if (result.ok) setTiktokStatus(result.data);
  }, []);

  useEffect(() => {
    loadTiktokStatus();
  }, [loadTiktokStatus]);

  async function handleSyncTiktok() {
    setSyncing(true);
    setSyncResult(null);
    const result = await syncTiktokOrders();
    if (result.ok) {
      setSyncResult(result.data);
      if (result.data.created > 0) {
        loadOrders();
        loadAllCounts();
      }
    } else {
      setError(result.error);
    }
    setSyncing(false);
  }

  // ------------------------------------------------------------------
  // Summary counts (always from unfiltered full set)
  // ------------------------------------------------------------------

  const [allCounts, setAllCounts] = useState<Record<OrderStatus, number>>({
    pending: 0, processing: 0, shipped: 0, delivered: 0, cancelled: 0,
  });

  const loadAllCounts = useCallback(async () => {
    const result = await fetchOrders(1, 100);
    if (result.ok) {
      const counts: Record<OrderStatus, number> = {
        pending: 0, processing: 0, shipped: 0, delivered: 0, cancelled: 0,
      };
      for (const o of result.data.items) {
        counts[o.status]++;
      }
      setAllCounts(counts);
    }
  }, []);

  useEffect(() => {
    loadAllCounts();
  }, [loadAllCounts]);

  const summary = ALL_ORDER_STATUSES.map((s) => ({
    status: s,
    count: allCounts[s],
  }));

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.customer_name.trim() || !form.product_name.trim()) return;
    setCreating(true);
    const result = await createOrder(form);
    if (result.ok) {
      setOrders((prev) => [...prev, result.data]);
      setForm({ customer_name: "", shipping_address: "", product_name: "", quantity: 1, sku: "", reserve_inventory: false });
      setShowForm(false);
    } else {
      setError(result.error);
    }
    setCreating(false);
  }

  async function handleStatusChange(orderId: string, newStatus: OrderStatus) {
    const result = await updateOrderStatus(orderId, newStatus);
    if (result.ok) {
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? result.data : o)),
      );
    } else {
      setError(result.error);
    }
  }

  async function handleReserve(orderId: string) {
    const result = await reserveOrderInventory(orderId);
    if (result.ok) {
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? result.data : o)),
      );
    } else {
      setError(result.error);
    }
  }

  // ------------------------------------------------------------------
  // Detail view
  // ------------------------------------------------------------------

  function handleOrderStatusChanged(updated: Order) {
    setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    loadAllCounts();
  }

  if (selectedOrderId) {
    return (
      <section aria-label="Order Detail">
        <OrderDetail
          orderId={selectedOrderId}
          onClose={() => setSelectedOrderId(null)}
          onStatusChanged={handleOrderStatusChanged}
        />
      </section>
    );
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <section aria-label="Orders" className="space-y-8">
      {/* ---- Error banner ---- */}
      {error && (
        <div
          className="bg-red-50 border border-red-100 text-red-700 rounded-lg px-5 py-4 text-sm flex items-start justify-between shadow-subtle"
          role="alert"
        >
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-4 text-red-500 hover:text-red-700 font-bold"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {/* ---- TikTok Shop Orders ---- */}
      <div className="bg-white border border-gray-100 rounded-lg p-6 shadow-subtle">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold text-luxury-charcoal">
            TikTok Shop Sync
          </h2>
          {tiktokStatus?.configured ? (
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-50 border border-green-100 text-xs font-semibold text-green-700">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              Connected
            </span>
          ) : (
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-yellow-50 border border-yellow-100 text-xs font-semibold text-yellow-700">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
              Not Configured
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Sync new orders from TikTok Shop and match them to inventory.
        </p>
        <button
          onClick={handleSyncTiktok}
          disabled={syncing || !tiktokStatus?.configured}
          className="px-5 py-2.5 rounded-lg text-sm font-semibold text-white bg-luxury-charcoal hover:bg-luxury-charcoal-light disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          {syncing ? "Syncing…" : "Sync TikTok Orders"}
        </button>
        {!tiktokStatus?.configured && (
          <p className="text-xs text-gray-400 mt-2">
            Connect TikTok Shop (TIKTOK_APP_KEY / APP_SECRET / ACCESS_TOKEN) to enable automatic order ingestion.
          </p>
        )}
        {syncResult && (
          <div className="mt-3 text-sm bg-gray-50 border border-gray-100 rounded-md px-3 py-2 text-gray-700">
            {syncResult.notice}
            {syncResult.created > 0 && (
              <span className="text-gray-500">
                {" "}
                — {syncResult.sheet_synced} synced to Google Sheet, {syncResult.workflow_started} sent to the fulfillment pipeline.
              </span>
            )}
            {syncResult.errors.length > 0 && (
              <ul className="mt-1 list-disc list-inside text-red-600">
                {syncResult.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* ---- Summary cards ---- */}
      <div>
        <h2 className="text-base font-semibold text-luxury-charcoal mb-5">
          Order Summary
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-5">
          {summary.map(({ status, count }) => {
            const meta = ORDER_STATUS_META[status];
            return (
              <div
                key={status}
                className="rounded-lg border border-gray-100 bg-white p-5 text-center shadow-subtle hover:shadow-card transition-shadow"
              >
                <div className="flex items-center justify-center gap-2 mb-3">
                  <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
                </div>
                <p className="text-3xl font-bold text-luxury-charcoal mb-1">{count}</p>
                <p className="text-xs text-gray-500 font-medium">{meta.label}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- Create order ---- */}
      <div className="bg-white border border-gray-100 rounded-lg p-6 shadow-subtle">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-luxury-charcoal">
            Create Order
          </h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="text-sm text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors"
          >
            {showForm ? "Cancel" : "+ New Manual Order"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <input
                type="text"
                value={form.customer_name}
                onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
                placeholder="Customer name"
                required
                className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-luxury-gold/50 focus:border-transparent bg-white"
              />
              <input
                type="text"
                value={form.product_name}
                onChange={(e) => setForm({ ...form, product_name: e.target.value })}
                placeholder="Product name"
                required
                className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-luxury-gold/50 focus:border-transparent bg-white"
              />
            </div>
            <input
              type="text"
              value={form.shipping_address}
              onChange={(e) => setForm({ ...form, shipping_address: e.target.value })}
              placeholder="Shipping address"
              required
              className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-luxury-gold/50 focus:border-transparent bg-white"
            />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-gray-500 font-medium mb-2">SKU (optional)</label>
                <input
                  type="text"
                  value={form.sku || ""}
                  onChange={(e) => setForm({ ...form, sku: e.target.value })}
                  placeholder="e.g. MOUSE-001"
                  className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-luxury-gold/50 focus:border-transparent bg-white"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 font-medium mb-2">Quantity</label>
                <input
                  type="number"
                  min={1}
                  value={form.quantity}
                  onChange={(e) =>
                    setForm({ ...form, quantity: parseInt(e.target.value) || 1 })
                  }
                  className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-luxury-gold/50 focus:border-transparent bg-white"
                />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.reserve_inventory || false}
                    onChange={(e) => setForm({ ...form, reserve_inventory: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  Reserve inventory
                </label>
              </div>
            </div>
            <button
              type="submit"
              disabled={creating || !form.customer_name.trim() || !form.product_name.trim()}
              className="px-5 py-2.5 rounded-lg text-sm font-semibold text-white bg-luxury-charcoal hover:bg-luxury-charcoal-light disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? "Creating…" : "Create Order"}
            </button>
          </form>
        )}
      </div>

      {/* ---- Order list ---- */}
      <div>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-luxury-charcoal">
            All Orders
          </h2>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search…"
              className="text-sm border border-gray-200 rounded-lg px-4 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-luxury-gold/50 w-48"
            />
            <select
              value={statusFilter ?? ""}
              onChange={(e) =>
                setStatusFilter(
                  e.target.value ? (e.target.value as OrderStatus) : undefined,
                )
              }
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-luxury-gold/50"
            >
              <option value="">All Statuses</option>
              {ALL_ORDER_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {ORDER_STATUS_META[s].label}
                </option>
              ))}
            </select>
            <select
              value={sourceFilter ?? ""}
              onChange={(e) =>
                setSourceFilter(
                  e.target.value ? (e.target.value as Order["source"]) : undefined,
                )
              }
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-luxury-gold/50"
            >
              <option value="">All Sources</option>
              <option value="TIKTOK">TikTok Shop</option>
              <option value="MANUAL">Manual</option>
              <option value="AMAZON">Amazon</option>
              <option value="MOCK_AMAZON">Mock Amazon</option>
            </select>
            <button
              onClick={loadOrders}
              className="text-sm text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading && (
          <div className="bg-white border border-gray-100 rounded-lg p-8 text-center text-gray-400 shadow-subtle">
            Loading orders…
          </div>
        )}

        {!loading && orders.length === 0 && (
          <div className="bg-white border border-gray-100 rounded-lg p-8 text-center text-gray-400 shadow-subtle">
            No orders yet. Create one above to get started.
          </div>
        )}

        {!loading && orders.length > 0 && (
          <div className="bg-white border border-gray-100 rounded-lg overflow-hidden shadow-subtle">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-luxury-cream/50 border-b border-gray-100 text-left text-xs font-semibold text-gray-500 uppercase tracking-widest">
                    <th className="px-6 py-4">Order ID</th>
                    <th className="px-6 py-4">Date</th>
                    <th className="px-6 py-4">SKU</th>
                    <th className="px-6 py-4">Product</th>
                    <th className="px-6 py-4">Variation</th>
                    <th className="px-6 py-4">Qty</th>
                    <th className="px-6 py-4">Customer</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Agent Status</th>
                    <th className="px-6 py-4">Inventory</th>
                    <th className="px-6 py-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {orders.map((order) => {
                    const meta = ORDER_STATUS_META[order.status];
                    const agentMeta = agentStatusFor(order);
                    return (
                      <tr key={order.id} className="hover:bg-luxury-cream-dark/30 transition-colors">
                        <td className="px-6 py-4 text-xs font-mono text-gray-700">
                          {order.source === "TIKTOK" && order.tiktok_order_id
                            ? order.tiktok_order_id
                            : order.id.slice(0, 8)}
                        </td>
                        <td className="px-6 py-4 text-gray-600 text-xs">
                          {formatTime(order.created_at)}
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-xs font-mono text-gray-700">
                            {order.sku || "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-800">
                          {order.product_name}
                        </td>
                        <td className="px-6 py-4 text-gray-600 text-xs">
                          {order.variation || "—"}
                        </td>
                        <td className="px-6 py-4 text-gray-800">
                          {order.quantity}
                        </td>
                        <td className="px-6 py-4">
                          <div className="font-medium text-gray-900">
                            {order.customer_name}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${meta.bg} ${meta.text}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                            {meta.label}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold ${agentMeta.bg} ${agentMeta.text}`}>
                            {agentMeta.label}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {order.inventory_reserved ? (
                            <span className="inline-flex items-center gap-1 text-xs text-green-700 font-semibold">
                              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                              Reserved
                            </span>
                          ) : order.sku ? (
                            <button
                              onClick={() => handleReserve(order.id)}
                              className="text-xs text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors"
                            >
                              Reserve
                            </button>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => setSelectedOrderId(order.id)}
                            className="text-xs text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
