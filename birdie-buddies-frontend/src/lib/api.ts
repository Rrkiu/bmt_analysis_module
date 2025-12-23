// src/lib/api.ts
const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type User = {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  is_admin: boolean;
}; // /auth/me, /auth/verify-otp :contentReference[oaicite:0]{index=0}

export type Session = {
  id: string;
  title?: string | null;
  starts_at_utc: string; // ISO (UTC)
  timezone: string; // IANA tz
  capacity: number;
  fee_cents: number; // price in cents
  status: "scheduled" | "closed" | "canceled";
  created_at: string;
  confirmed_seats: number;
  remaining_seats: number;
  waitlist_seats: number;
}; // /sessions*, SessionWithStatsOut :contentReference[oaicite:1]{index=1}

export type RegRow = {
  registration_id: string;
  host_user_id: string;
  host_name: string;
  seats: number;
  guest_names?: string[] | null;
  waitlist_pos?: number | null;
  state: "confirmed" | "waitlisted" | "canceled";
  group_key?: string | null;
  is_host?: boolean;
  canceled_at?: string | null;
  canceled_from_state?: "confirmed" | "waitlisted" | null;
};

export type MyRegistration = {
  registration_id: string;
  session_id: string;
  session_title?: string | null;
  starts_at_utc: string; // ISO (UTC)
  timezone: string; // IANA
  session_status: "scheduled" | "closed" | "canceled";
  seats: number;
  guest_names?: string[] | null;
  waitlist_pos?: number | null;
  state: "confirmed" | "waitlisted" | "canceled";
  group_key?: string | null;
  is_host?: boolean;
}; // list regs for a session + my regs :contentReference[oaicite:2]{index=2}

export type RequestStatus = {
  state: "queued" | "confirmed" | "waitlisted" | "rejected";
  session_id: string;
  user_id: string;
  seats: number;
  guest_names: string[];
  created_at: string;
  registration_id?: string | null;
  waitlist_pos?: number | null;
}; // /requests/{id}/status :contentReference[oaicite:3]{index=3}

export type CancelOut = {
  refund_cents: number;
  penalty_cents: number;
  state: "canceled";
}; // /registrations/{id}/cancel :contentReference[oaicite:4]{index=4}

export type Wallet = {
  posted_cents: number;
  holds_cents: number;
  available_cents: number;
}; // /wallet/me :contentReference[oaicite:5]{index=5}
export type WalletTotals = {
  total_posted_cents: number;
  total_holds_cents: number;
  total_available_cents: number;
}; // /admin/wallets/summary

export type WalletLedgerRow = {
  id: number;
  kind: string;
  amount_cents: number;
  session_id?: string | null;
  registration_id?: string | null;
  created_at: string;
  session_title?: string | null; // For display purposes
  starts_at_utc?: string | null; // For display purposes
}; // /wallet/me/ledger :contentReference[oaicite:6]{index=6}

// Keep the existing function but make it more robust
export function dollarsFromCents(v: number | null | undefined): string {
  return (Number(v ?? 0) / 100).toFixed(2);
}

// Add a formatted version that includes the $ symbol
export function formatDollarsFromCents(v: number | null | undefined): string {
  return `$${dollarsFromCents(v)}`;
}

export function UTCtohhmmTimeForamt(date: Date): string {
  let hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";

  hours = hours % 12;
  hours = hours ? hours : 12; // the hour '0' should be '12'

  return `${hours}:${minutes} ${ampm}`;
}

