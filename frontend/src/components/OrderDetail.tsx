"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approveFulfillment,
  createSkuMapping,
  fetchFulfillmentWorkflows,
  fetchOrder,
  rejectFulfillment,
  retryFulfillment,
  startFulfillment,
  updateOrderStatus,
  type FulfillmentWorkflow,
  type Order,
  type OrderStatus,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Business-level automation checklist — translates the internal 13-step
// workflow into the plain-language stages a non-technical user cares
// about. The internal step names/timeline are kept below (collapsible)
// for anyone who wants the detail, but this is the primary view.
// ---------------------------------------------------------------------------

function stepDone(workflow: FulfillmentWorkflow, name: string): boolean {
  const step = workflow.steps.find((s) => s.name === name);
  return step?.status === "completed";
}

type StageState = "done" | "current" | "pending";

interface BusinessStage {
  label: string;
  status: StageState;
  warning?: string;
}

/** Business-state checklist matching the canonical workflow:
 * TikTok Order Received -> Order Data Validated -> Google Sheet Updated ->
 * SKU Matched -> Amazon Product Verified -> Amazon Order Prepared ->
 * Human Approval Required -> Final Supported Action -> Confirmation.
 * These are statuses, not manual "Next" buttons — everything up to the
 * approval gate happens automatically; the approve/reject buttons that
 * drive the last three rows live in the panel below this checklist. */
function businessStages(order: Order, workflow: FulfillmentWorkflow | null): BusinessStage[] {
  const stages: BusinessStage[] = [
    { label: "TikTok Order Received", status: "done" },
    {
      label: "Order Data Validated",
      status: workflow && stepDone(workflow, "validate_order") ? "done" : "pending",
    },
  ];

  if (order.source === "TIKTOK") {
    stages.push({
      label: "Google Sheet Updated",
      status: order.sheet_synced_at ? "done" : "pending",
      warning: order.sheet_sync_error ? "Sheet sync failed — see below" : undefined,
    });
  }

  const skuMatched = workflow ? stepDone(workflow, "resolve_sku_mapping") : false;
  stages.push({
    label: "SKU Matched",
    status: skuMatched ? "done" : "pending",
    warning:
      workflow?.sku_mapping_status && !["matched", "not_required"].includes(workflow.sku_mapping_status)
        ? `SKU mapping needs review (${workflow.sku_mapping_status})`
        : undefined,
  });

  stages.push({
    label: "Amazon Product Verified",
    status: workflow?.marketplace_integration_configured ? "done" : "pending",
    warning:
      workflow && !workflow.marketplace_integration_configured
        ? "Amazon integration not configured — using sandbox"
        : undefined,
  });

  stages.push({
    label: "Amazon Order Prepared",
    status: workflow && stepDone(workflow, "validate_provider_order") ? "done" : "pending",
  });

  const isTerminal = workflow?.status === "completed";
  stages.push({
    label: "Human Approval Required",
    status: isTerminal ? "done" : workflow?.status === "waiting_approval" ? "current" : "pending",
  });
  stages.push({
    label: "Final Supported Action",
    status: isTerminal ? "done" : "pending",
  });
  stages.push({
    label: "Confirmation",
    status: workflow?.confirmation ? "done" : "pending",
  });

  return stages;
}

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const ORDER_STATUS_META: Record<
  OrderStatus,
  { label: string; dot: string; bg: string; text: string; step: number }
> = {
  pending:     { label: "Pending",     dot: "bg-yellow-400", bg: "bg-yellow-50", text: "text-yellow-700", step: 0 },
  processing:  { label: "Processing",  dot: "bg-blue-400",   bg: "bg-blue-50",   text: "text-blue-700",   step: 1 },
  shipped:     { label: "Shipped",     dot: "bg-purple-400", bg: "bg-purple-50", text: "text-purple-700", step: 2 },
  delivered:   { label: "Delivered",   dot: "bg-green-400",  bg: "bg-green-50",  text: "text-green-700",  step: 3 },
  cancelled:   { label: "Cancelled",   dot: "bg-red-400",    bg: "bg-red-50",    text: "text-red-700",    step: -1 },
};

