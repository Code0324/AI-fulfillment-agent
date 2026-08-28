"use client";

import { motion } from "framer-motion";
import {
  LayoutDashboard,
  ShoppingCart,
  Warehouse,
  Truck,
  FlaskConical,
  MapPin,
  BarChart3,
  Settings,
  Bell,
  User,
  Package,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/* Sidebar                                                                     */
/* -------------------------------------------------------------------------- */

const sidebarItems = [
  { icon: LayoutDashboard, label: "Overview", active: true },
  { icon: ShoppingCart, label: "Orders" },
  { icon: Warehouse, label: "Inventory" },
  { icon: Truck, label: "Fulfillment" },
  { icon: FlaskConical, label: "Automation" },
  { icon: MapPin, label: "Addresses" },
  { icon: BarChart3, label: "Analytics" },
  { icon: Settings, label: "Settings" },
];

/* -------------------------------------------------------------------------- */
/* Orders data                                                                 */
/* -------------------------------------------------------------------------- */

const recentOrders = [
  { id: "AMZ-29841", date: "Aug 24, 2026", status: "Fulfilled", items: 3, destination: "New York, NY" },
  { id: "AMZ-29840", date: "Aug 24, 2026", status: "Approved", items: 1, destination: "Los Angeles, CA" },
  { id: "AMZ-29839", date: "Aug 23, 2026", status: "Pending", items: 2, destination: "Chicago, IL" },
  { id: "AMZ-29838", date: "Aug 23, 2026", status: "Fulfilled", items: 5, destination: "Houston, TX" },
  { id: "AMZ-29837", date: "Aug 22, 2026", status: "Approved", items: 1, destination: "Phoenix, AZ" },
];

const statusStyles: Record<string, string> = {
  Pending: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
  Approved: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
  Fulfilled: "bg-green-500/10 text-green-400 border border-green-500/20",
};

/* -------------------------------------------------------------------------- */
/* Inventory data                                                              */
/* -------------------------------------------------------------------------- */

const inventoryStats = [
  { label: "Total SKUs", value: "2,842" },
  { label: "In Stock", value: "1,932", change: "+8.4%", up: true },
  { label: "Low Stock", value: "217", change: "-3.1%", up: false },
];

const lowStockItems = [
  { name: "Wireless Charger Pro", sku: "WC-PRO-01", stock: 8 },
  { name: "USB-C Hub 7-in-1", sku: "USB-HUB-07", stock: 12 },
  { name: "Laptop Stand Aluminum", sku: "LS-ALU-03", stock: 15 },
];

/* -------------------------------------------------------------------------- */
/* Fulfillment pipeline                                                        */
/* -------------------------------------------------------------------------- */

const pipelineSteps = [
  { label: "Received", pct: 100 },
  { label: "Processing", pct: 76 },
  { label: "Shipped", pct: 52 },
  { label: "Delivered", pct: 28 },
];

/* -------------------------------------------------------------------------- */
/* Today's summary                                                             */
/* -------------------------------------------------------------------------- */

const summaryCards = [
  { label: "Orders Received", value: "156", icon: ShoppingCart, color: "text-brand-orange" },
  { label: "Orders Fulfilled", value: "82", icon: Package, color: "text-green-400" },
  { label: "Fulfillment Rate", value: "92.6%", icon: BarChart3, color: "text-blue-400" },
];

/* -------------------------------------------------------------------------- */
/* Main Component                                                              */
/* -------------------------------------------------------------------------- */

export default function DashboardPreview() {
  return (
    <section id="dashboard" className="py-20 lg:py-28 bg-brand-navy relative">
      <div className="section-container">
        {/* Section heading */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center max-w-2xl mx-auto mb-12"
        >
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Powerful <span className="gradient-text">Dashboard</span>
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Manage your entire Amazon fulfillment operation from one place.
          </p>
        </motion.div>

        {/* Browser frame */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="relative rounded-2xl overflow-hidden border border-white/10 shadow-float bg-brand-navy-card"
        >
          {/* Browser traffic lights */}
          <div className="flex items-center gap-2 px-4 py-3 bg-brand-navy-light border-b border-white/5">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
              <div className="w-3 h-3 rounded-full bg-green-500/80" />
            </div>
            <div className="flex-1 flex justify-center">
              <div className="px-4 py-1 rounded-lg bg-white/5 text-xs text-gray-500 font-mono">
                amazon-ai-fulfillment.app/dashboard
              </div>
            </div>
          </div>

          {/* Dashboard content */}
          <div className="flex h-[600px]">
            {/* Sidebar */}
            <DashboardSidebar />

            {/* Main area */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Top bar */}
              <DashboardTopBar />

              {/* Content grid */}
              <div className="flex-1 p-4 overflow-auto space-y-4">
                <DashboardContent />
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Sidebar                                                                     */
/* -------------------------------------------------------------------------- */

function DashboardSidebar() {
  return (
    <div className="w-52 bg-brand-navy-light border-r border-white/5 p-3 hidden md:flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-6 px-2">
        <div className="w-7 h-7 rounded-lg bg-brand-orange/10 border border-brand-orange/20 flex items-center justify-center">
          <Package className="w-4 h-4 text-brand-orange" />
        </div>
        <span className="text-xs font-bold text-white">
          Amazon<span className="text-brand-orange">FTE</span>
        </span>
      </div>

      {/* Nav items */}
      <div className="space-y-0.5 flex-1">
        {sidebarItems.map(({ icon: Icon, label, active }) => (
          <div
            key={label}
            className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              active
                ? "bg-brand-orange/10 text-brand-orange"
                : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Top bar                                                                     */
/* -------------------------------------------------------------------------- */

function DashboardTopBar() {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-brand-navy-card/50">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold text-white">
          Amazon AI Fulfillment Assistant
        </span>
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20 text-[10px] font-semibold text-green-400">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          Connected to SP-API
        </span>
      </div>
      <div className="flex items-center gap-3">
        <button className="relative p-1.5 rounded-lg hover:bg-white/5 transition-colors">
          <Bell className="w-4 h-4 text-gray-400" />
          <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-brand-orange text-[8px] font-bold text-brand-navy flex items-center justify-center">
            3
          </span>
        </button>
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-orange/30 to-brand-orange/10 border border-brand-orange/20 flex items-center justify-center">
          <User className="w-3.5 h-3.5 text-brand-orange" />
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Content grid                                                                */
/* -------------------------------------------------------------------------- */

function DashboardContent() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      {/* Left column: Orders + Inventory */}
      <div className="xl:col-span-2 space-y-4">
        {/* Orders Table */}
        <div className="rounded-xl bg-white/5 border border-white/10 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-white">Recent Orders</h3>
            <button className="text-xs text-brand-orange hover:text-brand-orange-light transition-colors font-medium">
              View All →
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-white/5">
                  <th className="pb-2 font-medium">Order ID</th>
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Items</th>
                  <th className="pb-2 font-medium">Destination</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recentOrders.map((order) => (
                  <tr key={order.id} className="hover:bg-white/3 transition-colors">
                    <td className="py-2.5 font-mono text-gray-300">{order.id}</td>
                    <td className="py-2.5 text-gray-500">{order.date}</td>
                    <td className="py-2.5">
                      <span className={`status-badge ${statusStyles[order.status]}`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="py-2.5 text-gray-400">{order.items}</td>
                    <td className="py-2.5 text-gray-400">{order.destination}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Inventory Overview */}
        <div className="rounded-xl bg-white/5 border border-white/10 p-4">
          <h3 className="text-sm font-bold text-white mb-3">Inventory Overview</h3>
          <div className="grid grid-cols-3 gap-3 mb-4">
            {inventoryStats.map((stat) => (
              <div key={stat.label} className="rounded-lg bg-white/3 border border-white/5 p-3">
                <p className="text-[10px] text-gray-500 font-medium">{stat.label}</p>
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-lg font-bold text-white">{stat.value}</p>
                  {stat.change && (
                    <span className={`flex items-center gap-0.5 text-[10px] font-semibold ${stat.up ? "text-green-400" : "text-red-400"}`}>
                      {stat.up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {stat.change}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Low stock items */}
          <p className="text-xs font-semibold text-gray-400 mb-2">Top Low Stock Items</p>
          <div className="space-y-1.5">
            {lowStockItems.map((item) => (
              <div key={item.sku} className="flex items-center justify-between py-1.5 px-2 rounded-lg bg-white/3">
                <div>
                  <p className="text-xs text-gray-300 font-medium">{item.name}</p>
                  <p className="text-[10px] text-gray-500 font-mono">{item.sku}</p>
                </div>
                <span className="text-xs font-bold text-red-400">{item.stock} left</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right column: Pipeline + Summary */}
      <div className="space-y-4">
        {/* Fulfillment Pipeline */}
        <div className="rounded-xl bg-white/5 border border-white/10 p-4">
          <h3 className="text-sm font-bold text-white mb-4">Fulfillment Pipeline</h3>
          <div className="space-y-4">
            {pipelineSteps.map((step) => (
              <div key={step.label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-gray-400 font-medium">{step.label}</span>
                  <span className="text-xs font-bold text-white">{step.pct}%</span>
                </div>
                <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${step.pct}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 1, delay: 0.3, ease: "easeOut" }}
                    className="h-full rounded-full bg-gradient-to-r from-brand-orange to-brand-orange-light"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Today's Summary */}
        <div className="rounded-xl bg-white/5 border border-white/10 p-4">
          <h3 className="text-sm font-bold text-white mb-4">Today&apos;s Summary</h3>
          <div className="space-y-3">
            {summaryCards.map((card) => (
              <div key={card.label} className="flex items-center gap-3 p-3 rounded-lg bg-white/3 border border-white/5">
                <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center">
                  <card.icon className={`w-4 h-4 ${card.color}`} />
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 font-medium">{card.label}</p>
                  <p className="text-lg font-bold text-white">{card.value}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
