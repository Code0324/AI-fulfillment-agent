"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "@/components/dashboard/DashboardShell";
import {
  fetchOrders,
  fetchInventory,
  fetchDashboardSummary,
  type Order,
  type OrderStatus,
  type InventoryItem,
  type DashboardSummary,
  type ConnectionState,
} from "@/lib/api";
import {
  ShoppingCart,
  Package,
  TrendingUp,
  Warehouse,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  XCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// AI Fulfillment Control Center — connections, automation summary, activity
// feed, and the human-approval queue. This is the automation-first view;
// the order/inventory panels below remain for anyone who wants the
// generic operational detail.
// ---------------------------------------------------------------------------

const CONNECTION_STATE_META: Record<
  ConnectionState,
  { label: string; dot: string; text: string; border: string; bg: string }
> = {
  NOT_CONFIGURED: { label: "Not Configured", dot: "bg-yellow-400", text: "text-yellow-700", border: "border-yellow-100", bg: "bg-yellow-50" },
  CONNECTION_ERROR: { label: "Connection Error", dot: "bg-red-500", text: "text-red-700", border: "border-red-100", bg: "bg-red-50" },
  CONNECTED: { label: "Connected", dot: "bg-green-500", text: "text-green-700", border: "border-green-100", bg: "bg-green-50" },
};

function ConnectionBadge({
  label,
  state,
  detail,
  error,
}: {
  label: string;
  state: ConnectionState;
  detail?: string;
  error?: string;
}) {
  const meta = CONNECTION_STATE_META[state];
  return (
    <div className={`rounded-lg border p-4 flex items-center justify-between shadow-subtle transition-all ${meta.border} ${meta.bg}`} title={error}>
      <div>
        <p className="text-sm font-semibold text-gray-900">{label}</p>
        {detail && <p className="text-xs text-gray-500 mt-1">{detail}</p>}
      </div>
      <span className={`inline-flex items-center gap-2 text-xs font-semibold ${meta.text}`}>
        <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
        {meta.label}
      </span>
    </div>
  );
}

const ACTIVITY_ICON: Record<string, string> = {
  success: "✓",
  warning: "⚠",
  error: "✗",
  info: "•",
};

const ACTIVITY_COLOR: Record<string, string> = {
  success: "text-green-700",
  warning: "text-yellow-700",
  error: "text-red-700",
  info: "text-gray-500",
};

function ControlCenter() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const result = await fetchDashboardSummary();
    if (result.ok) {
      setSummary(result.data);
      setSummaryError(null);
    } else {
      setSummaryError(result.error);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const countCards = summary
    ? [
        { label: "New TikTok Orders", value: summary.counts.new, icon: ShoppingCart, color: "text-brand-blue", bg: "bg-blue-50" },
        { label: "Processing", value: summary.counts.processing, icon: Bot, color: "text-purple-600", bg: "bg-purple-50" },
        { label: "Awaiting Approval", value: summary.counts.awaiting_approval, icon: Clock, color: "text-yellow-600", bg: "bg-yellow-50" },
        { label: "Completed", value: summary.counts.completed, icon: CheckCircle2, color: "text-green-600", bg: "bg-green-50" },
        { label: "Errors", value: summary.counts.errors, icon: XCircle, color: "text-red-600", bg: "bg-red-50" },
      ]
    : [];

  return (
    <div className="mb-12 space-y-8">
      <div>
        <h2 className="text-3xl font-serif font-bold text-luxury-charcoal mb-2">Fulfillment Control</h2>
        <p className="text-sm text-gray-500">Automation & approval queue — your oversight where it matters.</p>
      </div>

      {summaryError && (
        <div className="bg-red-50 border border-red-100 text-red-700 rounded-lg px-5 py-4 text-sm shadow-subtle" role="alert">
          {summaryError}
        </div>
      )}

      {summary && (
        <>
          {/* Connections */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <ConnectionBadge label="TikTok Shop" state={summary.connections.tiktok.status} detail={summary.connections.tiktok.environment} error={summary.connections.tiktok.error} />
            <ConnectionBadge label="Google Sheets" state={summary.connections.google_sheets.status} error={summary.connections.google_sheets.error} />
            <ConnectionBadge label="Amazon Account" state={summary.connections.amazon.status} detail={summary.connections.amazon.environment} error={summary.connections.amazon.error} />
            <ConnectionBadge label="Database" state={summary.connections.database.status} detail={summary.connections.database.healthy ? "Healthy" : undefined} />
          </div>

          {/* Automation summary */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-5">
            {countCards.map((c) => (
              <div key={c.label} className="bg-white rounded-lg border border-gray-100 p-5 shadow-subtle hover:shadow-card transition-shadow">
                <div className={`w-10 h-10 rounded-lg ${c.bg} flex items-center justify-center mb-4`}>
                  <c.icon className={`w-5 h-5 ${c.color}`} />
                </div>
                <p className="text-2xl font-bold text-luxury-charcoal">{c.value}</p>
                <p className="text-xs text-gray-500 mt-2 font-medium">{c.label}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Activity feed */}
            <div className="bg-white rounded-lg border border-gray-100 p-6 shadow-subtle">
              <h3 className="text-base font-semibold text-luxury-charcoal mb-5">Activity Feed</h3>
              {summary.activity.length === 0 ? (
                <p className="text-sm text-gray-400">No recent activity — orders synced here when queued.</p>
              ) : (
                <ul className="space-y-3">
                  {summary.activity.map((line, i) => (
                    <li key={i} className={`text-sm leading-relaxed ${ACTIVITY_COLOR[line.level]}`}>
                      {ACTIVITY_ICON[line.level]} {line.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Approval queue */}
            <div className="bg-white rounded-lg border border-gray-100 p-6 shadow-subtle">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-base font-semibold text-luxury-charcoal">Approval Queue</h3>
                <Link href="/dashboard/approvals" className="text-sm text-luxury-gold hover:text-luxury-gold-dark font-medium transition-colors">
                  View All →
                </Link>
              </div>
              {summary.approval_queue.length === 0 ? (
                <p className="text-sm text-gray-400">All clear — no approvals pending.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 text-xs font-semibold uppercase tracking-widest border-b border-gray-100">
                        <th className="py-3 pr-4">Order</th>
                        <th className="py-3 pr-4">SKU</th>
                        <th className="py-3 pr-4">Qty</th>
                        <th className="py-3 pr-4">Total</th>
                        <th className="py-3 text-right"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {summary.approval_queue.map((item) => (
                        <tr key={item.workflow_id} className="hover:bg-luxury-cream-dark/30 transition-colors">
                          <td className="py-3 pr-4 font-mono text-xs text-gray-700">{item.tiktok_order_id ?? item.order_id.slice(0, 8)}</td>
                          <td className="py-3 pr-4 text-gray-700">{item.amazon_sku}</td>
                          <td className="py-3 pr-4 text-gray-700">{item.quantity}</td>
                          <td className="py-3 pr-4 font-semibold text-gray-900">{item.total != null ? `$${item.total.toFixed(2)}` : "—"}</td>
                          <td className="py-3 text-right">
                            <Link href="/dashboard/approvals" className="text-xs text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors">
                              Review →
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const statusStyles: Record<OrderStatus, string> = {
  pending: "bg-yellow-50 text-yellow-700 border border-yellow-200",
  processing: "bg-orange-50 text-orange-700 border border-orange-200",
  shipped: "bg-purple-50 text-purple-700 border border-purple-200",
  delivered: "bg-green-50 text-green-700 border border-green-200",
  cancelled: "bg-red-50 text-red-700 border border-red-200",
};

const PIPELINE_STAGES: { status: OrderStatus; label: string; color: string }[] = [
  { status: "pending", label: "Pending", color: "from-yellow-400 to-yellow-500" },
  { status: "processing", label: "Processing", color: "from-brand-blue to-brand-blue-light" },
  { status: "shipped", label: "Shipped", color: "from-orange-400 to-orange-500" },
  { status: "delivered", label: "Delivered", color: "from-purple-400 to-purple-500" },
];

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function DashboardPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [totalSkus, setTotalSkus] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [ordersResult, inventoryResult] = await Promise.all([
      fetchOrders(1, 100),
      fetchInventory(1, 100),
    ]);
    if (ordersResult.ok) {
      setOrders(ordersResult.data.items);
      setTotalOrders(ordersResult.data.total_items);
    } else {
      setError(ordersResult.error);
    }
    if (inventoryResult.ok) {
      setInventory(inventoryResult.data.items);
      setTotalSkus(inventoryResult.data.total_items);
    } else {
      setError((prev) => prev ?? inventoryResult.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const deliveredCount = orders.filter((o) => o.status === "delivered").length;
  const pendingCount = orders.filter((o) => o.status === "pending").length;
  const lowStockItems = inventory
    .filter((i) => i.status === "low_stock" || i.status === "out_of_stock")
    .sort((a, b) => a.available_quantity - b.available_quantity)
    .slice(0, 5);
  const recentOrders = [...orders]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);
  const reservedCount = orders.filter((o) => o.inventory_reserved).length;
  const reservationRate = orders.length ? Math.round((reservedCount / orders.length) * 100) : 0;

  const statsCards = [
    { label: "Total Orders", value: totalOrders, icon: ShoppingCart, color: "text-brand-blue", bg: "bg-blue-50" },
    { label: "Delivered", value: deliveredCount, icon: Package, color: "text-green-600", bg: "bg-green-50" },
    { label: "Pending", value: pendingCount, icon: TrendingUp, color: "text-orange-500", bg: "bg-orange-50" },
    { label: "Total SKUs", value: totalSkus, icon: Warehouse, color: "text-purple-600", bg: "bg-purple-50" },
  ];

  return (
    <DashboardShell activeItem="Overview">
      <ControlCenter />

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-700 rounded-lg px-5 py-4 text-sm mb-8 shadow-subtle" role="alert">
          {error}
        </div>
      )}

      {/* Stats cards */}
      <div>
        <h3 className="text-base font-semibold text-luxury-charcoal mb-5">Order & Inventory Summary</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {statsCards.map((stat) => (
            <div key={stat.label} className="bg-white rounded-lg border border-gray-100 p-6 shadow-subtle hover:shadow-card transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <div className={`w-10 h-10 rounded-lg ${stat.bg} flex items-center justify-center`}>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
              </div>
              <p className="text-3xl font-bold text-luxury-charcoal">{loading ? "—" : stat.value}</p>
              <p className="text-sm text-gray-500 mt-2 font-medium">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 mt-8">
        {/* Left column: Orders + Inventory */}
        <div className="xl:col-span-2 space-y-8">
          <div className="bg-white rounded-lg border border-gray-100 overflow-hidden shadow-subtle">
            <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-base font-semibold text-luxury-charcoal">Recent Orders</h2>
              <Link href="/dashboard/orders" className="text-sm text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors">
                View All →
              </Link>
            </div>
            {loading && <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>}
            {!loading && recentOrders.length === 0 && (
              <div className="p-8 text-center text-gray-400 text-sm">No orders yet.</div>
            )}
            {!loading && recentOrders.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b border-gray-100 bg-luxury-cream/50">
                      <th className="px-6 py-4 font-semibold text-xs uppercase tracking-widest">Customer</th>
                      <th className="px-6 py-4 font-semibold text-xs uppercase tracking-widest">Date</th>
                      <th className="px-6 py-4 font-semibold text-xs uppercase tracking-widest">Status</th>
                      <th className="px-6 py-4 font-semibold text-xs uppercase tracking-widest">Product</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {recentOrders.map((order) => (
                      <tr key={order.id} className="hover:bg-luxury-cream-dark/20 transition-colors">
                        <td className="px-6 py-4">
                          <div className="font-medium text-gray-900">{order.customer_name}</div>
                          <div className="text-xs text-gray-500 font-mono mt-0.5">{order.id.slice(0, 8)}</div>
                        </td>
                        <td className="px-6 py-4 text-gray-600">{formatDate(order.created_at)}</td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold ${statusStyles[order.status]}`}>
                            {order.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-700">
                          {order.quantity}× {order.product_name}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Inventory Overview */}
          <div className="bg-white rounded-lg border border-gray-100 p-6 shadow-subtle">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold text-luxury-charcoal">Inventory Alerts</h2>
              <Link href="/dashboard/inventory" className="text-sm text-luxury-gold hover:text-luxury-gold-dark font-semibold transition-colors">
                View All →
              </Link>
            </div>
            {!loading && lowStockItems.length === 0 && (
              <p className="text-sm text-gray-500">Inventory levels are healthy.</p>
            )}
            {lowStockItems.length > 0 && (
              <>
                <p className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500" /> Low Stock
                </p>
                <div className="space-y-3">
                  {lowStockItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between py-3 px-4 rounded-lg bg-luxury-cream-dark/50">
                      <div>
                        <p className="text-sm text-gray-900 font-medium">{item.product_name}</p>
                        <p className="text-xs text-gray-500 font-mono mt-0.5">{item.sku}</p>
                      </div>
                      <span className="text-sm font-bold text-red-600">{item.available_quantity} left</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right column: Pipeline + Summary */}
        <div className="space-y-8">
          <div className="bg-white rounded-lg border border-gray-100 p-6 shadow-subtle">
            <h2 className="text-base font-semibold text-luxury-charcoal mb-6">Order Pipeline</h2>
            <div className="space-y-6">
              {PIPELINE_STAGES.map((stage) => {
                const count = orders.filter((o) => o.status === stage.status).length;
                const pct = orders.length ? Math.round((count / orders.length) * 100) : 0;
                return (
                  <div key={stage.status}>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm text-gray-700 font-medium">{stage.label}</span>
                      <span className="text-sm font-bold text-luxury-charcoal">{count}</span>
                    </div>
                    <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${stage.color} transition-all duration-1000`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-100 p-6 shadow-subtle">
            <h2 className="text-base font-semibold text-luxury-charcoal mb-6">Key Metrics</h2>
            <div className="space-y-4">
              <div className="flex items-center gap-4 p-4 rounded-lg bg-luxury-cream-dark/30">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-100 flex items-center justify-center flex-shrink-0">
                  <ShoppingCart className="w-5 h-5 text-luxury-gold" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-medium">Total Orders</p>
                  <p className="text-2xl font-bold text-luxury-charcoal">{totalOrders}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 rounded-lg bg-luxury-cream-dark/30">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-100 flex items-center justify-center flex-shrink-0">
                  <Package className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-medium">Delivered</p>
                  <p className="text-2xl font-bold text-luxury-charcoal">{deliveredCount}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 rounded-lg bg-luxury-cream-dark/30">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-100 flex items-center justify-center flex-shrink-0">
                  <Warehouse className="w-5 h-5 text-luxury-charcoal" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-medium">Reservation Rate</p>
                  <p className="text-2xl font-bold text-luxury-charcoal">{reservationRate}%</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
