"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// API base
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MockAmazonOrder {
  amazon_order_id: string;
  internal_order_id: string;
  sku: string;
  product_name: string;
  quantity: number;
  customer_name: string;
  status: string;
  inventory_reserved: boolean;
  fulfillment_status: string | null;
  source: string;
}

interface ImportResult {
  imported: number;
  skipped_duplicates: number;
  total_amazon_orders: number;
  imported_order_ids: string[];
}

interface FulfillmentResult {
  amazon_order_id: string;
  workflow_id: string;
  status: string;
  steps_completed: number;
  total_steps: number;
}

// ---------------------------------------------------------------------------
// Status badge helper
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
        Not started
      </span>
    );
  }

  const config: Record<string, { bg: string; text: string; label: string }> = {
    pending: { bg: "bg-yellow-50", text: "text-yellow-700", label: "Pending" },
    running: { bg: "bg-blue-50", text: "text-blue-700", label: "Running" },
    waiting_approval: { bg: "bg-orange-50", text: "text-orange-700", label: "Awaiting Approval" },
    approved: { bg: "bg-purple-50", text: "text-purple-700", label: "Approved" },
    completed: { bg: "bg-green-50", text: "text-green-700", label: "Completed" },
    failed: { bg: "bg-red-50", text: "text-red-700", label: "Failed" },
    cancelled: { bg: "bg-gray-100", text: "text-gray-600", label: "Cancelled" },
    expired: { bg: "bg-red-50", text: "text-red-600", label: "Expired" },
    not_started: { bg: "bg-gray-100", text: "text-gray-500", label: "Not started" },
  };

  const c = config[status] ?? { bg: "bg-gray-100", text: "text-gray-600", label: status };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
      {c.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MockAmazonOrders() {
  const [orders, setOrders] = useState<MockAmazonOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [fulfilling, setFulfilling] = useState<string | null>(null);

  // Load imported orders
  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/mock-amazon/orders`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: MockAmazonOrder[] = await res.json();
      setOrders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load orders");
    }
    setLoading(false);
  }, []);

  // Import mock orders
  const handleImport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/mock-amazon/import`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      const data: ImportResult = await res.json();
      setImportResult(data);
      await loadOrders();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    }
    setLoading(false);
  }, [loadOrders]);

  // Start fulfillment for one order
  const handleFulfill = useCallback(async (amazonOrderId: string) => {
    setFulfilling(amazonOrderId);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/mock-amazon/${amazonOrderId}/fulfill`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      await loadOrders();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fulfillment failed");
    }
    setFulfilling(null);
  }, [loadOrders]);

  // Start all pending fulfillments
  const handleFulfillAll = useCallback(async () => {
    const pendingOrders = orders.filter(
      (o) => !o.fulfillment_status || o.fulfillment_status === "not_started",
    );
    for (const order of pendingOrders) {
      await handleFulfill(order.amazon_order_id);
    }
  }, [orders, handleFulfill]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <section aria-label="Mock Amazon Orders" className="space-y-4">
      {/* ---- Demo Mode Banner ---- */}
      <div className="bg-amber-50 border-2 border-amber-300 rounded-lg px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-amber-200 text-amber-800 text-lg font-bold">
              ⚠
            </span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-amber-800 uppercase tracking-wide">
              Sandbox Mode — Mock Amazon Data Only
            </h3>
            <ul className="mt-1.5 text-xs text-amber-700 space-y-0.5">
              <li>• NO REAL AMAZON CONNECTION</li>
              <li>• NO REAL CUSTOMER DATA</li>
              <li>• NO REAL PURCHASES</li>
              <li>• ALL ORDER DATA IS SYNTHETIC</li>
            </ul>
          </div>
        </div>
      </div>

      {/* ---- Header ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Mock Amazon Orders
          </h2>
          <p className="text-sm text-gray-500">
            Source: <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">MOCK_AMAZON</span>{" "}
            &nbsp;|&nbsp; Environment:{" "}
            <span className="font-mono text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">SANDBOX</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleImport}
            disabled={loading}
            className="px-4 py-2 rounded-md text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Loading…" : "Load Mock Orders"}
          </button>
          {orders.length > 0 && (
            <button
              onClick={handleFulfillAll}
              disabled={loading}
              className="px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Start Fulfillment
            </button>
          )}
        </div>
      </div>

      {/* ---- Import result ---- */}
      {importResult && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
          Imported <strong>{importResult.imported}</strong> orders
          {importResult.skipped_duplicates > 0 && (
            <> · Skipped <strong>{importResult.skipped_duplicates}</strong> duplicates</>
          )}
          {" "}· Total available: {importResult.total_amazon_orders}
        </div>
      )}

      {/* ---- Error ---- */}
      {error && (
        <div
          className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm"
          role="alert"
        >
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-3 text-red-500 hover:text-red-700 font-bold"
          >
            ×
          </button>
        </div>
      )}

      {/* ---- Orders table ---- */}
      {loading && orders.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
          Loading…
        </div>
      )}

      {!loading && orders.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
          No mock Amazon orders imported yet. Click &ldquo;Load Mock Orders&rdquo; to import synthetic data.
        </div>
      )}

      {orders.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                <th className="px-4 py-3">Amazon Order ID</th>
                <th className="px-4 py-3">SKU</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3 text-center">Qty</th>
                <th className="px-4 py-3">Address</th>
                <th className="px-4 py-3">Inventory</th>
                <th className="px-4 py-3">Fulfillment</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {orders.map((order) => {
                const needsFulfillment =
                  !order.fulfillment_status ||
                  order.fulfillment_status === "not_started";
                return (
                  <tr key={order.amazon_order_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-mono text-xs font-medium text-gray-900">
                        {order.amazon_order_id}
                      </div>
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        Source: {order.source}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{order.sku}</td>
                    <td className="px-4 py-3 text-gray-700">{order.product_name}</td>
                    <td className="px-4 py-3 text-center">{order.quantity}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      <span className={order.status === "pending" ? "text-gray-400" : ""}>
                        {order.customer_name}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {order.inventory_reserved ? (
                        <span className="text-green-600 text-xs font-medium">✓ Reserved</span>
                      ) : (
                        <span className="text-gray-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={order.fulfillment_status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      {needsFulfillment && (
                        <button
                          onClick={() => handleFulfill(order.amazon_order_id)}
                          disabled={fulfilling === order.amazon_order_id}
                          className="px-3 py-1 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                        >
                          {fulfilling === order.amazon_order_id
                            ? "Starting…"
                            : "Start"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
