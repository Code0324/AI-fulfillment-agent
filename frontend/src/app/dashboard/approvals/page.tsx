"use client";

import { useCallback, useEffect, useState } from "react";
import DashboardShell from "@/components/dashboard/DashboardShell";
import {
  approveFulfillment,
  fetchDashboardSummary,
  rejectFulfillment,
  type DashboardApprovalItem,
} from "@/lib/api";
import { AlertTriangle } from "lucide-react";

export default function ApprovalsPage() {
  const [items, setItems] = useState<DashboardApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchDashboardSummary();
    if (result.ok) {
      setItems(result.data.approval_queue);
      setError(null);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAction(workflowId: string, action: "approve" | "reject") {
    setPendingId(workflowId);
    const fn = action === "approve" ? approveFulfillment : rejectFulfillment;
    const result = await fn(workflowId);
    if (result.ok) {
      setItems((prev) => prev.filter((i) => i.workflow_id !== workflowId));
    } else {
      setError(result.error);
    }
    setPendingId(null);
  }

  return (
    <DashboardShell activeItem="Approvals">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-gray-900">Approval Queue</h1>
        <p className="text-sm text-gray-500 mt-1">
          The agent has prepared these orders for Amazon checkout. Nothing final happens until you approve or reject.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-6" role="alert">
          {error}
        </div>
      )}

      {loading && (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">Loading…</div>
      )}

      {!loading && items.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
          Nothing needs your approval right now.
        </div>
      )}

      <div className="space-y-4">
        {items.map((item) => (
          <div key={item.workflow_id} className="bg-white border border-yellow-200 rounded-xl overflow-hidden">
            <div className="bg-yellow-50 border-b border-yellow-200 px-5 py-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-700" />
              <span className="text-sm font-semibold text-yellow-800">HUMAN APPROVAL REQUIRED</span>
              <span className="ml-auto text-xs font-mono text-yellow-700">{item.current_state}</span>
            </div>

            <div className="p-5 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-500 font-medium">TikTok Order ID</span>
                <p className="text-gray-900 mt-0.5 font-mono">{item.tiktok_order_id ?? "—"}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">TikTok SKU</span>
                <p className="text-gray-900 mt-0.5 font-mono">{item.tiktok_sku ?? "—"}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Amazon SKU</span>
                <p className="text-gray-900 mt-0.5 font-mono">{item.amazon_sku || "—"}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">ASIN</span>
                <p className="text-gray-900 mt-0.5 font-mono">{item.asin ?? "—"}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Product</span>
                <p className="text-gray-900 mt-0.5">{item.product_name}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Variation</span>
                <p className="text-gray-900 mt-0.5">{item.variation ?? "—"}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Quantity</span>
                <p className="text-gray-900 mt-0.5">{item.quantity}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Price</span>
                <p className="text-gray-900 mt-0.5">
                  {item.price != null ? `$${item.price.toFixed(2)}` : "—"}
                  {item.total != null && <span className="text-gray-400"> (total ${item.total.toFixed(2)})</span>}
                </p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Customer</span>
                <p className="text-gray-900 mt-0.5">{item.customer_name}</p>
              </div>
              <div className="sm:col-span-2">
                <span className="text-gray-500 font-medium">Shipping Address</span>
                <p className="text-gray-900 mt-0.5">{item.shipping_address}</p>
              </div>
              <div>
                <span className="text-gray-500 font-medium">Integration Mode</span>
                <p className="mt-0.5">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                      item.integration_mode === "REAL"
                        ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-gray-100 text-gray-600 border border-gray-200"
                    }`}
                  >
                    {item.integration_mode}
                  </span>
                </p>
              </div>
            </div>

            <div className="px-5 pb-5 flex gap-3">
              <button
                onClick={() => handleAction(item.workflow_id, "reject")}
                disabled={pendingId === item.workflow_id}
                className="px-4 py-2 rounded-md text-sm font-medium bg-white border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={() => handleAction(item.workflow_id, "approve")}
                disabled={pendingId === item.workflow_id}
                className="px-4 py-2 rounded-md text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
              >
                {pendingId === item.workflow_id ? "Working…" : "Approve & Continue"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </DashboardShell>
  );
}
