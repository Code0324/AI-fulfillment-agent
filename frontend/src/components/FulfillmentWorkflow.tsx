"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approveFulfillment,
  cancelFulfillment,
  fetchFulfillmentWorkflows,
  fetchOrders,
  rejectFulfillment,
  retryFulfillment,
  startFulfillment,
  type FulfillmentWorkflow as FulfillmentWorkflowType,
  type FulfillmentStep,
  type Order,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_META: Record<
  string,
  { label: string; dot: string; bg: string; text: string }
> = {
  pending: {
    label: "Pending",
    dot: "bg-gray-400",
    bg: "bg-gray-50",
    text: "text-gray-700",
  },
  running: {
    label: "Running",
    dot: "bg-blue-400",
    bg: "bg-blue-50",
    text: "text-blue-700",
  },
  waiting_approval: {
    label: "Awaiting Approval",
    dot: "bg-yellow-400",
    bg: "bg-yellow-50",
    text: "text-yellow-700",
  },
  approved: {
    label: "Approved",
    dot: "bg-green-400",
    bg: "bg-green-50",
    text: "text-green-700",
  },
  completed: {
    label: "Completed",
    dot: "bg-green-400",
    bg: "bg-green-50",
    text: "text-green-700",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-400",
    bg: "bg-red-50",
    text: "text-red-700",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-gray-400",
    bg: "bg-gray-50",
    text: "text-gray-500",
  },
  expired: {
    label: "Expired",
    dot: "bg-orange-400",
    bg: "bg-orange-50",
    text: "text-orange-700",
  },
};

const STEP_STATUS_META: Record<
  string,
  { label: string; icon: string; color: string }
