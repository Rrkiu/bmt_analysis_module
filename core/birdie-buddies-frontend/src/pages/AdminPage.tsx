// src/pages/AdminPage.tsx
import React, { useMemo, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import MobileShell from "../components/MobileShell/MobileShell";
import {
  // sessions
  listSessions,
  adminCreateSession,
  adminPatchSession,
  // users
  adminListUsers,
  adminGetUser,
  adminDeposit,
  newIdempotencyKey,
  adminPatchUser,
  adminDeleteUser,
  type AdminUserRow,
  adminWalletSummary,
  type WalletTotals,
} from "../lib/api";

import FlashBanners from "../components/UI/FlashBanners";
import { flashSuccess, flashError } from "../lib/flash";
import ClickDropdown, { type Option } from "../components/UI/ClickDropdown";
import { formatDollarsFromCents } from "../lib/api";
import { useDebounce } from "../hooks/useDebounce";

/* ---------------- Helpers ---------------- */

type DateOption = { label: string; value: string }; // YYYY-MM-DD
type TimeOption = { label: string; value: string }; // HH:mm (24h)
type PreregItem = {
  user_id: string;
  name: string;
  seats: Number;
  // guest_names: string[]; // 0..2
};

// function assertSeatsMatchGuests(i: PreregItem) {
//   return i.seats === 1 + (i.guest_names?.length ?? 0);
// }

/** Build "Aug 20, Wednesday" for the next N days */
function buildDateOptions(days = 21): DateOption[] {
  const res: DateOption[] = [];
  const now = new Date();
  for (let i = 0; i < days; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const value = `${y}-${m}-${day}`;
    const monthShort = d.toLocaleString("en-US", { month: "short" });
    const weekdayLong = d.toLocaleString("en-US", { weekday: "long" });
    const label = `${monthShort} ${day}, ${weekdayLong}`;
    res.push({ label, value });
  }
  return res;
}

/** Combine local YYYY-MM-DD + HH:mm into UTC ISO string */
function localDateTimeToUTCISO(
  localDateYYYYMMDD: string,
  hhmm: string
): string {
  const isoLocal = `${localDateYYYYMMDD}T${hhmm}:00`; // treated as local
  const date = new Date(isoLocal);
  return date.toISOString(); // UTC Z string
}

function UTCtohhmmTimeForamt(date: Date): string {
  let hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";

  hours = hours % 12;
  hours = hours ? hours : 12; // the hour '0' should be '12'

  return `${hours}:${minutes} ${ampm}`;
}

function displayKind(kind: string) {
  const k = (kind || "").toLowerCase();
  if (k === "deposit_in" || k === "deposit-in") return "Deposit";
  if (k === "fee_capture") return "Drop-in paid";
  if (k === "refund") return "Refund";
  if (k === "penalty") return "Penalty";
  if (k === "hold") return "Hold waitlist";
  if (k === "hold_release") return "Cancel waitlist";
  return k.replace(/_/g, "-"); // fallback
}

/** Format ISO date -> "MM DD" */
function mmdd(iso: string) {
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${mm}/${dd}`;
}

/** Hide fee-hold / hold-release ledger kinds */
// function isHiddenKind(kind: string) {
//   return /^(fee[_-]?hold|hold[_-]?release)$/i.test(kind || "");
// }

/* ---------------- Page ---------------- */

type Tab = "create" | "update" | "users";

export default function AdminPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("create");
  const walletTotals = useQuery<WalletTotals>({
    queryKey: ["admin-wallet-summary"],
    queryFn: adminWalletSummary,
  });

  return (
    <MobileShell>
      <h1 className="page-title">Admin</h1>

      <div className="detail-container" style={{ gap: 16 }}>
        <FlashBanners />

        <div className="admin-header-container">
          {walletTotals.isLoading ? (
            <div className="skeleton" style={{ height: 56, width: "100%" }} />
          ) : walletTotals.error ? (
            <div className="error">Failed to load wallet totals.</div>
          ) : walletTotals.data ? (
            <div className="stat-container">
              <div className="admin-header">Financial Status</div>
              <div className="stat-info">
                <div className="stat-item">
                  <div className="stat-value">
                    {formatDollarsFromCents(
                      walletTotals.data.total_posted_cents
                    )}
                  </div>
                  <div className="stat-label">Total Posted</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">
                    {formatDollarsFromCents(
                      walletTotals.data.total_holds_cents
                    )}
                  </div>
                  <div className="stat-label">Total Holds</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">
                    {formatDollarsFromCents(
                      walletTotals.data.total_available_cents
                    )}
                  </div>
                  <div className="stat-label">Total Available</div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Horizontally scrollable tab strip */}
        <div
          className="filter-tabs scroll-x"
          role="tablist"
          aria-label="Admin sections"
        >
          <button
            className={`filter-tab ${tab === "users" ? "active" : ""}`}
            onClick={() => setTab("users")}
            role="tab"
            aria-selected={tab === "users"}
          >
            Users
          </button>
          <button
            className={`filter-tab ${tab === "create" ? "active" : ""}`}
            onClick={() => setTab("create")}
            role="tab"
            aria-selected={tab === "create"}
          >
            Create Session
          </button>
          <button
            className={`filter-tab ${tab === "update" ? "active" : ""}`}
            onClick={() => setTab("update")}
            role="tab"
            aria-selected={tab === "update"}
          >
            Update Session
          </button>
        </div>

        {tab === "create" && (
          <CreateSessionCard
            onCreated={() => qc.invalidateQueries({ queryKey: ["sessions"] })}
          />
        )}
        {tab === "update" && <UpdateSessionCard />}
        {tab === "users" && <UsersAdminCard />}
      </div>
    </MobileShell>
  );
}

/* ---------------- Create Session ---------------- */

function CreateSessionCard({ onCreated }: { onCreated: () => void }) {
  const [timezone] = useState("America/Vancouver"); // fixed per your UX
  const [capacity, setCapacity] = useState(52);
  const [priceDollars, setPriceDollars] = useState(13.5);
  const [preregs, setPreregs] = useState<PreregItem[]>([]);
  const [isManuallyEdited, setIsManuallyEdited] = useState(false);

  /** Default time slots (edit as needed) */
  const DEFAULT_TIMES: TimeOption[] = [
    { label: "2:00 PM", value: "14:00" },
    { label: "2:30 PM", value: "14:30" },
    { label: "3:00 PM", value: "15:00" },
    { label: "3:30 PM", value: "15:30" },
    { label: "4:00 PM", value: "16:00" },
    { label: "4:30 PM", value: "16:30" },
    { label: "5:00 PM", value: "17:00" },
    { label: "5:30 PM", value: "17:30" },
    { label: "6:00 PM", value: "18:00" },
    { label: "6:30 PM", value: "18:30" },
    { label: "7:00 PM", value: "19:00" },
    { label: "7:30 PM", value: "19:30" },
    { label: "8:00 PM", value: "20:00" },
    { label: "8:30 PM", value: "20:30" },
    { label: "9:00 PM", value: "21:00" },
    { label: "9:30 PM", value: "21:30" },
    { label: "10:00 PM", value: "22:00" },
    { label: "10:30 PM", value: "22:30" },
    { label: "11:00 PM", value: "23:00" },
    { label: "11:30 PM", value: "23:30" },
  ];

  // keep your helpers:
  const dateOptions: Option[] = useMemo(() => buildDateOptions(21), []);
  const [dateVal, setDateVal] = useState<string>(dateOptions[0].value);
  const [timeVal, setTimeVal] = useState<string>(DEFAULT_TIMES[12].value);

  // Auto-set title based on selected date
  const autoTitle = useMemo(() => {
    const selectedDate = dateOptions.find((opt) => opt.value === dateVal);
    return selectedDate?.label || "";
  }, [dateVal, dateOptions]);

  const [title, setTitle] = useState(autoTitle);

  // Update title when date changes (unless user manually edited it)
  React.useEffect(() => {
    if (!isManuallyEdited) {
      setTitle(autoTitle);
    }
  }, [autoTitle, isManuallyEdited]);
  const starts_at_utc = useMemo(
    () => localDateTimeToUTCISO(dateVal, timeVal),
    [dateVal, timeVal]
  );
  const fee_cents = useMemo(
    () => Math.max(0, Number(priceDollars) * 100),
    [priceDollars]
  );
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: async (input: any) => {
      return adminCreateSession({
        ...input,
        preregistrations: preregs.map((p) => ({
          user_id: p.user_id,
          seats: p.seats,
          // guest_names: p.guest_names,
        })),
      });
    },
    onSuccess: (data) => {
      flashSuccess("✓ Session created!");
      onCreated();
      setPreregs([]);
      setIsManuallyEdited(false); // Reset for next session creation
      navigate(`/admin/sessions/${data.id}`);
    },

    // In case I need to show the result to the admin

    // onSuccess: (data) => {
    //   qc.invalidateQueries({ queryKey: ["sessions"] });
    //   // show results to admin
    //   const ok = data.prereg_result.filter(r => r.state !== "rejected").length;
    //   const rej = data.prereg_result.filter(r => r.state === "rejected").length;
    //   alert(`Session created. Pre-reg: ${ok} ok, ${rej} rejected.`);
    //   setPreregs([]);
    // },
    onError: (e: any) => flashError(String(e?.message || "Create failed")),
  });

  return (
    <>
      <h2 className="section-title">Create Session</h2>

      <div className="form-group">
        <label className="form-label">Title</label>
        <input
          className="form-input"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            setIsManuallyEdited(true);
          }}
          placeholder="Session Title"
        />
      </div>

      <div className="form-group">
        <label className="form-label">Date</label>
        <ClickDropdown
          value={dateVal}
          valueLabel={dateOptions.find((o) => o.value === dateVal)?.label}
          options={dateOptions}
          onSelect={setDateVal}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Time</label>
        <ClickDropdown
          value={timeVal}
          valueLabel={DEFAULT_TIMES.find((o) => o.value === timeVal)?.label}
          options={DEFAULT_TIMES}
          onSelect={setTimeVal}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Capacity</label>
        <input
          className="form-input"
          type="string"
          //   min={0}
          value={capacity}
          onChange={(e) => setCapacity(Math.max(0, +e.target.value))}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Price (per player, $)</label>
        <input
          className="form-input"
          type="string"
          //   min={0}
          //   step={0.5}
          value={priceDollars}
          onChange={(e) =>
            setPriceDollars(e.target.value === "" ? 0 : Number(e.target.value))
          }
        />
      </div>

      <PreregEditor
        value={preregs}
        onChange={setPreregs}
        // Optionally pass a quick users index so rows show names:
        // usersIndex={useMemo(
        //   () => {
        //     // If you already have adminListUsers loaded, build a small map:
        //     // return Object.fromEntries(listUsers.data?.items.map(u => [u.id, u]));
        //     return {};
        //   },
        //   [
        //     /* deps */
        //   ]
        // )}
      />

      <button
        className="btn btn-primary"
        disabled={create.isPending}
        onClick={() =>
          create.mutate({
            title: title.trim() || null,
            starts_at_utc,
            timezone,
            capacity: Number(capacity),
            fee_cents,
          })
        }
      >
        {create.isPending ? "Creating…" : "Complete"}
      </button>
      {create.isError && (
        <div className="error" style={{ marginTop: 8 }}>
          {String((create.error as any)?.message || "Create failed")}
        </div>
      )}
    </>
  );
}

/* ---------------- Update Session ---------------- */

function UpdateSessionCard() {
  const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: listSessions });
  const [sid, setSid] = useState<string>("");
  const s = sessions.data?.find((x) => x.id === sid);
  const sessionOptions: Option[] = React.useMemo(
    () =>
      (sessions.data ?? []).map((x) => ({
        value: x.id,
        label: `${x.title || "Badminton Session"} — ${UTCtohhmmTimeForamt(
          new Date(x.starts_at_utc)
        )}`,
      })),
    [sessions.data]
  );

  const selectedLabel = React.useMemo(
    () => sessionOptions.find((o) => o.value === sid)?.label,
    [sessionOptions, sid]
  );

  const [capacity, setCapacity] = useState<number | "">("");
  const [status, setStatus] = useState<
    "scheduled" | "closed" | "canceled" | ""
  >("");
  type SessionStatus = "scheduled" | "closed" | "canceled";

  const STATUS_OPTIONS: Option[] = [
    { label: "scheduled", value: "scheduled" },
    { label: "closed", value: "closed" },
    { label: "canceled", value: "canceled" },
  ];

  // choose defaults when session changes
  React.useEffect(() => {
    if (s) {
      setCapacity(s.capacity);
      setStatus(s.status as any);
    } else {
      setCapacity("");
      setStatus("");
    }
  }, [sid]);

  const patch = useMutation({
    mutationFn: (payload: {
      capacity?: number;
      status?: "scheduled" | "closed" | "canceled";
    }) => adminPatchSession(sid, payload),
    onSuccess: () => {
      flashSuccess("✓ Session updated");
      qc.invalidateQueries({ queryKey: ["sessions"] });
      if (sid) qc.invalidateQueries({ queryKey: ["session", sid] });
    },
    onError: (e: any) => flashError(String(e?.message || "Update failed")),
  });

  return (
    <>
      <h2 className="section-title">Update Session</h2>

      <div className="form-group">
        <label className="form-label">Select session</label>

        {/* Loading & error states (optional but nice) */}
        {sessions.isLoading && (
          <div className="skeleton" style={{ height: 44 }} />
        )}
        {sessions.error && (
          <div className="error">Failed to load sessions.</div>
        )}

        {!sessions.isLoading && !sessions.error && (
          <ClickDropdown
            value={sid}
            valueLabel={selectedLabel}
            options={[
              // Add a dummy "Select…" option if you want an explicit placeholder
              // { label: "Select…", value: "" },
              ...sessionOptions,
            ]}
            onSelect={setSid}
            placeholder="Select…"
            visibleCount={4} // shows 4 items; rest scroll
            widthPx={340} // optional: widen the panel a bit
          />
        )}
      </div>

      {s && (
        <>
          <div className="session-stats" style={{ marginBottom: 8 }}>
            <div className="stat-item">
              <div className="stat-value">
                {s.confirmed_seats}/{s.capacity}
              </div>
              <div className="stat-label">Registered</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">
                {formatDollarsFromCents(s.fee_cents)}
              </div>
              <div className="stat-label">Per Player</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{s.status}</div>
              <div className="stat-label">Status</div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Capacity</label>
            <input
              className="form-input"
              type="number"
              min={1}
              value={capacity}
              onChange={(e) =>
                setCapacity(
                  e.target.value === "" ? "" : Math.max(1, +e.target.value)
                )
              }
            />
          </div>

          <div className="form-group">
            <label className="form-label">Status</label>
            <ClickDropdown
              value={status || undefined} // let placeholder show if empty
              valueLabel={status || undefined} // displays the selected label
              options={STATUS_OPTIONS}
              onSelect={(v) => setStatus(v as SessionStatus)}
              placeholder="Select status"
              visibleCount={3} // show up to 3, rest scroll
              widthPx={260} // optional: panel width
            />
          </div>

          <button
            className="btn btn-primary"
            disabled={patch.isPending}
            onClick={() =>
              patch.mutate({
                ...(capacity !== "" ? { capacity: Number(capacity) } : {}),
                ...(status ? { status } : {}),
              })
            }
          >
            {patch.isPending ? "Saving…" : "Save Changes"}
          </button>
          {patch.isError && (
            <div className="error" style={{ marginTop: 8 }}>
              {String((patch.error as any)?.message || "Update failed")}
            </div>
          )}
        </>
      )}
    </>
  );
}

/* ---------------- Users (list + detail + deposit) ---------------- */
type EditState = {
  id: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  status?: "active" | "disabled";
  is_admin?: boolean;
};

function UsersAdminCard() {
  const [q, setQ] = useState("");
  const debouncedQ = useDebounce(q, 450); // Debounce search query by 450ms for mobile typing
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditState | null>(null);

  const list = useQuery({
    queryKey: ["admin-users", debouncedQ],
    queryFn: () => adminListUsers(debouncedQ, 200, 0),
  });

  const detail = useQuery({
    queryKey: ["admin-user", selected],
    queryFn: () => adminGetUser(selected as string, 100),
    enabled: !!selected,
  });

  const idemRef = useRef<string>(newIdempotencyKey());

  const qc = useQueryClient();

  const patchUserMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) =>
      adminPatchUser(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const deleteUserMut = useMutation({
    mutationFn: (id: string) => adminDeleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const deposit = useMutation({
    mutationFn: ({
      user_id,
      amount_cents,
    }: {
      user_id: string;
      amount_cents: number;
    }) => adminDeposit(user_id, amount_cents, idemRef.current),
    onSuccess: () => {
      flashSuccess("✓ Deposit applied");
      // Regenerate idempotency key for next deposit
      idemRef.current = newIdempotencyKey();
      // Invalidate queries to refresh data
      if (selected) {
        qc.invalidateQueries({ queryKey: ["admin-user", selected] });
      }
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e: any) => flashError(String(e?.message || "Deposit failed")),
  });

  // visible rows (simple)
  const users = list.data?.items ?? [];

  return (
    <>
      <h2 className="section-title">Users</h2>

      <div className="form-group">
        <label className="form-label">Search</label>
        <input
          className="form-input"
          value={q}
          placeholder="Name or email"
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <div className="participants-section">
        <div className="section-header">
          <h3 className="section-title">User List</h3>
          <span className="participant-count">{users.length}</span>
        </div>

        <div>
          {users.map((u) => (
            <div key={u.id} style={{ marginBottom: "12px" }}>
              <button
                className={`waitlist-item ${selected === u.id ? "active" : ""}`}
                style={{ width: "100%", textAlign: "left" }}
                onClick={() => setSelected(selected === u.id ? null : u.id)}
              >
                {/* <div className="participant-card">
                  <div className="participant-info"> */}
                {/* <div className="participant-avatar">
                  {u.name.slice(0, 2).toUpperCase()}
                </div> */}
                {/* <div className="participant-details"> */}
                <div className="participant-name">
                  {u.name}{" "}
                  {u.is_admin ? (
                    <span className="guest-badge">admin</span>
                  ) : null}
                </div>
                <div className="participant-meta">
                  <div>{u.email.split("@")[0]}</div>{" "}
                  <div>{u.phone ? `• ${u.phone}` : ""}</div>
                </div>
                <div className="stat-value" style={{ marginLeft: "auto" }}>
                  {formatDollarsFromCents(u.available_cents)}
                </div>
                {/* </div>
                  </div> */}
                {/* </div> */}
              </button>

              {/* Inline expanded detail */}
              {selected === u.id && detail.data && (
                <div
                  className="user-detail-expanded animate-in"
                  style={{
                    background: "rgba(16, 185, 129, 0.05)",
                    border: "2px solid var(--primary)",
                    borderRadius: "var(--radius)",
                    padding: "16px",
                    marginTop: "8px",
                  }}
                >
                  {/* Wallet summary + deposit */}
                  <div className="cost-display" style={{ marginTop: 12 }}>
                    <div>
                      <div className="cost-label">Available</div>
                      <div className="cost-value">
                        {formatDollarsFromCents(
                          detail.data.wallet.available_cents
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="cost-label">Posted</div>
                      <div className="cost-value">
                        {formatDollarsFromCents(
                          detail.data.wallet.posted_cents
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="cost-label">Holds</div>
                      <div className="cost-value">
                        {formatDollarsFromCents(detail.data.wallet.holds_cents)}
                      </div>
                    </div>
                  </div>

                  <DepositBox
                    busy={deposit.isPending}
                    onSubmit={(dollars) => {
                      deposit.mutate({
                        user_id: u.id,
                        amount_cents: dollars,
                      });
                    }}
                  />

                  {/* Action buttons */}
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "row",
                      justifyContent: "space-around",
                      marginTop: "12px",
                      gap: "8px",
                    }}
                  >
                    <button
                      className="btn btn-secondary"
                      style={{ flex: 1 }}
                      onClick={() =>
                        setEditing({
                          id: u.id,
                          name: u.name ?? "",
                          email: u.email ?? "",
                          phone: u.phone ?? "",
                          status:
                            (u.status as "active" | "disabled") ?? "active",
                          is_admin: !!u.is_admin,
                        })
                      }
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-danger"
                      style={{ flex: 1 }}
                      onClick={() => {
                        if (
                          confirm(
                            "Soft delete this user? They will be disabled and hidden."
                          )
                        ) {
                          deleteUserMut.mutate(u.id);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>

                  {/* Ledger (compact) */}
                  <div
                    className="participants-section"
                    style={{ marginTop: 16 }}
                  >
                    <div className="section-header">
                      <h4 className="section-title">Recent Ledger</h4>
                      <span className="participant-count">
                        {detail.data.ledger.length}
                      </span>
                    </div>
                    <div>
                      {detail.data.ledger.map((e) => {
                        const kindLabel =
                          displayKind(e.kind) != "Deposit"
                            ? displayKind(e.kind)
                            : e.amount_cents >= 0
                            ? displayKind(e.kind)
                            : "Admin withdrawal";
                        const isHoldKind = /^(hold|hold_release)$/i.test(
                          e.kind || ""
                        );
                        const displayAmountCents = isHoldKind
                          ? -e.amount_cents
                          : e.amount_cents;

                        let label = "";
                        let dateToShow = "";

                        if (e.session_title && e.starts_at_utc) {
                          const sessionDate = mmdd(e.starts_at_utc);
                          label = `${e.session_title} - ${kindLabel}`;
                          dateToShow = sessionDate; // Show session date
                        } else if (e.session_id && e.starts_at_utc) {
                          const sessionDate = mmdd(e.starts_at_utc);
                          label = `Session - ${kindLabel}`;
                          dateToShow = sessionDate; // Show session date
                        } else {
                          label = kindLabel;
                          dateToShow = mmdd(e.created_at); // Show transaction date for non-session entries
                        }

                        return (
                          <div className="waitlist-item" key={e.id}>
                            <div className="waitlist-info">
                              <div className="waitlist-name">{label}</div>
                              <div
                                className="waitlist-seats"
                                style={{
                                  fontSize: "0.85em",
                                  color: "var(--medium)",
                                }}
                              >
                                {dateToShow}
                              </div>
                            </div>
                            <div
                              className="stat-value"
                              style={{ marginLeft: "auto" }}
                            >
                              {displayAmountCents >= 0 ? "+" : "-"}
                              {formatDollarsFromCents(
                                Math.abs(displayAmountCents)
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Registrations (compact) */}
                  <div
                    className="participants-section"
                    style={{ marginTop: 16 }}
                  >
                    <div className="section-header">
                      <h4 className="section-title">Registrations</h4>
                      <span className="participant-count">
                        {detail.data.registrations.length}
                      </span>
                    </div>
                    <div>
                      {detail.data.registrations.map((r) => (
                        <div
                          className="participant-card"
                          key={r.registration_id}
                        >
                          <div className="participant-info">
                            <div className="participant-details">
                              <div className="participant-name">
                                {r.session_title || r.session_id} —{" "}
                                {UTCtohhmmTimeForamt(new Date(r.starts_at_utc))}
                              </div>
                              <div className="participant-meta">
                                {r.seats} seat(s)
                                {r.guest_names?.length
                                  ? ` • ${r.guest_names.join(", ")}`
                                  : ""}
                                {" • "}
                                {r.state}
                                {r.waitlist_pos ? ` #${r.waitlist_pos}` : ""}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                      {detail.isLoading && <div className="skeleton" />}
                      {detail.error && (
                        <div className="error">
                          Failed to load user details.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
          {list.isLoading && <div className="skeleton" />}
          {list.error && <div className="error">Failed to load users.</div>}
          {!list.isLoading && users.length === 0 && (
            <div className="empty-state">No users found.</div>
          )}
        </div>
      </div>
      {editing && (
        <div className="modal-overlay" onClick={() => setEditing(null)}>
          <div
            className="modal-card animate-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="section-title" style={{ marginBottom: 8 }}>
              Edit user
            </div>

            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                className="form-input"
                placeholder="Name"
                value={editing.name ?? ""}
                onChange={(e) =>
                  setEditing({ ...editing, name: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                className="form-input"
                placeholder="Email"
                value={editing.email ?? ""}
                onChange={(e) =>
                  setEditing({ ...editing, email: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label className="form-label">Phone</label>
              <input
                className="form-input"
                placeholder="Phone"
                value={editing.phone ?? ""}
                onChange={(e) =>
                  setEditing({ ...editing, phone: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label className="form-label">Status</label>
              <select
                className="form-input"
                value={editing.status ?? "active"}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    status: e.target.value as "active" | "disabled",
                  })
                }
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </select>
            </div>

            <div
              className="form-group"
              style={{ display: "flex", alignItems: "center", gap: 8 }}
            >
              <input
                id="is_admin"
                type="checkbox"
                checked={!!editing.is_admin}
                onChange={(e) =>
                  setEditing({ ...editing, is_admin: e.target.checked })
                }
              />
              <label
                htmlFor="is_admin"
                className="form-label"
                style={{ margin: 0 }}
              >
                Admin
              </label>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button
                className="btn btn-secondary"
                onClick={() => setEditing(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  const { id, ...body } = editing!;
                  patchUserMut.mutate(
                    {
                      id,
                      body: {
                        name: body.name ?? undefined,
                        email: body.email ?? undefined,
                        phone: body.phone ?? undefined,
                        status: body.status ?? undefined,
                        is_admin: body.is_admin ?? undefined,
                      },
                    },
                    {
                      onSuccess: () => setEditing(null),
                      onError: (err: any) => {
                        alert(
                          typeof err?.message === "string"
                            ? err.message
                            : "Failed to update user"
                        );
                      },
                    }
                  );
                }}
              >
                {patchUserMut.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function DepositBox({
  onSubmit,
  busy,
}: //   errorText,
{
  onSubmit: (amountDollars: number) => void;
  busy: boolean;
  //   errorText: string | null;
}) {
  const [amount, setAmount] = useState<string>("");
  const parsed = Number(amount);
  const ok = Number.isFinite(parsed);

  return (
    <div className="detail-container" style={{ marginTop: 12 }}>
      <div className="form-group">
        <label className="form-label">Deposit amount ($)</label>
        <input
          className="form-input"
          type="number"
          // min={0}
          step="0.50"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="e.g. 20"
        />
      </div>
      <button
        className="btn btn-secondary"
        disabled={!ok || busy}
        onClick={() => {
          const dollars = Number(amount);
          if (!Number.isFinite(dollars)) return;
          const cents = Math.round(dollars * 100);
          onSubmit(cents);
          // Clear input after submit
          setAmount("");
        }}
      >
        {busy ? "Depositing…" : "Deposit"}
      </button>
      {/* {errorText && (
        <div className="error" style={{ marginTop: 8 }}>
          {errorText}
        </div>
      )} */}
    </div>
  );
}

const PreregEditor: React.FC<{
  value: PreregItem[];
  onChange: (v: PreregItem[]) => void;
  // usersIndex?: Record<string, { id: string; name: string; email: string }>; // optional, to display names
}> = ({ value, onChange }) => {
  // const [draft, setDraft] = React.useState<PreregItem>({
  //   user_id: "",
  //   name: "",
  //   seats: 1,
  //   // guest_names: [],
  // });

  const add = (draft: PreregItem) => {
    if (!draft.user_id) return;
    // if (!assertSeatsMatchGuests(draft)) {
    //   alert("Seats must equal 1 (host) + number of guests.");
    //   return;
    // }
    onChange([...value, draft]);
    // setDraft({ user_id: "", name: "", seats: 1 });
  };

  const remove = (idx: number) => {
    const next = value.slice();
    next.splice(idx, 1);
    onChange(next);
  };

  // --- Picker state (reuses existing adminListUsers API) ---
  const [pickerOpen, setPickerOpen] = React.useState(false);
  const [pickerQuery, setPickerQuery] = React.useState("");
  const debouncedPickerQuery = useDebounce(pickerQuery, 450); // Debounce picker search by 450ms for mobile typing
  const [limit, setLimit] = React.useState(20);
  const [offset, setOffset] = React.useState(0);

  const usersQ = useQuery({
    queryKey: ["admin-users-picker", debouncedPickerQuery, limit, offset],
    queryFn: async () => adminListUsers(debouncedPickerQuery, limit, offset),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const total = usersQ.data?.total ?? 0;
  const items = usersQ.data?.items ?? [];
  const canPrev = offset > 0;
  const canNext = offset + limit < total;
  return (
    <div
      className="card"
      style={{ padding: 12, marginTop: 12, position: "relative" }}
    >
      <div className="section-header">
        <div className="section-title">Preregistrations</div>
        {/* <span className="section-count">{value.length}</span> */}
      </div>

      {/* Draft row */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          alignItems: "center",
        }}
      >
        {/* <input
          className="form-input"
          placeholder="Name"
          value={draft.name}
          onChange={(e) =>
            setDraft({ ...draft, user_id: e.target.value.trim() })
          }
        /> */}

        {/* <select
          className="form-input"
          value={draft.seats}
          onChange={(e) =>
            setDraft({ ...draft, seats: Number(e.target.value) as 1 | 2 | 3 })
          }
        >
          <option value={1}>1 seat</option>
          <option value={2}>2 seats</option>
          <option value={3}>3 seats</option>
        </select> */}

        {/* <input
          className="form-input"
          placeholder="Guest names (comma separated, 0..2)"
          value={(draft.guest_names || []).join(", ")}
          onChange={(e) => {
            const parts = e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean);
            setDraft({
              ...draft,
              guest_names: parts.slice(0, 2),
              seats: parts.length + 1,
            });
          }}
        /> */}

        {/* Picker trigger */}
        <div style={{ position: "relative", width: "100%" }}>
          <button
            // type="button"
            className="btn btn-secondary"
            onClick={() => setPickerOpen((v) => !v)}
          >
            Pick users
          </button>

          {pickerOpen && (
            <div className="popover">
              <div className="popover-panel">
                <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                  <input
                    autoFocus
                    className="form-input"
                    placeholder="Search name or email…"
                    value={pickerQuery}
                    onChange={(e) => {
                      setPickerQuery(e.target.value);
                      setOffset(0); // reset to first page when search changes
                    }}
                  />
                  <select
                    className="form-input"
                    style={{ maxWidth: 120 }}
                    value={limit}
                    onChange={(e) => {
                      setLimit(Number(e.target.value));
                      setOffset(0);
                    }}
                  >
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>

                <div style={{ maxHeight: 260, overflow: "auto" }}>
                  {usersQ.isLoading ? (
                    <div className="muted">Loading…</div>
                  ) : usersQ.isError ? (
                    <div className="danger">Failed to load users</div>
                  ) : items.length ? (
                    items.map((u: AdminUserRow) => (
                      <button
                        key={u.id}
                        className="list-row"
                        style={{ width: "100%", textAlign: "left" }}
                        onClick={() => {
                          add({
                            user_id: u.id,
                            name: u.name,
                            seats: 1,
                          });
                          setPickerOpen(false);
                        }}
                        title={u.id}
                      >
                        <div className="list-title">
                          {u.is_admin ? "[Admin] • " : ""}{" "}
                          {u.name || "(no name)"}
                        </div>
                        <div className="list-subtitle">{u.email || "—"}</div>
                      </button>
                    ))
                  ) : (
                    <div className="muted">No users</div>
                  )}
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: 8,
                    gap: 8,
                  }}
                >
                  <div className="muted">
                    {offset + 1}-{Math.min(offset + limit, total)} of {total}
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="btn btn-secondary"
                      disabled={!canPrev || usersQ.isFetching}
                      onClick={() => setOffset((o) => Math.max(0, o - limit))}
                    >
                      Prev
                    </button>
                    <button
                      className="btn btn-secondary"
                      disabled={!canNext || usersQ.isFetching}
                      onClick={() => setOffset((o) => o + limit)}
                    >
                      Next
                    </button>
                    <button
                      className="btn"
                      onClick={() => setPickerOpen(false)}
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
        {/* <button className="btn" onClick={add}>
          Add
        </button> */}
      </div>

      {/* Current prereg list */}
      {value.length > 0 && (
        <table style={{ width: "100%", marginTop: 12 }}>
          <thead>
            <tr>
              <th>User</th>
              {/* <th>Seats</th>
              <th>Guests</th> */}
              <th />
            </tr>
          </thead>
          <tbody>
            {value.map((it, idx) => (
              <tr key={idx}>
                <td title={it.user_id}>{it.name}</td>
                {/* <td>{it.seats}</td> */}
                {/* <td>{it.guest_names?.join(", ") || "-"}</td> */}
                <td>
                  <button className="btn" onClick={() => remove(idx)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
