"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchAmazonStatus,
  type AmazonConnectionStatus,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Amazon Sandbox Status Component (CHUNK 1V)
// ---------------------------------------------------------------------------

export default function AmazonSandboxStatus() {
  const [status, setStatus] = useState<AmazonConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await fetchAmazonStatus();
    if (result.ok) {
      setStatus(result.data);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Determine connection indicator
  const getConfiguredIndicator = () => {
    if (status?.configured) {
      return (
        <span className="inline-flex items-center gap-1.5 text-green-700 font-medium">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          Configured
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 text-yellow-600 font-medium">
        <span className="w-2 h-2 rounded-full bg-yellow-400" />
        Not Configured
      </span>
    );
  };

  const getEnvironmentBadge = () => {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
        SANDBOX
      </span>
    );
  };

  const getModeBadge = () => {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-50 text-purple-700">
        <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
        READ-ONLY
      </span>
    );
  };

  return (
    <section aria-label="Amazon Sandbox Status">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Amazon Sandbox Connection
      </h2>

      {loading && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 text-center text-gray-400">
          Loading Amazon status…
        </div>
      )}

      {!loading && error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && status && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          {/* Connection Status */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              {getConfiguredIndicator()}
              {getEnvironmentBadge()}
              {getModeBadge()}
            </div>
            <button
              onClick={loadStatus}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Refresh
            </button>
          </div>

          {/* Notice */}
          {status.notice && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700 mb-4">
              {status.notice}
            </div>
          )}

          {/* Connection Details */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">Region</div>
              <div className="font-medium text-gray-900">
                {status.region?.toUpperCase() ?? "N/A"}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">Marketplace</div>
              <div className="font-medium text-gray-900 font-mono text-xs">
                {status.marketplace_id ?? "N/A"}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">Token Expires In</div>
              <div className="font-medium text-gray-900">
                {status.token_expires_in
                  ? `${Math.floor(status.token_expires_in / 60)}m`
                  : "N/A"}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">Token Refreshes</div>
              <div className="font-medium text-gray-900">
                {status.token_refresh_count ?? 0}
              </div>
            </div>
          </div>

          {/* Request Statistics */}
          {status.request_stats && (
            <div className="border-t border-gray-200 pt-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Request Statistics
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">Total</div>
                  <div className="font-medium text-gray-900">
                    {status.request_stats.total_requests}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">Successful</div>
                  <div className="font-medium text-green-600">
                    {status.request_stats.successful_requests}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">Failed</div>
                  <div className="font-medium text-red-600">
                    {status.request_stats.failed_requests}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Orders Statistics */}
          <div className="border-t border-gray-200 pt-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">Orders Retrieved</div>
                <div className="font-medium text-gray-900">
                  {status.orders_retrieved ?? 0}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">Orders Normalized</div>
                <div className="font-medium text-gray-900">
                  {status.orders_normalized ?? 0}
                </div>
              </div>
            </div>
          </div>

          {/* Safety Notice */}
          <div className="border-t border-gray-200 pt-4 mt-4">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-700">
              <strong>Safety:</strong> This integration is read-only and sandbox-only.
              No production endpoints are accessible. No orders will be automatically
              submitted. All fulfillment requires human approval.
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
