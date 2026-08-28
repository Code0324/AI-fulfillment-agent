"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createInventoryItem,
  fetchInventory,
  updateInventoryItem,
  type CreateInventoryPayload,
  type InventoryItem,
  type InventoryStatus,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const INVENTORY_STATUS_META: Record<
  InventoryStatus,
  { label: string; dot: string; bg: string; text: string }
> = {
  in_stock: {
    label: "In Stock",
    dot: "bg-green-400",
    bg: "bg-green-50",
    text: "text-green-700",
  },
  low_stock: {
    label: "Low Stock",
    dot: "bg-yellow-400",
    bg: "bg-yellow-50",
    text: "text-yellow-700",
  },
  out_of_stock: {
    label: "Out of Stock",
    dot: "bg-red-400",
    bg: "bg-red-50",
    text: "text-red-700",
  },
};

const ALL_INVENTORY_STATUSES: InventoryStatus[] = [
  "in_stock",
  "low_stock",
  "out_of_stock",
];

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

export default function InventorySection() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // create form
  const [form, setForm] = useState<CreateInventoryPayload>({
    sku: "",
    product_name: "",
    current_stock: 0,
    reserved_quantity: 0,
    low_stock_threshold: 10,
  });
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // filter
  const [statusFilter, setStatusFilter] = useState<InventoryStatus | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // edit mode
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editStock, setEditStock] = useState(0);
  const [editReserved, setEditReserved] = useState(0);
  const [editThreshold, setEditThreshold] = useState(10);

  // debounced search
  function handleSearchChange(value: string) {
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setDebouncedSearch(value);
    }, 300);
  }

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, []);

  // ------------------------------------------------------------------
  // Load data
  // ------------------------------------------------------------------

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchInventory(1, 100, statusFilter, debouncedSearch || undefined);
    if (result.ok) {
      setItems(result.data.items);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [statusFilter, debouncedSearch]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // ------------------------------------------------------------------
  // Summary counts
  // ------------------------------------------------------------------

  const [allCounts, setAllCounts] = useState<Record<InventoryStatus, number>>({
    in_stock: 0, low_stock: 0, out_of_stock: 0,
  });

  const loadAllCounts = useCallback(async () => {
    const result = await fetchInventory(1, 100);
    if (result.ok) {
      const counts: Record<InventoryStatus, number> = { in_stock: 0, low_stock: 0, out_of_stock: 0 };
      for (const i of result.data.items) {
        counts[i.status]++;
      }
      setAllCounts(counts);
    }
  }, []);

  useEffect(() => {
    loadAllCounts();
  }, [loadAllCounts]);

  const summary = ALL_INVENTORY_STATUSES.map((s) => ({
    status: s,
    count: allCounts[s],
  }));

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.sku.trim() || !form.product_name.trim()) return;
    setCreating(true);
    const result = await createInventoryItem(form);
    if (result.ok) {
      setItems((prev) => [...prev, result.data]);
      setForm({ sku: "", product_name: "", current_stock: 0, reserved_quantity: 0, low_stock_threshold: 10 });
      setShowForm(false);
      loadAllCounts();
    } else {
      setError(result.error);
    }
    setCreating(false);
  }

  function startEdit(item: InventoryItem) {
    setEditingId(item.id);
    setEditStock(item.current_stock);
    setEditReserved(item.reserved_quantity);
    setEditThreshold(item.low_stock_threshold);
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(itemId: string) {
    const result = await updateInventoryItem(itemId, {
      current_stock: editStock,
      reserved_quantity: editReserved,
      low_stock_threshold: editThreshold,
    });
    if (result.ok) {
      setItems((prev) => prev.map((i) => (i.id === itemId ? result.data : i)));
      setEditingId(null);
      loadAllCounts();
    } else {
      setError(result.error);
    }
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <section aria-label="Inventory" className="space-y-6">
      {/* ---- Error banner ---- */}
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

      {/* ---- Summary cards ---- */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Inventory Summary
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {summary.map(({ status, count }) => {
            const meta = INVENTORY_STATUS_META[status];
            return (
              <div
                key={status}
                className="rounded-lg border border-gray-200 bg-white p-4 text-center"
              >
                <div className="flex items-center justify-center gap-2 mb-1">
                  <span className={`w-2.5 h-2.5 rounded-full ${meta.dot}`} />
                  <span className="text-sm font-medium text-gray-700">
                    {meta.label}
                  </span>
                </div>
                <p className="text-3xl font-bold text-gray-900">{count}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- Create inventory item ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Add Inventory Item
          </h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            {showForm ? "Cancel" : "+ New Item"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="text"
                value={form.sku}
                onChange={(e) => setForm({ ...form, sku: e.target.value })}
                placeholder="SKU / Product ID *"
                required
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <input
                type="text"
                value={form.product_name}
                onChange={(e) => setForm({ ...form, product_name: e.target.value })}
                placeholder="Product name *"
                required
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Stock</label>
                <input
                  type="number"
                  min={0}
                  value={form.current_stock}
                  onChange={(e) => setForm({ ...form, current_stock: parseInt(e.target.value) || 0 })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Reserved</label>
                <input
                  type="number"
                  min={0}
                  value={form.reserved_quantity}
                  onChange={(e) => setForm({ ...form, reserved_quantity: parseInt(e.target.value) || 0 })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Threshold</label>
                <input
                  type="number"
                  min={0}
                  value={form.low_stock_threshold}
                  onChange={(e) => setForm({ ...form, low_stock_threshold: parseInt(e.target.value) || 10 })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={creating || !form.sku.trim() || !form.product_name.trim()}
              className="px-5 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? "Adding…" : "Add Item"}
            </button>
          </form>
        )}
      </div>

      {/* ---- Inventory list ---- */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Inventory Items
          </h2>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search SKU, product…"
              className="text-xs border border-gray-300 rounded px-3 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 w-48"
            />
            <select
              value={statusFilter ?? ""}
              onChange={(e) =>
                setStatusFilter(
                  e.target.value ? (e.target.value as InventoryStatus) : undefined,
                )
              }
              className="text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              {ALL_INVENTORY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {INVENTORY_STATUS_META[s].label}
                </option>
              ))}
            </select>
            <button
              onClick={loadItems}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading && (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
            Loading inventory…
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
            No inventory items yet. Add one above to get started.
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th className="px-4 py-3">SKU</th>
                    <th className="px-4 py-3">Product</th>
                    <th className="px-4 py-3">Stock</th>
                    <th className="px-4 py-3">Reserved</th>
                    <th className="px-4 py-3">Available</th>
                    <th className="px-4 py-3">Threshold</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {items.map((item) => {
                    const meta = INVENTORY_STATUS_META[item.status];
                    const isEditing = editingId === item.id;
                    return (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-900 font-mono text-xs">
                            {item.sku}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {item.product_name}
                        </td>
                        <td className="px-4 py-3">
                          {isEditing ? (
                            <input
                              type="number"
                              min={0}
                              value={editStock}
                              onChange={(e) => setEditStock(parseInt(e.target.value) || 0)}
                              className="w-20 text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          ) : (
                            <span className="text-gray-700">{item.current_stock}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isEditing ? (
                            <input
                              type="number"
                              min={0}
                              value={editReserved}
                              onChange={(e) => setEditReserved(parseInt(e.target.value) || 0)}
                              className="w-20 text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          ) : (
                            <span className="text-gray-700">{item.reserved_quantity}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`font-medium ${item.available_quantity === 0 ? "text-red-600" : "text-gray-900"}`}>
                            {item.available_quantity}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {isEditing ? (
                            <input
                              type="number"
                              min={0}
                              value={editThreshold}
                              onChange={(e) => setEditThreshold(parseInt(e.target.value) || 10)}
                              className="w-20 text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          ) : (
                            <span className="text-gray-500">{item.low_stock_threshold}</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${meta.bg} ${meta.text}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                            {meta.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {isEditing ? (
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={() => saveEdit(item.id)}
                                className="text-xs text-white bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded font-medium"
                              >
                                Save
                              </button>
                              <button
                                onClick={cancelEdit}
                                className="text-xs text-gray-600 hover:text-gray-800 font-medium"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => startEdit(item)}
                              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                            >
                              Edit
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
