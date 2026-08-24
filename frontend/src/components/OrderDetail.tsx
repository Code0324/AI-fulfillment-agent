"use client";

import { useEffect, useState } from "react";
import { fetchOrder, updateOrderStatus, type Order, type OrderStatus } from "@/lib/api";

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

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchOrder(orderId).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setOrder(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [orderId]);

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