> = {
  pending: { label: "Pending", icon: "○", color: "text-gray-400" },
  running: { label: "Running", icon: "◉", color: "text-blue-500" },
  completed: { label: "Done", icon: "✓", color: "text-green-500" },
  failed: { label: "Failed", icon: "✗", color: "text-red-500" },
  skipped: { label: "Skipped", icon: "—", color: "text-gray-400" },
  waiting_approval: {
    label: "Awaiting Approval",
    icon: "⏳",
    color: "text-yellow-500",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FulfillmentWorkflowComponent() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [workflows, setWorkflows] = useState<FulfillmentWorkflowType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<string | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<string>("");
  const [shippingMethod, setShippingMethod] = useState("standard");
  const [expandedWorkflow, setExpandedWorkflow] = useState<string | null>(null);

  // ---------------------------------------------------------------
  // Load data
  // ---------------------------------------------------------------

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [ordersResult, workflowsResult] = await Promise.all([
      fetchOrders(1, 100),
      fetchFulfillmentWorkflows(1, 50),
    ]);
    if (ordersResult.ok) setOrders(ordersResult.data.items);
    if (workflowsResult.ok) setWorkflows(workflowsResult.data.items);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ---------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------

  async function handleStartFulfillment() {
    if (!selectedOrder) return;
    setStarting(selectedOrder);
    setError(null);
    const result = await startFulfillment(selectedOrder, shippingMethod);
    if (result.ok) {
      setWorkflows((prev) => [result.data, ...prev]);
      setSelectedOrder("");
    } else {
      setError(result.error);
    }
    setStarting(null);
  }

  async function handleApprove(workflowId: string) {
    setError(null);
    const result = await approveFulfillment(workflowId);
    if (result.ok) {
      setWorkflows((prev) =>
        prev.map((w) => (w.id === workflowId ? result.data : w))
      );
    } else {
      setError(result.error);
    }
  }

  async function handleReject(workflowId: string) {
    setError(null);
    const result = await rejectFulfillment(workflowId);
    if (result.ok) {
      setWorkflows((prev) =>
        prev.map((w) => (w.id === workflowId ? result.data : w))
      );
    } else {
      setError(result.error);
    }
  }

  async function handleCancel(workflowId: string) {
    setError(null);
    const result = await cancelFulfillment(workflowId);
    if (result.ok) {
      setWorkflows((prev) =>
        prev.map((w) => (w.id === workflowId ? result.data : w))
      );
    } else {
      setError(result.error);
    }
  }

  async function handleRetry(workflowId: string) {
    setError(null);
    const result = await retryFulfillment(workflowId);
    if (result.ok) {
      setWorkflows((prev) =>
        prev.map((w) => (w.id === workflowId ? result.data : w))
      );
    } else {
      setError(result.error);
    }
  }

  // ---------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------

  function renderStepTimeline(steps: FulfillmentStep[]) {
    return (
      <div className="space-y-2">
        {steps.map((step, i) => {
          const meta = STEP_STATUS_META[step.status] || STEP_STATUS_META.pending;
          return (
            <div
              key={i}
              className="flex items-center gap-3 text-sm"
            >
              <span className={`w-5 text-center ${meta.color} font-mono`}>
                {meta.icon}
              </span>
              <span className="flex-1">
                <span className="font-medium text-gray-700">
                  {step.description}
                </span>
                {step.error && (
                  <span className="ml-2 text-red-600 text-xs">
                    — {step.error}
                  </span>
                )}
                {step.result && step.status === "completed" && (
                  <span className="ml-2 text-green-600 text-xs">
                    — {step.result.length > 60 ? step.result.slice(0, 60) + "…" : step.result}
                  </span>
                )}
              </span>
              <span className={`text-xs ${meta.color}`}>{meta.label}</span>
            </div>
          );
        })}
      </div>
    );
  }

  // ---------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------

  // Orders eligible for fulfillment (pending, no active workflow)
  const activeWorkflowOrderIds = new Set(
    workflows
      .filter((w) => ["pending", "running", "waiting_approval"].includes(w.status))
      .map((w) => w.order_id)
  );
  const eligibleOrders = orders.filter(
    (o) =>
      o.status === "pending" &&
      o.sku &&
      !activeWorkflowOrderIds.has(o.id)
  );

  return (
    <section aria-label="Fulfillment Workflow" className="space-y-6">
      {/* Error banner */}
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

      {/* Sandbox banner */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg px-4 py-3 text-sm text-purple-800 font-medium text-center">
        📦 SANDBOX — SYNTHETIC DATA ONLY — NO REAL AMAZON OR SUPPLIER CONNECTION
      </div>

      {/* Start fulfillment */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Start Fulfillment
        </h2>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-xs text-gray-500 block mb-1">
              Select Order
            </label>
            <select
              value={selectedOrder}
              onChange={(e) => setSelectedOrder(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Choose an order…</option>
              {eligibleOrders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.customer_name} — {o.product_name} (SKU: {o.sku})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">
              Shipping
            </label>
            <select
              value={shippingMethod}
              onChange={(e) => setShippingMethod(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="standard">Standard</option>
              <option value="express">Express</option>
              <option value="priority">Priority</option>
            </select>
          </div>
          <button
            onClick={handleStartFulfillment}
            disabled={!selectedOrder || starting !== null}
            className="px-5 py-2 rounded-md text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {starting ? "Starting…" : "Start Fulfillment"}
          </button>
        </div>
        {eligibleOrders.length === 0 && !loading && (
          <p className="text-xs text-gray-400 mt-2">
            No eligible orders. Create a pending order with a SKU first.
          </p>
        )}
      </div>

      {/* Workflow list */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Fulfillment Workflows
          </h2>
          <button
            onClick={loadData}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            Refresh
          </button>
        </div>

        {loading && (
          <div className="text-center text-gray-400 py-8">
            Loading workflows…
          </div>
        )}

        {!loading && workflows.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            No workflows yet. Start a fulfillment above to begin.
          </div>
        )}

        {!loading && workflows.length > 0 && (
          <div className="space-y-3">
            {workflows.map((wf) => {
              const meta = STATUS_META[wf.status] || STATUS_META.pending;
              const isExpanded = expandedWorkflow === wf.id;
              const completedSteps = wf.steps.filter(
                (s) => s.status === "completed"
              ).length;
              const totalSteps = wf.steps.length;

              return (
                <div
                  key={wf.id}
                  className="p-4 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${meta.bg} ${meta.text}`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${meta.dot}`}
                          />
                          {meta.label}
                        </span>
                        <span className="text-xs text-gray-400">
                          {completedSteps}/{totalSteps} steps
                        </span>
                        <span className="text-xs text-gray-400 font-mono">
                          {wf.id.slice(0, 8)}…
                        </span>
                      </div>
                      <div className="text-sm text-gray-700">
                        Order: {wf.order_id.slice(0, 8)}…
                        {wf.supplier_payload && (
                          <>
                            {" — "}
                            {wf.supplier_payload.product_name} (
                            {wf.supplier_payload.sku})
                          </>
                        )}
                      </div>
                      {wf.error_message && (
                        <div className="text-xs text-red-600 mt-1">
                          {wf.error_message}
                        </div>
                      )}
                      {wf.confirmation && (
                        <div className="text-xs text-green-600 mt-1 font-medium">
                          ✓ Confirmation: {wf.confirmation.confirmation_id} —{" "}
                          {wf.confirmation.estimated_delivery}
                        </div>
                      )}
                      {wf.retry_count > 0 && (
                        <div className="text-xs text-blue-600 mt-1">
                          Retry attempt #{wf.retry_count}
                        </div>
                      )}
                      {wf.approval_expires_at && wf.status === "waiting_approval" && (
                        <div className="text-xs text-orange-600 mt-1">
                          Approval expires: {new Date(wf.approval_expires_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      {wf.status === "waiting_approval" && (
                        <>
                          <button
                            onClick={() => handleApprove(wf.id)}
                            className="px-3 py-1.5 rounded text-xs font-medium text-white bg-green-600 hover:bg-green-700 transition-colors"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(wf.id)}
                            className="px-3 py-1.5 rounded text-xs font-medium text-white bg-red-600 hover:bg-red-700 transition-colors"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {(wf.status === "waiting_approval" ||
                        wf.status === "running") && (
                        <button
                          onClick={() => handleCancel(wf.id)}
                          className="px-3 py-1.5 rounded text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
                        >
                          Cancel
                        </button>
                      )}
                      {(wf.status === "failed" ||
                        wf.status === "expired" ||
                        wf.status === "cancelled") && (
                        <button
                          onClick={() => handleRetry(wf.id)}
                          className="px-3 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors"
                        >
                          Retry
                        </button>
                      )}
                      <button
                        onClick={() =>
                          setExpandedWorkflow(isExpanded ? null : wf.id)
                        }
                        className="px-3 py-1.5 rounded text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
                      >
                        {isExpanded ? "Hide" : "Details"}
                      </button>
                    </div>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      {renderStepTimeline(wf.steps)}

                      {wf.supplier_payload && (
                        <div className="mt-4 p-3 bg-white rounded border border-gray-200">
                          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                            Supplier Order
                          </h4>
                          <div className="grid grid-cols-2 gap-2 text-sm">
                            <div>
                              <span className="text-gray-500">SKU:</span>{" "}
                              {wf.supplier_payload.sku}
                            </div>
                            <div>
                              <span className="text-gray-500">Product:</span>{" "}
                              {wf.supplier_payload.product_name}
                            </div>
                            <div>
                              <span className="text-gray-500">Qty:</span>{" "}
                              {wf.supplier_payload.quantity}
                            </div>
                            <div>
                              <span className="text-gray-500">Shipping:</span>{" "}
                              {wf.supplier_payload.shipping_method}
                            </div>
                            <div className="col-span-2">
                              <span className="text-gray-500">Address:</span>{" "}
                              {wf.supplier_payload.first_name}{" "}
                              {wf.supplier_payload.last_name},{" "}
                              {wf.supplier_payload.address_line_1},{" "}
                              {wf.supplier_payload.city},{" "}
                              {wf.supplier_payload.state}{" "}
                              {wf.supplier_payload.postal_code}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
