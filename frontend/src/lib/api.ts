const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const HEALTH_ENDPOINT = `${API_BASE_URL}/api/v1/health`;

export interface HealthStatus {
  status: string;
}

export interface HealthCheckSuccess {
  ok: true;
  httpStatus: number;
  data: HealthStatus;
}

export interface HealthCheckFailure {
  ok: false;
  httpStatus: number | null;
  error: string;
}

export type HealthCheckResult = HealthCheckSuccess | HealthCheckFailure;

function isHealthStatus(value: unknown): value is HealthStatus {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    typeof (value as { status: unknown }).status === "string"
  );
}

export async function checkBackendHealth(): Promise<HealthCheckResult> {
  try {
    const response = await fetch(HEALTH_ENDPOINT, {
      method: "GET",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return {
        ok: false,
        httpStatus: response.status,
        error: `Unexpected HTTP status ${response.status}`,
      };
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      return {
        ok: false,
        httpStatus: response.status,
        error: "Unexpected response body (not valid JSON)",
      };
    }

    if (!isHealthStatus(body)) {
      return {
        ok: false,
        httpStatus: response.status,
        error: "Unexpected response shape",
      };
    }

    return { ok: true, httpStatus: response.status, data: body };
  } catch (error) {
    return {
      ok: false,
      httpStatus: null,
      error:
        error instanceof Error ? error.message : "Unknown network error",
    };
  }
}
