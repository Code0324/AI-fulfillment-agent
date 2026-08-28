/**
 * Auth token management and authenticated API client.
 *
 * Adapted from Digital-FTE's lib/api.ts pattern.
 * Manages JWT tokens in localStorage and provides an authenticated
 * fetch wrapper that automatically attaches the Bearer token.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Token Store (localStorage)
// ---------------------------------------------------------------------------

export const tokenStore = {
  get: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null,
  set: (token: string): void => {
    if (typeof window !== "undefined") localStorage.setItem("access_token", token);
  },
  clear: (): void => {
    if (typeof window !== "undefined") localStorage.removeItem("access_token");
  },
};

/**
 * Authenticated fetch wrapper.
 * Attaches the Bearer token to every request if available.
 */
export async function authFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = tokenStore.get();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
}

/**
 * Check if an error response indicates an expired/invalid session.
 */
export function isUnauthorized(response: Response): boolean {
  return response.status === 401;
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  auth_provider: string;
  is_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  message: string;
  user: AuthUser;
  access_token: string | null;
  token_type: string;
}

export interface SignupPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  subscription_plan: string;
  is_active: boolean;
  created_at: string;
}

export interface ApiError {
  error: string;
  detail?: string;
}

function isApiError(body: unknown): body is ApiError {
  return (
    typeof body === "object" &&
    body !== null &&
    ("error" in body || "detail" in body)
  );
}

function getErrorMessage(body: unknown): string {
  if (isApiError(body)) return body.detail || body.error;
  return "Unknown error";
}

// ---- Auth API calls ----

export async function authLogin(
  email: string,
  password: string,
): Promise<{ ok: true; data: AuthResponse } | { ok: false; error: string }> {
  try {
    const res = await authFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: getErrorMessage(body) || `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AuthResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function authSignup(
  payload: SignupPayload,
): Promise<{ ok: true; data: AuthResponse } | { ok: false; error: string }> {
  try {
    const res = await authFetch("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: getErrorMessage(body) || `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AuthResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function authMe(): Promise<{ ok: true; data: AuthResponse } | { ok: false; error: string }> {
  try {
    const res = await authFetch("/auth/me");
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: getErrorMessage(body) || `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AuthResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---- Organization API calls ----

export async function createOrganization(
  name: string,
  slug: string,
  description?: string,
): Promise<{ ok: true; data: Organization } | { ok: false; error: string }> {
  try {
    const res = await authFetch("/organizations", {
      method: "POST",
      body: JSON.stringify({ name, slug, description }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: getErrorMessage(body) || `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Organization };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function listOrganizations(): Promise<
  { ok: true; data: Organization[] } | { ok: false; error: string }
> {
  try {
    const res = await authFetch("/organizations");
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: getErrorMessage(body) || `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Organization[] };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}
