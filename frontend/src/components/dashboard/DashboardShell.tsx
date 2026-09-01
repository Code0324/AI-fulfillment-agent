"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  Menu,
  X,
  LogOut,
  CheckSquare,
} from "lucide-react";
import { fetchAmazonStatus, type AmazonConnectionStatus } from "@/lib/api";

const sidebarItems = [
  { icon: LayoutDashboard, label: "Overview", href: "/dashboard" },
  { icon: ShoppingCart, label: "Orders", href: "/dashboard/orders" },
  { icon: CheckSquare, label: "Approvals", href: "/dashboard/approvals" },
  { icon: Warehouse, label: "Inventory", href: "/dashboard/inventory" },
  { icon: Truck, label: "Fulfillment", href: "/dashboard/fulfillment" },
  { icon: FlaskConical, label: "Automation", href: "/dashboard/automation" },
  { icon: MapPin, label: "Addresses", href: "/dashboard/addresses" },
  { icon: BarChart3, label: "Analytics", href: "/dashboard/analytics" },
  { icon: Settings, label: "Settings", href: "/dashboard/settings" },
];

export default function DashboardShell({
  children,
  activeItem,
}: {
  children: React.ReactNode;
  activeItem?: string;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  const [amazonStatus, setAmazonStatus] = useState<AmazonConnectionStatus | null>(null);
  const [amazonStatusError, setAmazonStatusError] = useState(false);

  const loadAmazonStatus = useCallback(async () => {
    const result = await fetchAmazonStatus();
    if (result.ok) {
      setAmazonStatus(result.data);
      setAmazonStatusError(false);
    } else {
      setAmazonStatusError(true);
    }
  }, []);

  useEffect(() => {
    loadAmazonStatus();
  }, [loadAmazonStatus]);

  const currentActive =
    activeItem ||
    sidebarItems.find(
      (item) =>
        pathname === item.href ||
        (item.href !== "/dashboard" && pathname.startsWith(item.href))
    )?.label ||
    "Overview";

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:sticky top-0 left-0 z-50 h-screen w-60 bg-white border-r border-gray-200 flex flex-col transition-transform duration-300 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-4 border-b border-gray-100">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-brand-blue flex items-center justify-center group-hover:scale-105 transition-transform">
              <Package className="w-4 h-4 text-white" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-bold text-gray-900">
                Amazon<span className="text-brand-orange">FTE</span>
              </span>
              <span className="text-[9px] text-gray-500 -mt-0.5">Dashboard</span>
            </div>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="ml-auto lg:hidden p-1 rounded hover:bg-gray-100"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {sidebarItems.map(({ icon: Icon, label, href }) => {
            const isActive = currentActive === label;
            return (
              <Link
                key={label}
                href={href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-brand-blue/10 text-brand-blue shadow-sm"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-blue" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="px-3 py-4 border-t border-gray-100">
          <Link
            href="/"
            className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Back to Home
          </Link>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
            <h1 className="text-base font-bold text-gray-900">
              Amazon AI Fulfillment Assistant
            </h1>
            {amazonStatusError && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 border border-red-200 text-xs font-semibold text-red-700">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                Backend unreachable
              </span>
            )}
            {!amazonStatusError && amazonStatus?.configured && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-50 border border-green-200 text-xs font-semibold text-green-700">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                </span>
                SP-API Connected ({amazonStatus.environment})
              </span>
            )}
            {!amazonStatusError && amazonStatus && !amazonStatus.configured && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-yellow-50 border border-yellow-200 text-xs font-semibold text-yellow-700">
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                SP-API Not Configured
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
              title="Notifications (not yet implemented)"
              disabled
            >
              <Bell className="w-5 h-5 text-gray-500" />
            </button>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-blue/20 to-brand-blue/5 border border-brand-blue/20 flex items-center justify-center">
              <User className="w-4 h-4 text-brand-blue" />
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
