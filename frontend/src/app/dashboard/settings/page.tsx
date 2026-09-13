"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardShell from "@/components/dashboard/DashboardShell";
import AmazonSandboxStatus from "@/components/AmazonSandboxStatus";
import { fetchOrders, fetchInventory } from "@/lib/api";
import { Settings, User, Key, Bell, CreditCard, Shield, Save } from "lucide-react";

const tabs = [
  { id: "profile", label: "Profile", icon: User },
  { id: "api", label: "API Keys", icon: Key },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "security", label: "Security", icon: Shield },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("profile");
  const [saved, setSaved] = useState(false);
  const [orderCount, setOrderCount] = useState<number | null>(null);
  const [skuCount, setSkuCount] = useState<number | null>(null);

  const loadCounts = useCallback(async () => {
    const [ordersResult, inventoryResult] = await Promise.all([
      fetchOrders(1, 1),
      fetchInventory(1, 1),
    ]);
    if (ordersResult.ok) setOrderCount(ordersResult.data.total_items);
    if (inventoryResult.ok) setSkuCount(inventoryResult.data.total_items);
  }, []);

  useEffect(() => {
    if (activeTab === "billing") loadCounts();
  }, [activeTab, loadCounts]);

  const handleSave = () => {
    // No user/settings backend exists yet — this is a UI-only preview and
    // nothing is actually persisted. See the note next to the button below.
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <DashboardShell>
      <div className="max-w-4xl space-y-8">
        <div>
          <h1 className="text-3xl font-serif font-bold text-luxury-charcoal mb-2 flex items-center gap-3">
            <Settings className="w-8 h-8 text-luxury-gold" />
            Settings
          </h1>
          <p className="text-sm text-gray-500">Manage account and integration settings.</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 bg-luxury-cream-dark rounded-lg p-1.5 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? "bg-white text-luxury-charcoal shadow-subtle"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-white rounded-lg border border-gray-100 p-8 shadow-subtle">
          {activeTab === "profile" && (
            <div className="space-y-6">
              <h3 className="text-base font-semibold text-luxury-charcoal">Profile Settings</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">Full Name</label>
                  <input type="text" defaultValue="John Seller" className="w-full px-4 py-2.5 text-sm rounded-lg border border-gray-200 focus:border-luxury-gold focus:ring-2 focus:ring-luxury-gold/20 outline-none bg-white" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                  <input type="email" defaultValue="john@seller.com" className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-brand-blue focus:ring-1 focus:ring-brand-blue/20 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Company</label>
                  <input type="text" defaultValue="SellerCo Inc." className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-brand-blue focus:ring-1 focus:ring-brand-blue/20 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Timezone</label>
                  <select className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-brand-blue focus:ring-1 focus:ring-brand-blue/20 outline-none bg-white">
                    <option>UTC-5 (Eastern)</option>
                    <option>UTC-6 (Central)</option>
                    <option>UTC-7 (Mountain)</option>
                    <option>UTC-8 (Pacific)</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeTab === "api" && (
            <div className="space-y-5">
              <h3 className="text-sm font-bold text-gray-900">Amazon SP-API Configuration</h3>
              <p className="text-xs text-gray-500">
                Credentials are configured via server-side environment variables
                (<code className="font-mono">AMAZON_LWA_CLIENT_ID</code>,{" "}
                <code className="font-mono">AMAZON_LWA_CLIENT_SECRET</code>,{" "}
                <code className="font-mono">AMAZON_LWA_REFRESH_TOKEN</code>) — they are never
                entered or displayed in the browser. The status below reflects the
                backend&apos;s actual connection state.
              </p>
              <AmazonSandboxStatus />
            </div>
          )}

          {activeTab === "notifications" && (
            <div className="space-y-5">
              <h3 className="text-sm font-bold text-gray-900">Notification Preferences</h3>
              <div className="space-y-3">
                {[
                  { label: "Order received alerts", desc: "Get notified when new orders come in", enabled: true },
                  { label: "Fulfillment complete", desc: "Notify when orders are fulfilled", enabled: true },
                  { label: "Low stock warnings", desc: "Alert when inventory drops below threshold", enabled: true },
                  { label: "Address validation failures", desc: "Notify on failed address checks", enabled: false },
                  { label: "Daily summary report", desc: "Receive daily performance email", enabled: true },
                  { label: "Weekly analytics digest", desc: "Weekly trends and insights email", enabled: false },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-100">
                    <div>
                      <p className="text-xs font-medium text-gray-800">{item.label}</p>
                      <p className="text-[10px] text-gray-400">{item.desc}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={item.enabled} className="sr-only peer" />
                      <div className="w-9 h-5 bg-gray-200 peer-focus:ring-2 peer-focus:ring-brand-blue/20 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-brand-blue" />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "billing" && (
            <div className="space-y-5">
              <h3 className="text-sm font-bold text-gray-900">Billing & Plan</h3>
              <div className="p-4 rounded-xl bg-blue-50 border border-blue-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-bold text-gray-900">Professional Plan</p>
                    <p className="text-xs text-gray-500">$49/month · Next billing: Sep 25, 2026</p>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-green-100 text-green-700 text-xs font-semibold">Active</span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 text-center">
                  <p className="text-lg font-bold text-gray-900">{orderCount ?? "—"}</p>
                  <p className="text-[10px] text-gray-500">Total orders</p>
                </div>
                <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 text-center">
                  <p className="text-lg font-bold text-gray-900">{skuCount ?? "—"}</p>
                  <p className="text-[10px] text-gray-500">SKUs managed</p>
                </div>
                <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 text-center">
                  <p className="text-lg font-bold text-gray-900">5,000</p>
                  <p className="text-[10px] text-gray-500">Order limit</p>
                </div>
              </div>
              <p className="text-[10px] text-gray-400">
                Billing and plan management are illustrative — this build has no payment backend.
              </p>
            </div>
          )}

          {activeTab === "security" && (
            <div className="space-y-5">
              <h3 className="text-sm font-bold text-gray-900">Security Settings</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <div>
                    <p className="text-xs font-medium text-gray-800">Two-Factor Authentication</p>
                    <p className="text-[10px] text-gray-400">Add an extra layer of security to your account</p>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-green-100 text-green-700 text-xs font-semibold">Enabled</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <div>
                    <p className="text-xs font-medium text-gray-800">Session Timeout</p>
                    <p className="text-[10px] text-gray-400">Auto logout after inactivity</p>
                  </div>
                  <select className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-white">
                    <option>30 minutes</option>
                    <option>1 hour</option>
                    <option>4 hours</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Change Password</label>
                  <input type="password" placeholder="New password" className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-brand-blue focus:ring-1 focus:ring-brand-blue/20 outline-none" />
                </div>
              </div>
            </div>
          )}

          {/* Save button — hidden on the API tab, which has nothing to save
              (credentials are server-side env vars, not editable here) */}
          {activeTab !== "api" && (
            <div className="flex items-center justify-end gap-3 mt-6 pt-5 border-t border-gray-100">
              <span className="text-[10px] text-gray-400">Preview only — not persisted to a backend</span>
              {saved && (
                <span className="text-xs text-green-600 font-medium animate-pulse">✓ Saved (locally, this session only)</span>
              )}
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-brand-blue rounded-lg hover:bg-brand-blue-dark transition-colors"
              >
                <Save className="w-3.5 h-3.5" />
                Save Changes
              </button>
            </div>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}