const WORKFLOW_STEPS: OrderStatus[] = ["pending", "processing", "shipped", "delivered"];

// Valid transitions from current status
const VALID_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending:    ["processing", "cancelled"],
  processing: ["shipped", "cancelled"],
  shipped:    ["delivered", "cancelled"],
  delivered:  [],
  cancelled:  [],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface OrderDetailProps {
  orderId: string;
  onClose: () => void;
  onStatusChanged: (updated: Order) => void;
}

export default function OrderDetail({ orderId, onClose, onStatusChanged }: OrderDetailProps) {
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const [workflow, setWorkflow] = useState<FulfillmentWorkflow | null>(null);
  const [workflowActionPending, setWorkflowActionPending] = useState(false);
  const [skuForm, setSkuForm] = useState({ amazon_sku: "", asin: "" });
  const [resolvingSku, setResolvingSku] = useState(false);

  const loadWorkflow = useCallback(async (id: string) => {
    const result = await fetchFulfillmentWorkflows(1, 100);
    if (result.ok) {
      const match = result.data.items.find((w) => w.order_id === id);
      setWorkflow(match ?? null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchOrder(orderId).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setOrder(result.data);
        loadWorkflow(result.data.id);
      } else {
        setError(result.error);
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [orderId, loadWorkflow]);

  async function handleTransition(newStatus: OrderStatus) {
    if (!order) return;
    setUpdating(true);
    setError(null);
    const result = await updateOrderStatus(order.id, newStatus);
    if (result.ok) {
      setOrder(result.data);
      onStatusChanged(result.data);
    } else {
      setError(result.error);
    }
    setUpdating(false);
  }

  async function handleStartFulfillment() {
    if (!order) return;
    setWorkflowActionPending(true);
    setError(null);
    const result = await startFulfillment(order.id);
    if (result.ok) setWorkflow(result.data);
    else setError(result.error);
    setWorkflowActionPending(false);
  }

  async function handleWorkflowAction(action: "approve" | "reject" | "retry") {
    if (!workflow) return;
    setWorkflowActionPending(true);
    setError(null);
    const fn = action === "approve" ? approveFulfillment : action === "reject" ? rejectFulfillment : retryFulfillment;
    const result = await fn(workflow.id);
    if (result.ok) setWorkflow(result.data);
    else setError(result.error);
    setWorkflowActionPending(false);
  }

  async function handleResolveSku(e: React.FormEvent) {
    e.preventDefault();
    if (!order || !skuForm.amazon_sku.trim()) return;
    setResolvingSku(true);
    setError(null);
    const mappingResult = await createSkuMapping({
      tiktok_sku: order.sku,
      variation: order.variation,
      amazon_sku: skuForm.amazon_sku.trim(),
      asin: skuForm.asin.trim() || undefined,
    });
    if (!mappingResult.ok) {
      setError(mappingResult.error);
      setResolvingSku(false);
      return;
    }
    if (workflow) {
      const retryResult = await retryFulfillment(workflow.id);
      if (retryResult.ok) setWorkflow(retryResult.data);
      else setError(retryResult.error);
    }
    setSkuForm({ amazon_sku: "", asin: "" });
    setResolvingSku(false);
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
        Loading order details…
      </div>
    );
  }

  if (error && !order) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <button onClick={onClose} className="text-sm text-blue-600 hover:text-blue-800 font-medium">
          ← Back to orders
        </button>
      </div>
    );
  }

  if (!order) return null;

  const meta = ORDER_STATUS_META[order.status];
  const allowed = VALID_TRANSITIONS[order.status];
  const currentStep = order.status === "cancelled" ? -1 : WORKFLOW_STEPS.indexOf(order.status);

  return (
    <div className="space-y-6">
      {/* ---- Back button ---- */}
      <button
        onClick={onClose}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium"
      >
        ← Back to orders
      </button>

      {/* ---- Error banner ---- */}
      {error && (
        <div
          className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* ---- Order header ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{order.product_name}</h2>
            <p className="text-sm text-gray-500 font-mono mt-0.5">Order {order.id.slice(0, 8)}…</p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${meta.bg} ${meta.text}`}
          >
            <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
            {meta.label}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500 font-medium">Customer</span>
            <p className="text-gray-900 mt-0.5">{order.customer_name}</p>
          </div>
          <div>
            <span className="text-gray-500 font-medium">Quantity</span>
            <p className="text-gray-900 mt-0.5">{order.quantity}</p>
          </div>
          <div className="sm:col-span-2">
            <span className="text-gray-500 font-medium">Shipping Address</span>
            <p className="text-gray-900 mt-0.5">{order.shipping_address}</p>
          </div>
          <div>
            <span className="text-gray-500 font-medium">Created</span>
            <p className="text-gray-900 mt-0.5">{formatTime(order.created_at)}</p>
          </div>
          <div>
            <span className="text-gray-500 font-medium">Last Updated</span>
            <p className="text-gray-900 mt-0.5">{formatTime(order.updated_at)}</p>
          </div>
        </div>

        {order.source === "TIKTOK" && (
          <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-500 font-medium">TikTok Order ID</span>
              <p className="text-gray-900 mt-0.5 font-mono">{order.tiktok_order_id ?? "—"}</p>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Variation</span>
              <p className="text-gray-900 mt-0.5">{order.variation ?? "—"}</p>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Phone</span>
              <p className="text-gray-900 mt-0.5">{order.channel_metadata?.phone_number ?? "—"}</p>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Price</span>
              <p className="text-gray-900 mt-0.5">
                {order.channel_metadata?.price != null ? `$${order.channel_metadata.price.toFixed(2)}` : "—"}
              </p>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Delivery Date</span>
              <p className="text-gray-900 mt-0.5">{order.channel_metadata?.delivery_date ?? "Not yet scheduled"}</p>
            </div>
            <div>
              <span className="text-gray-500 font-medium">Delivery Instructions</span>
              <p className="text-gray-900 mt-0.5">{order.channel_metadata?.delivery_instructions ?? "—"}</p>
            </div>
            <div className="sm:col-span-3">
              <span className="text-gray-500 font-medium">Google Sheet</span>
              {order.sheet_synced_at ? (
                <p className="text-green-700 mt-0.5">✓ Synced {formatTime(order.sheet_synced_at)}</p>
              ) : order.sheet_sync_error ? (
                <p className="text-red-600 mt-0.5">⚠ Sync failed: {order.sheet_sync_error}</p>
              ) : (
                <p className="text-gray-400 mt-0.5">Not yet synced</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ---- Business automation status ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Automation Status
        </h3>
        {workflow ? (
          <div className="space-y-2">
            {businessStages(order, workflow).map((stage) => (
              <div key={stage.label} className="flex items-center gap-2 text-sm">
                <span
                  className={
                    stage.status === "done"
                      ? "text-green-600"
                      : stage.status === "current"
                        ? "text-yellow-600"
                        : "text-gray-300"
                  }
                >
                  {stage.status === "done" ? "✓" : stage.status === "current" ? "⚠" : "○"}
                </span>
                <span className={stage.status === "pending" ? "text-gray-400" : "text-gray-900"}>{stage.label}</span>
                {stage.warning && (
                  <span className="text-xs text-orange-600 ml-1">⚠ {stage.warning}</span>
                )}
              </div>
            ))}

            {workflow.status === "waiting_approval" && (
              <div className="mt-4 pt-4 border-t border-gray-100 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p className="text-sm font-semibold text-yellow-800 mb-1">⚠ HUMAN APPROVAL REQUIRED</p>
                <p className="text-sm text-yellow-700 mb-3">
                  The Amazon checkout is prepared. No final submission has occurred yet.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => handleWorkflowAction("reject")}
                    disabled={workflowActionPending}
                    className="px-4 py-2 rounded-md text-sm font-medium bg-white border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleWorkflowAction("approve")}
                    disabled={workflowActionPending}
                    className="px-4 py-2 rounded-md text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    Approve &amp; Continue
                  </button>
                </div>
              </div>
            )}

            {workflow.status === "failed" && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-sm text-red-700 mb-3">⚠ {workflow.error_message ?? "Fulfillment failed"}</p>
                {workflow.sku_mapping_status && !["matched", "not_required"].includes(workflow.sku_mapping_status) ? (
                  <form onSubmit={handleResolveSku} className="space-y-2 bg-gray-50 border border-gray-100 rounded-lg p-4">
                    <p className="text-sm font-semibold text-gray-700">⚠ SKU MAPPING REQUIRED</p>
                    <p className="text-xs text-gray-500 mb-2">
                      TikTok SKU <span className="font-mono">{order.sku}</span>
                      {order.variation ? ` (${order.variation})` : ""} has no confirmed Amazon match.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="Amazon SKU *"
                        value={skuForm.amazon_sku}
                        onChange={(e) => setSkuForm({ ...skuForm, amazon_sku: e.target.value })}
                        required
                        className="rounded-md border border-gray-300 px-3 py-2 text-sm"
                      />
                      <input
                        type="text"
                        placeholder="ASIN (optional)"
                        value={skuForm.asin}
                        onChange={(e) => setSkuForm({ ...skuForm, asin: e.target.value })}
                        className="rounded-md border border-gray-300 px-3 py-2 text-sm"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={resolvingSku || !skuForm.amazon_sku.trim()}
                      className="px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300"
                    >
                      {resolvingSku ? "Resolving…" : "Confirm Mapping & Retry"}
                    </button>
                  </form>
                ) : (
                  <button
                    onClick={() => handleWorkflowAction("retry")}
                    disabled={workflowActionPending}
                    className="px-4 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    Retry
                  </button>
                )}
              </div>
            )}

            {workflow.status === "completed" && (
              <p className="mt-3 text-sm text-green-700">
                ✓ Confirmed — {workflow.confirmation?.confirmation_id}
              </p>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-400">Fulfillment has not started for this order yet.</p>
            {order.sku && (
              <button
                onClick={handleStartFulfillment}
                disabled={workflowActionPending}
                className="px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
              >
                {workflowActionPending ? "Starting…" : "Start Fulfillment"}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ---- Status timeline ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Fulfillment Timeline
        </h3>

        {order.status === "cancelled" ? (
          <div className="flex items-center gap-3 py-3">
            <span className="w-4 h-4 rounded-full bg-red-400" />
            <span className="text-sm font-medium text-red-700">
              This order has been cancelled
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-0">
            {WORKFLOW_STEPS.map((step, idx) => {
              const stepMeta = ORDER_STATUS_META[step];
              const isCompleted = idx < currentStep;
              const isCurrent = idx === currentStep;
              const isFuture = idx > currentStep;

              return (
                <div key={step} className="flex items-center flex-1 last:flex-initial">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
                        ${isCompleted ? "bg-green-500 text-white" : ""}
                        ${isCurrent ? `${stepMeta.dot} text-white` : ""}
                        ${isFuture ? "bg-gray-200 text-gray-400" : ""}
                      `}
                    >
                      {isCompleted ? "✓" : idx + 1}
                    </div>
                    <span
                      className={`text-xs mt-1.5 font-medium whitespace-nowrap
                        ${isCompleted ? "text-green-700" : ""}
                        ${isCurrent ? stepMeta.text : ""}
                        ${isFuture ? "text-gray-400" : ""}
                      `}
                    >
                      {stepMeta.label}
                    </span>
                  </div>
                  {idx < WORKFLOW_STEPS.length - 1 && (
                    <div
                      className={`h-0.5 flex-1 mx-1 rounded
                        ${idx < currentStep ? "bg-green-400" : "bg-gray-200"}
                      `}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ---- Workflow actions ---- */}
      {allowed.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Actions
          </h3>
          <div className="flex flex-wrap gap-3">
            {allowed.map((status) => {
              const sMeta = ORDER_STATUS_META[status];
              const isCancel = status === "cancelled";
              return (
                <button
                  key={status}
                  onClick={() => handleTransition(status)}
                  disabled={updating}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50
                    ${isCancel
                      ? "bg-red-50 text-red-700 border border-red-200 hover:bg-red-100"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                    }`}
                >
                  {isCancel ? "Cancel Order" : `Move to ${sMeta.label}`}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
