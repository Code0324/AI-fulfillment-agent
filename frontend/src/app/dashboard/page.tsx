"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DashboardShell from "@/components/dashboard/DashboardShell";
import {
  fetchOrders,
  fetchInventory,
  type Order,
  type OrderStatus,
  type InventoryItem,
} from "@/lib/api";
import {
  ShoppingCart,
  Package,
  TrendingUp,
  Warehouse,
  AlertTriangle,
} from "lucide-react";

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
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-6" role="alert">
          {error}
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {statsCards.map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className={`w-10 h-10 rounded-lg ${stat.bg} flex items-center justify-center`}>
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
              </div>
            </div>
            <p className="text-2xl font-bold text-gray-900">{loading ? "—" : stat.value}</p>
            <p className="text-sm text-gray-500 mt-1">{stat.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left column: Orders + Inventory */}
        <div className="xl:col-span-2 space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900">Recent Orders</h2>
              <Link href="/dashboard/orders" className="text-sm text-brand-blue hover:text-brand-blue-dark font-medium transition-colors">
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
                    <tr className="text-left text-gray-500 border-b border-gray-100 bg-gray-50/50">
                      <th className="px-5 py-3 font-medium text-xs uppercase tracking-wide">Customer</th>
                      <th className="px-5 py-3 font-medium text-xs uppercase tracking-wide">Date</th>
                      <th className="px-5 py-3 font-medium text-xs uppercase tracking-wide">Status</th>
                      <th className="px-5 py-3 font-medium text-xs uppercase tracking-wide">Product</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {recentOrders.map((order) => (
                      <tr key={order.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-5 py-3">
                          <div className="font-medium text-gray-900">{order.customer_name}</div>
                          <div className="text-xs text-gray-400 font-mono">{order.id.slice(0, 8)}</div>
                        </td>
                        <td className="px-5 py-3 text-gray-500">{formatDate(order.created_at)}</td>
                        <td className="px-5 py-3">
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${statusStyles[order.status]}`}>
                            {order.status}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-gray-600">
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
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-gray-900">Inventory Overview</h2>
              <Link href="/dashboard/inventory" className="text-sm text-brand-blue hover:text-brand-blue-dark font-medium transition-colors">
                View All →
              </Link>
            </div>
            {!loading && lowStockItems.length === 0 && (
              <p className="text-sm text-gray-400">No low-stock items — inventory looks healthy.</p>
            )}
            {lowStockItems.length > 0 && (
              <>
                <p className="text-sm font-semibold text-gray-600 mb-2 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-orange-500" /> Low / Out of Stock
                </p>
                <div className="space-y-2">
                  {lowStockItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50">
                      <div>
                        <p className="text-sm text-gray-800 font-medium">{item.product_name}</p>
                        <p className="text-xs text-gray-400 font-mono">{item.sku}</p>
                      </div>
                      <span className="text-sm font-bold text-red-500">{item.available_quantity} left</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right column: Pipeline + Summary */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-base font-bold text-gray-900 mb-5">Order Status Breakdown</h2>
            <div className="space-y-5">
              {PIPELINE_STAGES.map((stage) => {
                const count = orders.filter((o) => o.status === stage.status).length;
                const pct = orders.length ? Math.round((count / orders.length) * 100) : 0;
                return (
                  <div key={stage.status}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600 font-medium">{stage.label}</span>
                      <span className="text-sm font-bold text-gray-900">{count}</span>
                    </div>
                    <div className="h-3 rounded-full bg-gray-100 overflow-hidden">
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

          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-base font-bold text-gray-900 mb-4">Summary</h2>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-100 flex items-center justify-center">
                  <ShoppingCart className="w-5 h-5 text-brand-orange" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-medium">Total Orders</p>
                  <p className="text-xl font-bold text-gray-900">{totalOrders}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-100 flex items-center justify-center">
                  <Package className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-medium">Delivered</p>
                  <p className="text-xl font-bold text-gray-900">{deliveredCount}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <div className="w-10 h-10 rounded-lg bg-white border border-gray-100 flex items-center justify-center">
                  <Warehouse className="w-5 h-5 text-brand-blue" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 font-medium">Inventory Reservation Rate</p>
                  <p className="text-xl font-bold text-gray-900">{reservationRate}%</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
