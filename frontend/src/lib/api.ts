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

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export type OrderStatus =
  | "pending"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled";

export interface Order {
  id: string;
  customer_name: string;
  shipping_address: string;
  product_name: string;
  sku: string;
  quantity: number;
  status: OrderStatus;
  inventory_reserved: boolean;
  created_at: string;
  updated_at: string;
}

export interface OrderListResponse {
  items: Order[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

function orderApiBase(): string {
  return `${API_BASE_URL}/api/v1/orders`;
}

export async function fetchOrders(
  page = 1,
  pageSize = 50,
  statusFilter?: OrderStatus,
  searchQuery?: string,
): Promise<{ ok: true; data: OrderListResponse } | { ok: false; error: string }> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (statusFilter) params.set("status", statusFilter);
    if (searchQuery && searchQuery.trim()) params.set("search", searchQuery.trim());
    const res = await fetch(
      `${orderApiBase()}?${params.toString()}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as OrderListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchOrder(
  orderId: string,
): Promise<{ ok: true; data: Order } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${orderApiBase()}/${orderId}`, {
      cache: "no-store",
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Order };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export interface CreateOrderPayload {
  customer_name: string;
  shipping_address: string;
  product_name: string;
  quantity: number;
  sku?: string;
  reserve_inventory?: boolean;
}

export async function createOrder(
  payload: CreateOrderPayload,
): Promise<{ ok: true; data: Order } | { ok: false; error: string }> {
  try {
    const res = await fetch(orderApiBase(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, status: "pending" }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Order };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function reserveOrderInventory(
  orderId: string,
): Promise<{ ok: true; data: Order } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${orderApiBase()}/${orderId}/reserve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Order };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function updateOrderStatus(
  orderId: string,
  status: OrderStatus,
): Promise<{ ok: true; data: Order } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${orderApiBase()}/${orderId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as Order };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---------------------------------------------------------------------------
// Inventory
// ---------------------------------------------------------------------------

export type InventoryStatus = "in_stock" | "low_stock" | "out_of_stock";

export interface InventoryItem {
  id: string;
  sku: string;
  product_name: string;
  current_stock: number;
  reserved_quantity: number;
  available_quantity: number;
  low_stock_threshold: number;
  status: InventoryStatus;
  created_at: string;
  updated_at: string;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

function inventoryApiBase(): string {
  return `${API_BASE_URL}/api/v1/inventory`;
}

export async function fetchInventory(
  page = 1,
  pageSize = 50,
  statusFilter?: InventoryStatus,
  searchQuery?: string,
): Promise<{ ok: true; data: InventoryListResponse } | { ok: false; error: string }> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (statusFilter) params.set("status", statusFilter);
    if (searchQuery && searchQuery.trim()) params.set("search", searchQuery.trim());
    const res = await fetch(
      `${inventoryApiBase()}?${params.toString()}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as InventoryListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export interface CreateInventoryPayload {
  sku: string;
  product_name: string;
  current_stock: number;
  reserved_quantity?: number;
  low_stock_threshold?: number;
}

export async function createInventoryItem(
  payload: CreateInventoryPayload,
): Promise<{ ok: true; data: InventoryItem } | { ok: false; error: string }> {
  try {
    const res = await fetch(inventoryApiBase(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, reserved_quantity: payload.reserved_quantity ?? 0, low_stock_threshold: payload.low_stock_threshold ?? 10 }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as InventoryItem };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function updateInventoryItem(
  itemId: string,
  payload: { current_stock?: number; reserved_quantity?: number; low_stock_threshold?: number },
): Promise<{ ok: true; data: InventoryItem } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${inventoryApiBase()}/${itemId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as InventoryItem };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---------------------------------------------------------------------------
// Automation
// ---------------------------------------------------------------------------

export type AutomationSessionStatus = "idle" | "running" | "waiting_approval" | "completed" | "failed" | "stopped";

export interface AutomationSession {
  id: string;
  environment: string;
  status: AutomationSessionStatus;
  current_action: string | null;
  last_result: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface AutomationSessionListResponse {
  items: AutomationSession[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface NormalizedAddress {
  first_name: string;
  last_name: string;
  address_line_1: string;
  address_line_2?: string;
  city: string;
  state: string;
  postal_code: string;
  country?: string;
  phone?: string;
}

function automationApiBase(): string {
  return `${API_BASE_URL}/api/v1/automation`;
}

export async function createAutomationSession(): Promise<{ ok: true; data: AutomationSession } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${automationApiBase()}/sessions?environment=sandbox`, {
      method: "POST",
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AutomationSession };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchAutomationSessions(
  page = 1,
  pageSize = 50,
): Promise<{ ok: true; data: AutomationSessionListResponse } | { ok: false; error: string }> {
  try {
    const res = await fetch(
      `${automationApiBase()}/sessions?page=${page}&page_size=${pageSize}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AutomationSessionListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function stopAutomationSession(
  sessionId: string,
): Promise<{ ok: true; data: AutomationSession } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${automationApiBase()}/sessions/${sessionId}/stop`, {
      method: "POST",
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AutomationSession };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fillAutomationForm(
  sessionId: string,
  address: NormalizedAddress,
  shippingMethod: string = "standard",
): Promise<{ ok: true; data: { success: boolean; filled_fields: string[]; error_message: string | null } } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${automationApiBase()}/sessions/${sessionId}/fill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, address, shipping_method: shippingMethod }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as { success: boolean; filled_fields: string[]; error_message: string | null } };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---------------------------------------------------------------------------
// Address Processing
// ---------------------------------------------------------------------------

export type AddressProcessingStatus = "pending" | "processed" | "needs_review" | "failed";

export interface ValidationIssue {
  field: string;
  message: string;
  severity: "error" | "warning" | "info";
}

export interface AddressProcessingResult {
  id: string;
  raw_address: string;
  first_name: string;
  last_name: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
  status: AddressProcessingStatus;
  confidence: number;
  validation_issues: ValidationIssue[];
  review_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface AddressProcessingListResponse {
  items: AddressProcessingResult[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

function addressApiBase(): string {
  return `${API_BASE_URL}/api/v1/address`;
}

export async function parseAddress(
  rawAddress: string,
): Promise<{ ok: true; data: AddressProcessingResult } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${addressApiBase()}/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_address: rawAddress }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AddressProcessingResult };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchAddressResults(
  page = 1,
  pageSize = 50,
  statusFilter?: AddressProcessingStatus,
): Promise<{ ok: true; data: AddressProcessingListResponse } | { ok: false; error: string }> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (statusFilter) params.set("status", statusFilter);
    const res = await fetch(
      `${addressApiBase()}?${params.toString()}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AddressProcessingListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function reviewAddress(
  resultId: string,
  action: "approve" | "correct" | "reject",
  corrections?: Partial<NormalizedAddress>,
): Promise<{ ok: true; data: AddressProcessingResult } | { ok: false; error: string }> {
  try {
    const payload: Record<string, unknown> = { action, ...corrections };
    const res = await fetch(`${addressApiBase()}/${resultId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AddressProcessingResult };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---------------------------------------------------------------------------
// Fulfillment
// ---------------------------------------------------------------------------

export type FulfillmentStatus =
  | "pending"
  | "running"
  | "waiting_approval"
  | "approved"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired";

export type FulfillmentStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "waiting_approval";

export interface FulfillmentStep {
  name: string;
  description: string;
  status: FulfillmentStepStatus;
  result: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface SupplierOrderPayload {
  sku: string;
  product_name: string;
  quantity: number;
  first_name: string;
  last_name: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
  shipping_method: string;
}

export interface FulfillmentConfirmation {
  confirmation_id: string;
  supplier: string;
  status: string;
  submitted_at: string;
  estimated_delivery: string;
}

export interface FulfillmentWorkflow {
  id: string;
  order_id: string;
  status: FulfillmentStatus;
  steps: FulfillmentStep[];
  current_step: number;
  supplier_payload: SupplierOrderPayload | null;
  confirmation: FulfillmentConfirmation | null;
  approval_request_id: string | null;
  approval_requested_at: string | null;
  approval_expires_at: string | null;
  retry_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface FulfillmentListResponse {
  items: FulfillmentWorkflow[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

function fulfillmentApiBase(): string {
  return `${API_BASE_URL}/api/v1/fulfillment`;
}

export async function startFulfillment(
  orderId: string,
  shippingMethod: string = "standard",
): Promise<{ ok: true; data: FulfillmentWorkflow } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${fulfillmentApiBase()}/${orderId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shipping_method: shippingMethod }),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentWorkflow };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchFulfillmentWorkflows(
  page = 1,
  pageSize = 50,
): Promise<{ ok: true; data: FulfillmentListResponse } | { ok: false; error: string }> {
  try {
    const res = await fetch(
      `${fulfillmentApiBase()}?page=${page}&page_size=${pageSize}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchFulfillmentWorkflow(
  workflowId: string,
): Promise<{ ok: true; data: FulfillmentWorkflow } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${fulfillmentApiBase()}/${workflowId}`, {
      cache: "no-store",
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentWorkflow };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function approveFulfillment(
  workflowId: string,
): Promise<{ ok: true; data: FulfillmentWorkflow } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${fulfillmentApiBase()}/${workflowId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentWorkflow };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function rejectFulfillment(
  workflowId: string,
): Promise<{ ok: true; data: FulfillmentWorkflow } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${fulfillmentApiBase()}/${workflowId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentWorkflow };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function cancelFulfillment(
  workflowId: string,
): Promise<{ ok: true; data: FulfillmentWorkflow } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${fulfillmentApiBase()}/${workflowId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentWorkflow };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function retryFulfillment(
  workflowId: string,
): Promise<{ ok: true; data: FulfillmentWorkflow } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${fulfillmentApiBase()}/${workflowId}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as FulfillmentWorkflow };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

export interface ProviderInfo {
  name: string;
  environment: string;
  is_mock: boolean;
  capabilities: Record<string, boolean>;
}

export interface ProviderListResponse {
  providers: ProviderInfo[];
  mock_only: boolean;
  environment: string;
  notice: string;
}

function providersApiBase(): string {
  return `${API_BASE_URL}/api/v1/providers`;
}

export async function fetchProviders(): Promise<{ ok: true; data: ProviderListResponse } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${providersApiBase()}`, { cache: "no-store" });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as ProviderListResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

// ---------------------------------------------------------------------------
// Amazon Sandbox (CHUNK 1V)
// ---------------------------------------------------------------------------

export interface AmazonConnectionStatus {
  configured: boolean;
  sandbox: boolean;
  environment: string;
  mode: string;
  region?: string;
  marketplace_id?: string;
  credentials_available?: boolean;
  token_expires_in?: number;
  token_refresh_count?: number;
  request_stats?: {
    total_requests: number;
    successful_requests: number;
    failed_requests: number;
    is_sandbox: boolean;
  };
  orders_retrieved?: number;
  orders_normalized?: number;
  provider?: string;
  notice?: string;
}

export interface AmazonOrder {
  order_id: string;
  amazon_order_id?: string;
  sku: string;
  product_name: string;
  quantity: number;
  customer_name: string;
  shipping_address: string;
  order_status: string;
  fulfillment_channel?: string;
  purchase_date?: string;
  source: string;
  marketplace_id?: string;
  created_at: string;
}

export interface AmazonOrdersResponse {
  orders: AmazonOrder[];
  total: number;
  provider: string | null;
  sandbox: boolean;
  environment: string;
  mode: string;
  notice?: string;
}

export interface AmazonImportResponse {
  imported: string[];
  total: number;
  provider: string | null;
  sandbox: boolean;
  environment: string;
  notice?: string;
}

export interface AmazonInfo {
  api_version: string;
  sandbox: boolean;
  environment: string;
  mode: string;
  endpoints: Record<string, string>;
  rate_limits: {
    requests_per_second: number;
    burst: number;
  };
  supported_operations: string[];
  blocked_operations: string[];
  notice: string;
}

function amazonApiBase(): string {
  return `${API_BASE_URL}/api/v1/amazon`;
}

export async function fetchAmazonStatus(): Promise<{ ok: true; data: AmazonConnectionStatus } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${amazonApiBase()}/status`, { cache: "no-store" });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AmazonConnectionStatus };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchAmazonOrders(
  limit = 50,
  offset = 0,
): Promise<{ ok: true; data: AmazonOrdersResponse } | { ok: false; error: string }> {
  try {
    const res = await fetch(
      `${amazonApiBase()}/orders?limit=${limit}&offset=${offset}`,
      { cache: "no-store" },
    );
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AmazonOrdersResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function importAmazonOrders(
  orderIds?: string[],
): Promise<{ ok: true; data: AmazonImportResponse } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${amazonApiBase()}/orders/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(orderIds ?? []),
    });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AmazonImportResponse };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}

export async function fetchAmazonInfo(): Promise<{ ok: true; data: AmazonInfo } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${amazonApiBase()}/info`, { cache: "no-store" });
    const body: unknown = await res.json();
    if (!res.ok || isApiError(body)) {
      return { ok: false, error: isApiError(body) ? body.error : `HTTP ${res.status}` };
    }
    return { ok: true, data: body as AmazonInfo };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
}