export async function http<T>(
  path: string,
  init: Omit<RequestInit, "body"> & { body?: unknown } = {}
): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...(init.headers || {}),
  };

  // If body is a plain object (not string/FormData), JSON-encode it once.
  let body = (init as any).body;
  const isJson = headers["Content-Type"]
    ?.toLowerCase()
    .includes("application/json");
  if (
    body != null &&
    isJson &&
    typeof body !== "string" &&
    !(body instanceof FormData)
  ) {
    body = JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...init,
    headers,
    body,
  });

  if (!res.ok) {
    let detail = await res.text().catch(() => "");
    try {
      const j = JSON.parse(detail);
      detail = j.detail ?? detail;
    } catch {}
    throw new Error(detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

/* -------- Auth -------- */
export async function me(): Promise<User> {
  return http<User>("/auth/me"); // :contentReference[oaicite:7]{index=7}
}
export const requestOtp = (email: string) =>
  http<{ sent: boolean; ttl_sec: number }>("/auth/request-otp", {
    method: "POST",
    body: { email: email.trim().toLowerCase() },
  });

// export const verifyOtp = (
//   email: string,
//   code: string,
//   name?: string,
//   phone?: string
// ) =>
//   http<User>("/auth/verify-otp", {
//     method: "POST",
//     body: {
//       email: email.trim().toLowerCase(),
//       // keep leading zeros (do NOT Number() it)
//       code: String(code).replace(/\D/g, "").padStart(6, "0"),
//       ...(name ? { name: name.trim() } : {}),
//       ...(phone ? { phone: phone.trim() } : {}),
//     },
//   });

export async function logout(): Promise<void> {
  await http<void>("/auth/logout", { method: "POST", credentials: "include" }); // :contentReference[oaicite:10]{index=10}
}

/* -------- Sessions -------- */
export async function listSessions(): Promise<Session[]> {
  return http<Session[]>("/sessions"); // :contentReference[oaicite:11]{index=11}
}
export async function getSession(sessionId: string): Promise<Session> {
  return http<Session>(`/sessions/${sessionId}`); // :contentReference[oaicite:12]{index=12}
}

/* -------- Admin: Session History -------- */
export async function adminListSessionHistory(
  limit = 15,
  offset = 0
): Promise<Session[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return http<Session[]>(`/admin/sessions/history?${params.toString()}`);
}

/* -------- Registrations / Requests -------- */
export async function listRegistrationsForSession(
  sessionId: string
): Promise<RegRow[]> {
  return http<RegRow[]>(`/sessions/${sessionId}/registrations`); // :contentReference[oaicite:13]{index=13}
}

// TODO: Lazy loading
// type PageResult = { rows: RegRow[]; nextOffset?: number };
// export async function listRegistrationsForSession(
//   sessionId: string,
//   limit: number,
//   offset = 0
// ): Promise<PageResult> {
//   const params = new URLSearchParams({
//     limit: String(limit),
//     offset: String(offset),
//   });
//   const rows = await http<RegRow[]>(
//     `/sessions/${sessionId}/registrations?${params}`
//   );
//   return { rows, nextOffset: rows.length < limit ? undefined : offset + limit };
// }

export async function myRegistrations(
  showPast = false
): Promise<MyRegistration[]> {
  const params = showPast ? "?show_past=true" : "";
  return http<MyRegistration[]>(`/me/registrations${params}`);
}

export async function enqueueRegistration(
  sessionId: string,
  seats: number,
  guest_names: string[],
  idempotencyKey?: string
): Promise<{ request_id: string; state: "queued" }> {
  const key = idempotencyKey ?? crypto?.randomUUID?.() ?? String(Date.now());
  return http(`/sessions/${sessionId}/register`, {
    method: "POST",
    headers: { "Idempotency-Key": key }, // required :contentReference[oaicite:15]{index=15}
    body: { seats, guest_names },
  });
}

export async function getRequestStatus(
  requestId: string
): Promise<RequestStatus> {
  return http<RequestStatus>(`/requests/${requestId}/status`); // :contentReference[oaicite:16]{index=16}
}

export async function cancelRegistration(
  registrationId: string
): Promise<CancelOut> {
  return http<CancelOut>(`/registrations/${registrationId}/cancel`, {
    method: "POST",
  }); // :contentReference[oaicite:17]{index=17}
}

/* -------- Wallet -------- */
export type WalletSummary = {
  posted_cents: number;
  holds_cents: number;
  available_cents: number;
};

export function getMyWallet(): Promise<WalletSummary> {
  return http<WalletSummary>("/wallet/me", { method: "GET" });
}

// export async function getMyWallet(): Promise<Wallet> {
//   return http<Wallet>("/wallet/me"); // :contentReference[oaicite:18]{index=18}
// }
export async function getMyWalletLedger(
  limit = 50,
  beforeId?: number
): Promise<WalletLedgerRow[]> {
  const q = new URLSearchParams({
    limit: String(limit),
    ...(beforeId ? { before_id: String(beforeId) } : {}),
  });
  return http<WalletLedgerRow[]>(`/wallet/me/ledger?${q.toString()}`); // :contentReference[oaicite:19]{index=19}
}

export function adminWalletSummary(): Promise<WalletTotals> {
  return http<WalletTotals>("/admin/wallets/summary", { method: "GET" });
}

/* -------- Admin (create session) -------- */
export async function adminCreateSession(input: {
  title?: string | null;
  starts_at_utc: string; // must be UTC & tz-aware
  timezone: string; // IANA tz
  capacity: number;
  fee_cents: number;
}) {
  return http<Session>("/admin/sessions", {
    method: "POST",
    body: input,
  }); // :contentReference[oaicite:20]{index=20}
}

// --- types (near your other wallet/admin types) ---
export type AdminDepositOut = {
  id: number;
  kind: string; // "deposit_in"
  amount_cents: number;
  user_id: string;
  session_id?: string | null;
  registration_id?: string | null;
  created_at: string; // ISO
};

// api.ts
export function newIdempotencyKey(): string {
  // Prefer Web Crypto; fall back to a tiny random if needed
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  // last-resort fallback (still very low collision risk)
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function adminDeposit(
  user_id: string,
  amount_cents: number,
  idempotencyKey: string // <-- required
) {
  if (!idempotencyKey) throw new Error("idempotencyKey is required");
  return http<AdminDepositOut>("/admin/deposits", {
    method: "POST",
    body: { user_id, amount_cents, idempotency_key: idempotencyKey },
  });
}

// ========= Admin: Sessions =========

export type SessionPatchPayload = {
  capacity?: number; // > 0
  status?: "scheduled" | "closed" | "canceled";
};

// PATCH /admin/sessions/{id}
export function adminPatchSession(
  sessionId: string,
  payload: SessionPatchPayload
) {
  return http<Session>(`/admin/sessions/${sessionId}`, {
    method: "PATCH",
    body: payload, // or JSON.stringify(payload) if your http() doesn't auto-encode
  });
}

// ========= Admin: Users =========

// Rows in the admin users list
export type AdminUserRow = {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  is_admin: boolean;
  status: string; // e.g. "active"
  created_at: string; // ISO
  posted_cents: number;
  holds_cents: number;
  available_cents: number; // posted - holds
};

export type AdminUserListOut = {
  items: AdminUserRow[];
  total: number;
};

// GET /admin/users?q=&limit=&offset=
export function adminListUsers(q?: string, limit = 50, offset = 0) {
  const qs = new URLSearchParams();
  if (q && q.trim()) qs.set("q", q.trim());
  qs.set("limit", String(limit));
  qs.set("offset", String(offset));
  return http<AdminUserListOut>(`/admin/users?${qs.toString()}`);
}

// ========= Admin: User detail =========

export type AdminUserWallet = {
  posted_cents: number;
  holds_cents: number;
  available_cents: number;
};

export type AdminLedgerRow = {
  id: number;
  kind: string; // e.g. "deposit_in" | "fee_capture" | ...
  amount_cents: number;
  session_id?: string | null;
  registration_id?: string | null;
  created_at: string; // ISO
  session_title?: string | null; // For display purposes
  starts_at_utc?: string | null; // For display purposes
};

export type AdminRegistrationRow = {
  registration_id: string;
  session_id: string;
  session_title?: string | null;
  starts_at_utc: string; // ISO (UTC)
  timezone: string; // IANA
  seats: number;
  guest_names: string[];
  state: string; // "confirmed" | "waitlisted" | "canceled"
  waitlist_pos?: number | null;
  created_at: string; // ISO
  canceled_at?: string | null;
};

export type AdminUserDetailOut = {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  is_admin: boolean;
  status: string;
  created_at: string; // ISO
  wallet: AdminUserWallet;
  ledger: AdminLedgerRow[]; // most recent first
  registrations: AdminRegistrationRow[]; // with session info
};

// GET /admin/users/{user_id}?ledger_limit=100
export function adminGetUser(userId: string, ledger_limit = 100) {
  const qs = new URLSearchParams({ ledger_limit: String(ledger_limit) });
  return http<AdminUserDetailOut>(`/admin/users/${userId}?${qs.toString()}`);
}

// --- Types (near your other registration types) ---
export type GuestAddOut = {
  registration_id: string;
  state: "confirmed" | "waitlisted";
  waitlist_pos?: number | null;
};

// --- Function ---
export async function addGuest(
  hostRegistrationId: string,
  name: string
): Promise<GuestAddOut> {
  // Send exactly { name } to POST /registrations/{host_registration_id}/guests
  const raw = await http<any>(`/registrations/${hostRegistrationId}/guests`, {
    method: "POST",
    body: { name },
  });

  // Normalize possible backend key variants (reg_id/pos vs registration_id/waitlist_pos)
  return {
    registration_id: raw?.registration_id ?? raw?.reg_id ?? raw?.id,
    state: raw?.state,
    waitlist_pos: raw?.waitlist_pos ?? raw?.pos ?? null,
  } as GuestAddOut;
}

// =====================
// Admin prereg: DTOs
// =====================

export type UUID = string;

export type AdminPreregItemIn = {
  user_id: UUID;
  seats: 1 | 2 | 3;
  /** 0..2 names; seats must equal 1 + guest_names.length */
  guest_names?: string[];
  /** optional idempotency key; if omitted, server may treat as best-effort */
  idempotency_key?: string;
};

export type AdminPreregResultOut = {
  user_id: UUID;
  registration_id?: UUID | null;
  state: "confirmed" | "waitlisted" | "rejected";
  waitlist_pos?: number | null;
  error?: string | null;
};

// Your file already defines `Session` and `adminCreateSession`.
// We'll add a new input shape that extends the existing create payload with preregs:
export type SessionCreateInWithPrereg = {
  title?: string | null;
  /** ISO string, must be UTC & tz-aware per backend contract */
  starts_at_utc: string;
  /** IANA TZ name, e.g. "America/Vancouver" */
  timezone: string;
  capacity: number;
  fee_cents: number;
  preregistrations?: AdminPreregItemIn[];
};

export type SessionCreateWithPreregOut = {
  session: Session;
  prereg_result: AdminPreregResultOut[];
};

/**
 * New (non-breaking) variant: create a session and optionally preregister users
 * Returns { session, prereg_result }.
 * Keep your existing adminCreateSession() for places that don't use prereg.
 */
export async function adminCreateSessionWithPrereg(
  input: SessionCreateInWithPrereg
): Promise<SessionCreateWithPreregOut> {
  const res = await fetch(`${BASE}/admin/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    // surface backend errors (409, 403, etc.) to caller
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as SessionCreateWithPreregOut;
}

// =====================
// Admin: user management
// =====================

export type AdminUserPatchIn = {
  name?: string;
  email?: string;
  phone?: string;
  status?: "active" | "disabled";
  is_admin?: boolean;
};

/** PATCH /admin/users/{id} — 204 on success */
export async function adminPatchUser(
  userId: UUID,
  body: AdminUserPatchIn
): Promise<void> {
  const res = await fetch(`${BASE}/admin/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
}

/** DELETE /admin/users/{id} — soft delete, 204 on success */
export async function adminDeleteUser(userId: UUID): Promise<void> {
  const res = await fetch(`${BASE}/admin/users/${userId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
}

// New auth flow functions
export async function checkEmail(email: string): Promise<{ exists: boolean }> {
  return http<{ exists: boolean }>("/auth/check-email", {
    method: "POST",
    body: { email: email.trim().toLowerCase() },
  });
}

export async function login(email: string, phone: string): Promise<User> {
  return http<User>("/auth/login", {
    method: "POST",
    body: { email: email.trim().toLowerCase(), phone: phone.trim() },
  });
}

export async function signup(
  email: string,
  name: string,
  phone: string
): Promise<{ message: string; requires_otp: boolean }> {
  return http("/auth/signup", {
    method: "POST",
    body: {
      email: email.trim().toLowerCase(),
      name: name.trim(),
      phone: phone.trim(),
    },
  });
}

export async function verifyOtp(email: string, otp: string): Promise<User> {
  return http<User>("/auth/verify-otp-new", {
    method: "POST",
    body: {
      email: email.trim().toLowerCase(),
      otp: otp.trim(),
    },
  });
}
