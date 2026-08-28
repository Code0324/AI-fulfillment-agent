"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardShell from "@/components/dashboard/DashboardShell";
import { fetchOrders, fetchInventory, type Order, type OrderStatus, type InventoryItem } from "@/lib/api";
import { BarChart3, ShoppingCart, Package, Warehouse, AlertTriangle, Info } from "lucide-react";

const ALL_STATUSES: OrderStatus[] = ["pending", "processing", "shipped", "delivered", "cancelled"];

const statusColor: Record<OrderStatus, string> = {
  pending: "bg-yellow-400",
  processing: "bg-brand-blue",
  shipped: "bg-orange-400",
  delivered: "bg-green-500",
  cancelled: "bg-red-400",
};

export default function AnalyticsPage() {
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
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const deliveredCount = orders.filter((o) => o.status === "delivered").length;
  const cancelledCount = orders.filter((o) => o.status === "cancelled").length;
  const fulfillmentRate = orders.length
    ? Math.round((deliveredCount / orders.length) * 100)
    : 0;
  const lowStockCount = inventory.filter(
    (i) => i.status === "low_stock" || i.status === "out_of_stock",
  ).length;
  const maxStatusCount = Math.max(1, ...ALL_STATUSES.map((s) => orders.filter((o) => o.status === s).length));

  const kpis = [
    { label: "Total Orders", value: totalOrders, icon: ShoppingCart, color: "text-brand-blue", bg: "bg-blue-50" },
    { label: "Delivered", value: deliveredCount, icon: Package, color: "text-green-600", bg: "bg-green-50" },
    { label: "Fulfillment Rate", value: `${fulfillmentRate}%`, icon: BarChart3, color: "text-purple-600", bg: "bg-purple-50" },
    { label: "SKUs Low/Out of Stock", value: lowStockCount, icon: AlertTriangle, color: "text-orange-500", bg: "bg-orange-50" },
  ];

  return (
    <DashboardShell>
      <div className="space-y-6">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm" role="alert">
            {error}
          </div>
        )}

        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700 flex items-start gap-2">
          <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>
            These figures are computed live from real order and inventory data. Revenue and
            time-series trend analytics aren&apos;t available yet — the order model doesn&apos;t
            track price, and there&apos;s no historical/date-bucketed analytics backend.
          </span>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {kpis.map((kpi) => (
            <div key={kpi.label} className="bg-white rounded-xl border border-gray-200 p-4">
              <div className={`w-8 h-8 rounded-lg ${kpi.bg} flex items-center justify-center mb-2`}>
                <kpi.icon className={`w-4 h-4 ${kpi.color}`} />
              </div>
              <p className="text-2xl font-bold text-gray-900">{loading ? "—" : kpi.value}</p>
              <p className="text-xs text-gray-500 mt-1">{kpi.label}</p>
            </div>
          ))}
        </div>

        {/* Order status breakdown */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-bold text-gray-900 mb-5 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-brand-blue" />
            Order Status Breakdown ({orders.length} orders)
          </h2>
          {!loading && orders.length === 0 && (
            <p className="text-sm text-gray-400">No orders yet.</p>
          )}
          {orders.length > 0 && (
            <div className="space-y-4">
              {ALL_STATUSES.map((status) => {
                const count = orders.filter((o) => o.status === status).length;
                return (
                  <div key={status} className="flex items-center gap-3">
                    <span className="w-20 text-xs font-medium text-gray-600 capitalize">{status}</span>
                    <div className="flex-1 h-3 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${statusColor[status]} transition-all duration-500`}
                        style={{ width: `${(count / maxStatusCount) * 100}%` }}
                      />
                    </div>
                    <span className="w-8 text-xs font-bold text-gray-900 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Warehouse className="w-4 h-4 text-brand-blue" />
            Inventory Snapshot
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 text-center">
              <p className="text-lg font-bold text-gray-900">{loading ? "—" : totalSkus}</p>
              <p className="text-[10px] text-gray-500">Total SKUs</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 text-center">
              <p className="text-lg font-bold text-gray-900">
                {loading ? "—" : inventory.filter((i) => i.status === "in_stock").length}
              </p>
              <p className="text-[10px] text-gray-500">In Stock</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 text-center">
              <p className="text-lg font-bold text-gray-900">{loading ? "—" : lowStockCount}</p>
              <p className="text-[10px] text-gray-500">Low / Out of Stock</p>
            </div>
          </div>
        </div>

        {cancelledCount > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <p className="text-sm text-gray-600">
              <span className="font-bold text-gray-900">{cancelledCount}</span> order
              {cancelledCount === 1 ? "" : "s"} cancelled out of {orders.length} total.
            </p>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
