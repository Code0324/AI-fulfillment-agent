"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createAutomationSession,
  fetchAutomationSessions,
  fillAutomationForm,
  stopAutomationSession,
  type AutomationSession,
  type NormalizedAddress,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_META: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  idle: { label: "Idle", dot: "bg-gray-400", bg: "bg-gray-50", text: "text-gray-700" },
  running: { label: "Running", dot: "bg-blue-400", bg: "bg-blue-50", text: "text-blue-700" },
  waiting_approval: { label: "Awaiting Approval", dot: "bg-yellow-400", bg: "bg-yellow-50", text: "text-yellow-700" },
  completed: { label: "Completed", dot: "bg-green-400", bg: "bg-green-50", text: "text-green-700" },
  failed: { label: "Failed", dot: "bg-red-400", bg: "bg-red-50", text: "text-red-700" },
  stopped: { label: "Stopped", dot: "bg-gray-400", bg: "bg-gray-50", text: "text-gray-500" },
};

const TEST_ADDRESS: NormalizedAddress = {
  first_name: "Test",
  last_name: "Customer",
  address_line_1: "123 Test Street",
  address_line_2: "Apt 4",
  city: "Testville",
  state: "CA",
  postal_code: "90210",
  country: "US",
  phone: "555-0123",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AutomationSandbox() {
  const [sessions, setSessions] = useState<AutomationSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [filling, setFilling] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // Load sessions
  // ------------------------------------------------------------------

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchAutomationSessions(1, 20);
    if (result.ok) {
      setSessions(result.data.items);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  async function handleCreateSession() {
    setCreating(true);
    setError(null);
    const result = await createAutomationSession();
    if (result.ok) {
      setSessions((prev) => [result.data, ...prev]);
    } else {
      setError(result.error);
    }
    setCreating(false);
  }

  async function handleStopSession(sessionId: string) {
    const result = await stopAutomationSession(sessionId);
    if (result.ok) {
      setSessions((prev) => prev.map((s) => (s.id === sessionId ? result.data : s)));
    } else {
      setError(result.error);
    }
  }

  async function handleFillForm(sessionId: string) {
    setFilling(true);
    setError(null);
    setLastResult(null);
    const result = await fillAutomationForm(sessionId, TEST_ADDRESS, "express");
    if (result.ok) {
      setLastResult(
        result.data.success
          ? `Filled ${result.data.filled_fields.length} fields successfully`
          : `Failed: ${result.data.error_message}`
      );
      loadSessions();
    } else {
      setError(result.error);
    }
    setFilling(false);
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <section aria-label="Automation Sandbox" className="space-y-6">
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

      {/* ---- Sandbox banner ---- */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-800 font-medium text-center">
        ⚠️ SANDBOX — NO AMAZON CONNECTION — TEST DATA ONLY
      </div>

      {/* ---- Session controls ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Automation Sessions
          </h2>
          <div className="flex items-center gap-3">
            <button
              onClick={handleCreateSession}
              disabled={creating}
              className="px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? "Creating…" : "New Session"}
            </button>
            <button
              onClick={loadSessions}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* ---- Result display ---- */}
        {lastResult && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-sm text-green-700">
            {lastResult}
          </div>
        )}

        {/* ---- Session list ---- */}
        {loading && (
          <div className="text-center text-gray-400 py-8">Loading sessions…</div>
        )}

        {!loading && sessions.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            No sessions yet. Click &quot;New Session&quot; to start.
          </div>
        )}

        {!loading && sessions.length > 0 && (
          <div className="space-y-3">
            {sessions.map((session) => {
              const meta = STATUS_META[session.status] || STATUS_META.idle;
              return (
                <div
                  key={session.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${meta.bg} ${meta.text}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                      {meta.label}
                    </span>
                    <div>
                      <div className="text-xs font-mono text-gray-500">
                        {session.id.slice(0, 8)}…
                      </div>
                      {session.current_action && (
                        <div className="text-xs text-gray-600">
                          Action: {session.current_action}
                        </div>
                      )}
                      {session.error_message && (
                        <div className="text-xs text-red-600">
                          Error: {session.error_message}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {session.status === "idle" && (
                      <>
                        <button
                          onClick={() => handleFillForm(session.id)}
                          disabled={filling}
                          className="px-3 py-1.5 rounded text-xs font-medium text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-300 transition-colors"
                        >
                          {filling ? "Filling…" : "Fill Form"}
                        </button>
                        <button
                          onClick={() => handleStopSession(session.id)}
                          className="px-3 py-1.5 rounded text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
                        >
                          Stop
                        </button>
                      </>
                    )}
                    {session.status === "completed" && (
                      <button
                        onClick={() => handleStopSession(session.id)}
                        className="px-3 py-1.5 rounded text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
                      >
                        Cleanup
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ---- Test address display ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Test Address (Synthetic Data)
        </h2>
        <div className="text-sm text-gray-700 space-y-1">
          <p><span className="font-medium">Name:</span> {TEST_ADDRESS.first_name} {TEST_ADDRESS.last_name}</p>
          <p><span className="font-medium">Address:</span> {TEST_ADDRESS.address_line_1}, {TEST_ADDRESS.address_line_2}</p>
          <p><span className="font-medium">City:</span> {TEST_ADDRESS.city}, {TEST_ADDRESS.state} {TEST_ADDRESS.postal_code}</p>
          <p><span className="font-medium">Country:</span> {TEST_ADDRESS.country}</p>
          <p><span className="font-medium">Phone:</span> {TEST_ADDRESS.phone}</p>
        </div>
      </div>
    </section>
  );
}
