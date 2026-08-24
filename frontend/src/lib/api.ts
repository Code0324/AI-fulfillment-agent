const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface Task {
  id: string;
  title: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  items: Task[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface ApiError {
  error: string;
}

// ---- helpers ----

function taskApiBase(): string {
  return `${API_BASE_URL}/api/v1/tasks`;
}

function isApiError(body: unknown): body is ApiError {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as { error: unknown }).error === "string"
  );
}

// ---- API calls ----

export async function fetchTasks(
  page = 1,
  pageSize = 50,
): Promise<{ ok: true; data: TaskListResponse } | { ok: false; error: string }> {
  try {
    const res = await fetch(
      `${taskApiBase()}?page=${page}&page_size=${pageSize}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as TaskListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function createTask(
  title: string,
): Promise<{ ok: true; data: Task } | { ok: false; error: string }> {
  try {
    const res = await fetch(taskApiBase(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, status: "pending" }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Task };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function updateTaskStatus(
  taskId: string,
  status: TaskStatus,
): Promise<{ ok: true; data: Task } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${taskApiBase()}/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Task };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}
