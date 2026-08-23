"use client";

import { useState } from "react";
import {
  HEALTH_ENDPOINT,
  checkBackendHealth,
  type HealthCheckResult,
} from "@/lib/api";

type CheckState =
  | { phase: "idle" }
  | { phase: "checking" }
  | { phase: "done"; result: HealthCheckResult };

export default function BackendConnection() {
  const [state, setState] = useState<CheckState>({ phase: "idle" });

  const handleCheck = async () => {
    if (state.phase === "checking") return;
    setState({ phase: "checking" });
    const result = await checkBackendHealth();
    setState({ phase: "done", result });
  };

  const connected = state.phase === "done" && state.result.ok;
  const disconnected = state.phase === "done" && !state.result.ok;

  return (
    <section
      aria-label="Backend Connection"
      className="bg-white border border-gray-200 rounded-lg shadow-sm p-6 text-left"
    >
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        Backend Connection
      </h2>

      <div className="mb-4 text-sm">
        <span className="font-medium text-gray-700">Backend Status: </span>
        {state.phase !== "done" && (
          <span className="text-gray-500">
            {state.phase === "checking" ? "Checking..." : "Not checked"}
          </span>
        )}
        {connected && (
          <span className="font-medium text-green-700">
            🟢 Backend Connected
          </span>
        )}
        {disconnected && (
          <span className="font-medium text-red-700">
            🔴 Backend Disconnected
          </span>
        )}
      </div>

      <div className="mb-4 text-sm">
        <span className="font-medium text-gray-700">API Endpoint: </span>
        <code className="text-xs bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded break-all">
          {HEALTH_ENDPOINT}
        </code>
      </div>

      <div className="mb-4 text-sm">
        <span className="font-medium text-gray-700">Response:</span>
        <pre className="mt-1 bg-gray-900 text-green-400 text-xs rounded p-3 overflow-x-auto">
          {state.phase === "done" && state.result.ok
            ? JSON.stringify(state.result.data)
            : state.phase === "done"
              ? "// No response — see error below"
              : "// Run a check to see the response"}
        </pre>
      </div>

      {disconnected && (
        <p className="mb-4 text-sm text-red-600" role="alert">
          Unable to connect to the API.
        </p>
      )}

      <button
        type="button"
        onClick={handleCheck}
        disabled={state.phase === "checking"}
        className="w-full sm:w-auto px-5 py-2 rounded-md font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {state.phase === "checking" ? "Checking..." : "Check Backend"}
      </button>
    </section>
  );
}
