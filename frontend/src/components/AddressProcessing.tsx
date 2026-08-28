"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchAddressResults,
  parseAddress,
  reviewAddress,
  type AddressProcessingResult,
  type AddressProcessingStatus,
  type ValidationIssue,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_META: Record<
  AddressProcessingStatus,
  { label: string; dot: string; bg: string; text: string }
> = {
  pending: {
    label: "Pending",
    dot: "bg-gray-400",
    bg: "bg-gray-50",
    text: "text-gray-700",
  },
  processed: {
    label: "Processed",
    dot: "bg-green-400",
    bg: "bg-green-50",
    text: "text-green-700",
  },
  needs_review: {
    label: "Needs Review",
    dot: "bg-yellow-400",
    bg: "bg-yellow-50",
    text: "text-yellow-700",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-400",
    bg: "bg-red-50",
    text: "text-red-700",
  },
};

const SEVERITY_META: Record<string, { color: string }> = {
  error: { color: "text-red-600" },
  warning: { color: "text-yellow-600" },
  info: { color: "text-blue-600" },
};

// ---------------------------------------------------------------------------
// Synthetic test addresses for quick-fill
// ---------------------------------------------------------------------------

const TEST_ADDRESSES = [
  {
    label: "Complete Address",
    value:
      "John Smith\n45 East 10th Street\nApt 5B\nNew York NY 10003\nUS",
  },
  {
    label: "Missing ZIP",
    value: "Tom Brown\n456 Elm Blvd\nSeattle WA\nUS",
  },
  {
    label: "Multi-line with Suite",
    value:
      "Jane Doe\n789 Oak Avenue\nSuite 200\nLos Angeles CA 90001\nUnited States",
  },
  {
    label: "With Phone",
    value:
      "Alice Williams\n321 Pine Road\nHouston TX 77001\nUS\n555-123-4567",
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AddressProcessing() {
  const [results, setResults] = useState<AddressProcessingResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Parse form
  const [rawAddress, setRawAddress] = useState("");
  const [parsing, setParsing] = useState(false);
  const [lastResult, setLastResult] =
    useState<AddressProcessingResult | null>(null);

  // Review
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [correctionMode, setCorrectionMode] = useState(false);
  const [corrections, setCorrections] = useState({
    first_name: "",
    last_name: "",
    address_line_1: "",
    address_line_2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "",
    phone: "",
  });

  // Status filter
  const [statusFilter, setStatusFilter] = useState<
    AddressProcessingStatus | undefined
  >(undefined);

  // ---------------------------------------------------------------
  // Load results
  // ---------------------------------------------------------------

  const loadResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchAddressResults(1, 50, statusFilter);
    if (result.ok) {
      setResults(result.data.items);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  // ---------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------

  async function handleParse(e: React.FormEvent) {
    e.preventDefault();
    const addr = rawAddress.trim();
    if (!addr) return;
    setParsing(true);
    setError(null);
    const result = await parseAddress(addr);
    if (result.ok) {
      setLastResult(result.data);
      setResults((prev) => [result.data, ...prev]);
      setRawAddress("");
    } else {
      setError(result.error);
    }
    setParsing(false);
  }

  async function handleApprove(resultId: string) {
    setError(null);
    const result = await reviewAddress(resultId, "approve");
    if (result.ok) {
      setResults((prev) =>
        prev.map((r) => (r.id === resultId ? result.data : r))
      );
      if (lastResult?.id === resultId) setLastResult(result.data);
      setReviewingId(null);
    } else {
      setError(result.error);
    }
  }

  async function handleReject(resultId: string) {
    setError(null);
    const result = await reviewAddress(resultId, "reject");
    if (result.ok) {
      setResults((prev) =>
        prev.map((r) => (r.id === resultId ? result.data : r))
      );
      if (lastResult?.id === resultId) setLastResult(result.data);
      setReviewingId(null);
    } else {
      setError(result.error);
    }
  }

  async function handleCorrect(resultId: string) {
    setError(null);
    const result = await reviewAddress(resultId, "correct", corrections);
    if (result.ok) {
      setResults((prev) =>
        prev.map((r) => (r.id === resultId ? result.data : r))
      );
      if (lastResult?.id === resultId) setLastResult(result.data);
      setReviewingId(null);
      setCorrectionMode(false);
    } else {
      setError(result.error);
    }
  }

  function startReview(result: AddressProcessingResult) {
    setReviewingId(result.id);
    setCorrectionMode(false);
    setCorrections({
      first_name: result.first_name,
      last_name: result.last_name,
      address_line_1: result.address_line_1,
      address_line_2: result.address_line_2,
      city: result.city,
      state: result.state,
      postal_code: result.postal_code,
      country: result.country,
      phone: result.phone,
    });
  }

  // ---------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------

  function renderIssues(issues: ValidationIssue[]) {
    if (issues.length === 0) return null;
    return (
      <div className="mt-2 space-y-1">
        {issues.map((issue, i) => {
          const meta = SEVERITY_META[issue.severity] || SEVERITY_META.info;
          return (
            <div key={i} className={`text-xs ${meta.color}`}>
              <span className="font-medium">{issue.field}:</span>{" "}
              {issue.message}
            </div>
          );
        })}
      </div>
    );
  }

  function renderReviewForm(result: AddressProcessingResult) {
    return (
      <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">
            Review Address
          </span>
          <button
            onClick={() => {
              setReviewingId(null);
              setCorrectionMode(false);
            }}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        </div>

        {!correctionMode ? (
          <div className="flex gap-2">
            {result.status === "needs_review" && (
              <button
                onClick={() => handleApprove(result.id)}
                className="px-3 py-1.5 rounded text-xs font-medium text-white bg-green-600 hover:bg-green-700 transition-colors"
              >
                Approve
              </button>
            )}
            <button
              onClick={() => setCorrectionMode(true)}
              className="px-3 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors"
            >
              Correct
            </button>
            <button
              onClick={() => handleReject(result.id)}
              className="px-3 py-1.5 rounded text-xs font-medium text-white bg-red-600 hover:bg-red-700 transition-colors"
            >
              Reject
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              {(
                [
                  "first_name",
                  "last_name",
                  "address_line_1",
                  "address_line_2",
                  "city",
                  "state",
                  "postal_code",
                  "country",
                  "phone",
                ] as const
              ).map((field) => (
                <div key={field}>
                  <label className="text-xs text-gray-500">
                    {field.replace(/_/g, " ")}
                  </label>
                  <input
                    type="text"
                    value={corrections[field]}
                    onChange={(e) =>
                      setCorrections((prev) => ({
                        ...prev,
                        [field]: e.target.value,
                      }))
                    }
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              ))}
            </div>
            <button
              onClick={() => handleCorrect(result.id)}
              className="px-3 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors"
            >
              Save Corrections
            </button>
          </div>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------

  const summary = (
    ["processed", "needs_review", "failed", "pending"] as const
  ).map((s) => ({
    status: s,
    count: results.filter((r) => r.status === s).length,
  }));

  return (
    <section aria-label="Address Processing" className="space-y-6">
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
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800 font-medium text-center">
        🧪 SANDBOX — SYNTHETIC DATA ONLY — NO REAL CUSTOMER PII
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {summary.map(({ status, count }) => {
          const meta = STATUS_META[status];
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

      {/* Parse form */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Parse Address
        </h2>

        {/* Quick-fill buttons */}
        <div className="flex flex-wrap gap-2 mb-3">
          {TEST_ADDRESSES.map((test) => (
            <button
              key={test.label}
              onClick={() => setRawAddress(test.value)}
              className="px-3 py-1 rounded text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors"
            >
              {test.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleParse} className="space-y-3">
          <textarea
            value={rawAddress}
            onChange={(e) => setRawAddress(e.target.value)}
            placeholder={"Enter raw address...\nJohn Smith\n123 Main St\nCity ST 12345\nUS"}
            rows={5}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            type="submit"
            disabled={parsing || !rawAddress.trim()}
            className="px-5 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {parsing ? "Processing…" : "Parse Address"}
          </button>
        </form>

        {/* Last result preview */}
        {lastResult && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">
                Last Result
              </span>
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_META[lastResult.status].bg} ${STATUS_META[lastResult.status].text}`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${STATUS_META[lastResult.status].dot}`}
                />
                {STATUS_META[lastResult.status].label}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
              <div>
                <span className="text-gray-500">Name:</span>{" "}
                {lastResult.first_name} {lastResult.last_name}
              </div>
              <div>
                <span className="text-gray-500">Confidence:</span>{" "}
                {(lastResult.confidence * 100).toFixed(0)}%
              </div>
              <div>
                <span className="text-gray-500">Address:</span>{" "}
                {lastResult.address_line_1}
                {lastResult.address_line_2
                  ? `, ${lastResult.address_line_2}`
                  : ""}
              </div>
              <div>
                <span className="text-gray-500">City:</span>{" "}
                {lastResult.city}, {lastResult.state} {lastResult.postal_code}
              </div>
              <div>
                <span className="text-gray-500">Country:</span>{" "}
                {lastResult.country}
              </div>
              {lastResult.phone && (
                <div>
                  <span className="text-gray-500">Phone:</span>{" "}
                  {lastResult.phone}
                </div>
              )}
            </div>
            {lastResult.review_reason && (
              <div className="mt-2 text-xs text-yellow-700 bg-yellow-50 rounded px-2 py-1">
                {lastResult.review_reason}
              </div>
            )}
            {renderIssues(lastResult.validation_issues)}
          </div>
        )}
      </div>

      {/* Results list */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Processing Results
          </h2>
          <div className="flex items-center gap-3">
            <select
              value={statusFilter || ""}
              onChange={(e) =>
                setStatusFilter(
                  (e.target.value as AddressProcessingStatus) || undefined
                )
              }
              className="text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="processed">Processed</option>
              <option value="needs_review">Needs Review</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
            </select>
            <button
              onClick={loadResults}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading && (
          <div className="text-center text-gray-400 py-8">
            Loading results…
          </div>
        )}

        {!loading && results.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            No results yet. Parse an address above to get started.
          </div>
        )}

        {!loading && results.length > 0 && (
          <div className="space-y-3">
            {results.map((result) => {
              const meta = STATUS_META[result.status];
              return (
                <div
                  key={result.id}
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
                          {(result.confidence * 100).toFixed(0)}% confidence
                        </span>
                        <span className="text-xs text-gray-400 font-mono">
                          {result.id.slice(0, 8)}…
                        </span>
                      </div>
                      <div className="text-sm text-gray-700">
                        <span className="font-medium">
                          {result.first_name} {result.last_name}
                        </span>
                        {" — "}
                        {result.address_line_1}
                        {result.city && `, ${result.city}`}
                        {result.state && `, ${result.state}`}
                        {result.postal_code && ` ${result.postal_code}`}
                      </div>
                      {result.raw_address && (
                        <div className="text-xs text-gray-400 mt-1 font-mono truncate max-w-lg">
                          Raw: {result.raw_address.split("\n")[0]}…
                        </div>
                      )}
                      {result.review_reason && (
                        <div className="text-xs text-yellow-700 mt-1">
                          {result.review_reason}
                        </div>
                      )}
                      {renderIssues(result.validation_issues)}
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      {(result.status === "needs_review" ||
                        result.status === "failed") && (
                        <button
                          onClick={() => startReview(result)}
                          className="px-3 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors"
                        >
                          Review
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Review form */}
                  {reviewingId === result.id &&
                    renderReviewForm(result)}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
