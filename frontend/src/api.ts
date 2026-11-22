// All calls to our own backend. The browser never talks to PVGIS directly.

export type Site = {
  id: number;
  clientName: string;
  address: string;
  latitude: number;
  longitude: number;
  roofAreaM2: number | null;
  peakKwp: number;
};

export type Production = {
  yearlyKwh: number;
  monthlyKwh: { month: number; kwh: number }[];
};

export type Scenario = {
  selfUsedKwh: number;
  gridExportKwh: number;
  gridImportKwh: number;
  selfConsumptionPct: number;
  selfSufficiencyPct: number;
};

export type BatteryResult = {
  productionKwh: number;
  consumptionKwh: number;
  withoutBattery: Scenario;
  withBattery: Scenario;
};

type Me = { email: string; csrfToken: string };

/** An error answer from the API, with the per-field messages of a 422. */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

// The CSRF token lives only in memory (not in localStorage), so other scripts
// cannot find it lying around. After a page reload /api/me hands it out again.
let csrfToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

/** Called when a request gets 401 while we thought we were logged in (session expired). */
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin", // send the session cookie, only to our own server
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error; // the page no longer needs this answer
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }

  if (response.status === 401 && csrfToken !== null) onUnauthorized?.();
  if (response.status === 204) return undefined as T;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof data?.detail === "string" ? data.detail : `Request failed (HTTP ${response.status}).`;
    throw new ApiError(response.status, message, data?.errors ?? {});
  }
  return data as T;
}

/** The body for POST/PUT /api/sites. Values the user typed that are not
 * numbers are sent as they are, so the server's per-field message explains it. */
export type SitePayload = Record<string, string | number | null>;

export const api = {
  me: (signal?: AbortSignal) => request<Me>("GET", "/api/me", undefined, signal),
  login: (email: string, password: string) => request<Me>("POST", "/api/login", { email, password }),
  register: (email: string, password: string) => request<Me>("POST", "/api/register", { email, password }),
  logout: () => request<void>("POST", "/api/logout"),

  listSites: (signal?: AbortSignal) => request<Site[]>("GET", "/api/sites", undefined, signal),
  getSite: (id: string, signal?: AbortSignal) =>
    request<Site>("GET", `/api/sites/${encodeURIComponent(id)}`, undefined, signal),
  createSite: (payload: SitePayload) => request<Site>("POST", "/api/sites", payload),
  updateSite: (id: string, payload: SitePayload) =>
    request<Site>("PUT", `/api/sites/${encodeURIComponent(id)}`, payload),
  deleteSite: (id: string) => request<void>("DELETE", `/api/sites/${encodeURIComponent(id)}`),

  production: (id: string, signal?: AbortSignal) =>
    request<Production>("GET", `/api/sites/${encodeURIComponent(id)}/production`, undefined, signal),
  battery: (id: string, capacityKwh: number, annualUseKwh: number, signal?: AbortSignal) => {
    const query = new URLSearchParams({
      capacityKwh: String(capacityKwh),
      annualUseKwh: String(annualUseKwh),
    });
    return request<BatteryResult>("GET", `/api/sites/${encodeURIComponent(id)}/battery?${query}`, undefined, signal);
  },
};

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}
