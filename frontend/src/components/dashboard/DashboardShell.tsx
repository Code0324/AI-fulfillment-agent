"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ShoppingCart,
  Truck,
  BarChart3,
  Settings,
  Bell,
  User,
  Package,
  Menu,
  X,
  LogOut,
} from "lucide-react";
import { fetchAmazonStatus, type AmazonConnectionStatus } from "@/lib/api";

const sidebarItems = [
  { icon: LayoutDashboard, label: "Overview", href: "/dashboard" },
  { icon: ShoppingCart, label: "Orders", href: "/dashboard/orders" },
  { icon: Truck, label: "Fulfillment", href: "/dashboard/fulfillment" },
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
    <div className="min-h-screen bg-luxury-cream flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:sticky top-0 left-0 z-50 h-screen w-60 bg-white border-r border-luxury-cream-dark flex flex-col transition-transform duration-300 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-6 border-b border-luxury-cream-dark">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-luxury-charcoal flex items-center justify-center group-hover:scale-105 transition-transform">
              <Package className="w-4 h-4 text-white" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-bold font-serif text-luxury-charcoal">
                E-Commerce
              </span>
              <span className="text-[9px] text-gray-500 -mt-0.5 font-medium">Platform</span>
            </div>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="ml-auto lg:hidden p-1 rounded hover:bg-luxury-cream-dark transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
          {sidebarItems.map(({ icon: Icon, label, href }) => {
            const isActive = currentActive === label;
            return (
              <Link
                key={label}
                href={href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-luxury-gold/10 text-luxury-charcoal border-l-2 border-luxury-gold"
                    : "text-gray-600 hover:bg-luxury-cream-dark hover:text-luxury-charcoal"
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
                {isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-luxury-gold" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="px-3 py-4 border-t border-luxury-cream-dark">
          <Link
            href="/"
            className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-500 hover:bg-luxury-cream-dark hover:text-luxury-charcoal transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Back to Home
          </Link>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-white border-b border-luxury-cream-dark px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg hover:bg-luxury-cream-dark transition-colors"
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
            <h1 className="text-base font-serif font-bold text-luxury-charcoal">
              Fulfillment Platform
            </h1>
            {amazonStatusError && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-50 border border-red-200 text-xs font-semibold text-red-700">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                Backend unreachable
              </span>
            )}
            {!amazonStatusError && amazonStatus?.configured && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-green-50 border border-green-200 text-xs font-semibold text-green-700">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
                </span>
                Connected
              </span>
            )}
            {!amazonStatusError && amazonStatus && !amazonStatus.configured && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-yellow-50 border border-yellow-200 text-xs font-semibold text-yellow-700">
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                Not Configured
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              className="relative p-2 rounded-lg hover:bg-luxury-cream-dark transition-colors text-gray-400"
              title="Notifications (not yet implemented)"
              disabled
            >
              <Bell className="w-5 h-5" />
            </button>
            <div className="w-8 h-8 rounded-full bg-luxury-gold/10 border border-luxury-gold/20 flex items-center justify-center">
              <User className="w-4 h-4 text-luxury-gold" />
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 sm:p-8 bg-luxury-cream">{children}</main>
      </div>
    </div>
  );
}
