"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createOrder,
  fetchOrders,
  updateOrderStatus,
  type CreateOrderPayload,
  type Order,
  type OrderStatus,
} from "@/lib/api";
import OrderDetail from "@/components/OrderDetail";

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

  // create form
  const [form, setForm] = useState<CreateOrderPayload>({
    customer_name: "",
    shipping_address: "",
    product_name: "",
    quantity: 1,
  });
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // filter
  const [statusFilter, setStatusFilter] = useState<OrderStatus | undefined>(undefined);

  // detail view
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // Load data
  // ------------------------------------------------------------------

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchOrders(1, 200, statusFilter);
    if (result.ok) {
      setOrders(result.data.items);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  // ------------------------------------------------------------------
  // Summary counts (always from unfiltered full set)
  // ------------------------------------------------------------------

  const [allCounts, setAllCounts] = useState<Record<OrderStatus, number>>({
    pending: 0, processing: 0, shipped: 0, delivered: 0, cancelled: 0,
  });

  const loadAllCounts = useCallback(async () => {
    const result = await fetchOrders(1, 200);
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
      setForm({ customer_name: "", shipping_address: "", product_name: "", quantity: 1 });
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
    <section aria-label="Orders" className="space-y-6">
      {/* ---- Error banner ---- */}
      {error && (
        <div
          className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm flex items-start justify-between"
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

      {/* ---- Summary cards ---- */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Order Summary
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {summary.map(({ status, count }) => {
            const meta = ORDER_STATUS_META[status];
            return (
              <div
                key={status}
                className="rounded-lg border border-gray-200 bg-white p-4 text-center"
              >
                <div className="flex items-center justify-center gap-2 mb-1">
                  <span className={`w-2.5 h-2.5 rounded-full ${meta.dot}`} />
                  <span className="text-sm font-medium text-gray-700">
                    {meta.label}
                  </span>
                </div>
                <p className="text-3xl font-bold text-gray-900">{count}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- Create order ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Create Order
          </h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            {showForm ? "Cancel" : "+ New Order"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="text"
                value={form.customer_name}
                onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
                placeholder="Customer name *"
                required
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <input
                type="text"
                value={form.product_name}
                onChange={(e) => setForm({ ...form, product_name: e.target.value })}
                placeholder="Product name *"
                required
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <input
              type="text"
              value={form.shipping_address}
              onChange={(e) => setForm({ ...form, shipping_address: e.target.value })}
              placeholder="Shipping address *"
              required
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <div className="flex gap-3 items-end">
              <div className="w-24">
                <label className="block text-xs text-gray-500 mb-1">Qty</label>
                <input
                  type="number"
                  min={1}
                  value={form.quantity}
                  onChange={(e) =>
                    setForm({ ...form, quantity: parseInt(e.target.value) || 1 })
                  }
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <button
                type="submit"
                disabled={creating || !form.customer_name.trim() || !form.product_name.trim()}
                className="px-5 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {creating ? "Creating…" : "Create Order"}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* ---- Order list ---- */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Orders
          </h2>
          <div className="flex items-center gap-3">
            <select
              value={statusFilter ?? ""}
              onChange={(e) =>
                setStatusFilter(
                  e.target.value ? (e.target.value as OrderStatus) : undefined,
                )
              }
              className="text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              {ALL_ORDER_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {ORDER_STATUS_META[s].label}
                </option>
              ))}
            </select>
            <button
              onClick={loadOrders}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading && (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
            Loading orders…
          </div>
        )}

        {!loading && orders.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
            No orders yet. Create one above to get started.
          </div>
        )}

        {!loading && orders.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3">Product</th>
                    <th className="px-4 py-3">Qty</th>
                    <th className="px-4 py-3">Shipping</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {orders.map((order) => {
                    const meta = ORDER_STATUS_META[order.status];
                    return (
                      <tr key={order.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-900">
                            {order.customer_name}
                          </div>
                          <div className="text-xs text-gray-400 font-mono mt-0.5">
                            {order.id.slice(0, 8)}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {order.product_name}
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {order.quantity}
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs max-w-[200px] truncate">
                          {order.shipping_address}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${meta.bg} ${meta.text}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                            {meta.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {formatTime(order.created_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => setSelectedOrderId(order.id)}
                            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
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
