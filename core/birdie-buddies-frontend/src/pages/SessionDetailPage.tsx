import { useCallback, useMemo, useState, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";
import MobileShell from "../components/MobileShell/MobileShell";
import Button from "../components/UI/Button";
import SeatsSelector from "../components/Session/SeatsSelector";
import { useAuth } from "../lib/auth";
import {
  getSession,
  listRegistrationsForSession,
  enqueueRegistration,
  cancelRegistration,
  type Session,
  type RegRow,
  formatDollarsFromCents,
  UTCtohhmmTimeForamt,
  getRequestStatus,
  getMyWallet,
} from "../lib/api";
import { useRequestSSE, useSessionSSE } from "../lib/sse";
import FlashBanners from "../components/UI/FlashBanners";
import { flashSuccess, flashInfo, flashWarn } from "../lib/flash";
import AddGuestInline from "../components/Session/AddGuestInline";

export default function SessionDetailPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const { user } = useAuth();

  const sess = useQuery({
    queryKey: ["session", id],
    queryFn: () => getSession(id),
    enabled: !!id,
  });
  const regs = useQuery({
    queryKey: ["regs", id],
    queryFn: () => listRegistrationsForSession(id),
    enabled: !!id,
  });
  const wallet = useQuery({
    queryKey: ["wallet", user?.id],
    queryFn: () => getMyWallet(),
    enabled: !!user,
  });

  const refetchAll = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["session", id] }),
      qc.invalidateQueries({ queryKey: ["regs", id] }),
      qc.invalidateQueries({ queryKey: ["wallet", user?.id] }),
    ]);
  }, [id, qc, user?.id]);

  // live updates on session channel
  useSessionSSE(id, () => refetchAll());

  const [seats, setSeats] = useState(1);
  const [guest1, setGuest1] = useState("");
  const [guest2, setGuest2] = useState("");
  const guestNames = useMemo(() => {
    const arr = [];
    if (seats >= 2 && guest1.trim()) arr.push(guest1.trim());
    if (seats >= 3 && guest2.trim()) arr.push(guest2.trim());
    return arr;
  }, [seats, guest1, guest2]);

  const [requestId, setRequestId] = useState<string | undefined>();
  const [isProcessing, setIsProcessing] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);
  const [attendance, setAttendance] = useState<Record<string, boolean>>({});

  // Use ref to track if we should continue polling
  const shouldPollRef = useRef<boolean>(false);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  );

  // SSE handler - simple version that just refetches data
  useRequestSSE(requestId, async () => {
    if (!requestId) return;

    // Stop polling if it's running
    shouldPollRef.current = false;
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
    }

    // Refetch data
    await refetchAll();

    // Clear loading state after a short delay to ensure UI updates
    setTimeout(() => {
      setIsProcessing(false);
      setRequestId(undefined);
      flashSuccess("Registration confirmed!");
    }, 500);
  });

  const confirmed = (regs.data ?? []).filter((r) => r.state === "confirmed");
  const waitlist = (regs.data ?? []).filter((r) => r.state === "waitlisted");
  const canceled = useMemo(() => {
    const canceledRegs = (regs.data ?? []).filter(
      (r) => r.state === "canceled" && r.canceled_from_state === "confirmed"
    );
    return canceledRegs.slice().sort((a, b) => {
      const aTime = a.canceled_at ? new Date(a.canceled_at).getTime() : 0;
      const bTime = b.canceled_at ? new Date(b.canceled_at).getTime() : 0;
      return aTime - bTime;
    });
  }, [regs.data]);

  const [showAll, setShowAll] = useState(false);
  const confirmedTopSix = showAll ? confirmed : confirmed.slice(0, 6);

  const myRegs = (regs.data ?? []).filter(
    (r) => r.host_user_id === user?.id && r.state !== "canceled"
  );

  const hostReg =
    myRegs.find((r) => r.is_host) ??
    myRegs.find((r) => r.seats > 1) ??
    myRegs.find((r) => !r.guest_names || r.guest_names.length === 0) ??
    null;

  // Separate guest registrations (created via AddGuestInline). Includes confirmed and waitlisted guests.
  const guestRegs = useMemo(() => {
    if (!hostReg) return [];

    if (hostReg.group_key) {
      return myRegs.filter(
        (r) =>
          r.group_key === hostReg.group_key &&
          !r.is_host &&
          r.state !== "canceled" &&
          r.guest_names &&
          r.guest_names.length > 0
      );
    }

    return myRegs.filter(
      (r) =>
        r.registration_id !== hostReg.registration_id &&
        r.state !== "canceled" &&
        r.seats === 1 &&
        r.guest_names &&
        r.guest_names.length > 0
    );
  }, [hostReg, myRegs]);

  const myActiveSeatCount = myRegs.reduce((sum, r) => sum + (r.seats || 0), 0);
  const hasMyReg = myRegs.length > 0;

  // Compute detailed registration status message
  const registrationStatusMessage = useMemo(() => {
    if (myRegs.length === 0) return "";

    const confirmedRegs = myRegs.filter((r) => r.state === "confirmed");
    const waitlistedRegs = myRegs.filter((r) => r.state === "waitlisted");

    const confirmedCount = confirmedRegs.reduce(
      (sum, r) => sum + (r.seats || 0),
      0
    );
    const waitlistedCount = waitlistedRegs.reduce(
      (sum, r) => sum + (r.seats || 0),
      0
    );

    // All confirmed
    if (waitlistedCount === 0) {
      return confirmedCount === 1
        ? "You are confirmed!"
        : `You and ${confirmedCount - 1} guest${
            confirmedCount - 1 > 1 ? "s" : ""
          } are confirmed!`;
    }

    // All waitlisted
    if (confirmedCount === 0) {
      const waitlistPos = waitlistedRegs[0]?.waitlist_pos;
      return waitlistedCount === 1
        ? `⏳ You are waitlisted${
            waitlistPos ? ` (position #${waitlistPos})` : ""
          }`
        : `⏳ You and ${waitlistedCount - 1} guest${
            waitlistedCount - 1 > 1 ? "s" : ""
          } are waitlisted${waitlistPos ? ` (position #${waitlistPos})` : ""}`;
    }

    // Mixed: some confirmed, some waitlisted
    const confirmedText =
      confirmedCount === 1
        ? "You are confirmed"
        : `You and ${confirmedCount - 1} guest${
            confirmedCount - 1 > 1 ? "s" : ""
          } are confirmed`;
    const waitlistedText =
      waitlistedCount === 1
        ? "1 guest is waitlisted"
        : `${waitlistedCount} guests are waitlisted`;
    return `✅ ${confirmedText}, but ⏳ ${waitlistedText}`;
  }, [myRegs]);

  const feeDisplay = sess.data
    ? formatDollarsFromCents(sess.data.fee_cents)
    : "0.0";
  const totalDisplay = sess.data
    ? formatDollarsFromCents(sess.data.fee_cents * seats)
    : "0.0";

  const requiredCents = sess.data ? Number(sess.data.fee_cents) * seats : 0;
  const availableCents = wallet.data?.available_cents ?? 0;
  const canAfford = availableCents >= requiredCents;

  // Check if cancellation is locked (within 1 hour of session start)
  const isCancellationLocked = useMemo(() => {
    if (!sess.data) return false;
    const now = new Date();
    const sessionStart = new Date(sess.data.starts_at_utc);
    const oneHourBeforeStart = new Date(
      sessionStart.getTime() - 60 * 60 * 1000
    );
    return now >= oneHourBeforeStart;
  }, [sess.data]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      shouldPollRef.current = false;
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  // Admin-only: local attendance tracker per session (no backend changes)
  const attendanceKey = useMemo(
    () => (id ? `attendance:${id}` : undefined),
    [id]
  );

  useEffect(() => {
    if (!attendanceKey) return;
    try {
      const raw = localStorage.getItem(attendanceKey);
      if (raw) setAttendance(JSON.parse(raw));
    } catch {
      // ignore malformed local data
    }
  }, [attendanceKey]);

  const persistAttendance = useCallback(
    (next: Record<string, boolean>) => {
      if (!attendanceKey) return;
      try {
        localStorage.setItem(attendanceKey, JSON.stringify(next));
      } catch {
        // storage might be unavailable; fail silently
      }
    },
    [attendanceKey]
  );

  const toggleAttendance = useCallback(
    (registrationId: string) => {
      setAttendance((prev) => {
        const next = { ...prev, [registrationId]: !prev[registrationId] };
        persistAttendance(next);
        return next;
      });
    },
    [persistAttendance]
  );

  const handleRegistration = async () => {
    if (wallet.isSuccess && !canAfford) {
      flashWarn(
        `Insufficient deposit for ${seats} seat${
          seats > 1 ? "s" : ""
        }. Required: ${totalDisplay}. Please contact an admin to top up.`
      );
      return;
    }

    setIsProcessing(true);
    shouldPollRef.current = true;

    try {
      const res = await enqueueRegistration(s.id, seats, guestNames);
      setRequestId(res.request_id);
      flashInfo("Registration submitted!");

      // Start polling as backup (in case SSE doesn't work)
      let attempts = 0;
      const maxAttempts = 15;

      const pollStatus = async () => {
        // Check if we should continue polling
        if (!shouldPollRef.current || attempts >= maxAttempts) {
          if (attempts >= maxAttempts) {
            setIsProcessing(false);
            setRequestId(undefined);
            flashWarn(
              "Registration is taking longer than expected. Please refresh the page."
            );
          }
          return;
        }

        attempts++;

        try {
          // Try to get request status
          await getRequestStatus(res.request_id);

          // If successful, refetch data
          await refetchAll();

          // Check if registration now exists
          await new Promise((resolve) => setTimeout(resolve, 500)); // Small delay for data propagation
          const updatedRegs = await qc.fetchQuery({
            queryKey: ["regs", id],
            queryFn: () => listRegistrationsForSession(id),
          });

          const hasNewReg = updatedRegs?.some(
            (r) => r.host_user_id === user?.id && r.state !== "canceled"
          );

          if (hasNewReg) {
            shouldPollRef.current = false;
            setIsProcessing(false);
            setRequestId(undefined);
            flashSuccess("Registration confirmed!");
            return;
          }
        } catch (error) {
          // Request not ready yet, continue polling
        }

        // Schedule next poll if we should continue
        if (shouldPollRef.current) {
          pollTimeoutRef.current = setTimeout(pollStatus, 1500);
        }
      };

      // Start polling after 2 seconds (give SSE a chance first)
      pollTimeoutRef.current = setTimeout(pollStatus, 2000);
    } catch (error) {
      setIsProcessing(false);
      setRequestId(undefined);
      shouldPollRef.current = false;
      flashWarn("Failed to submit registration. Please try again.");
    }
  };

  if (!sess.data)
    return (
      <MobileShell>
        <div className="skeleton" />
      </MobileShell>
    );
  const s: Session = sess.data;
  const hasStarted = new Date() >= new Date(s.starts_at_utc);
  const isAdmin = !!user?.is_admin;

  return (
    <MobileShell>
      <div className="detail-container">
        <div className="registration-header">
          <label className="session-header">
            {s.title || "Badminton Session"}
          </label>
          <div className="detail-meta">
            <div>{UTCtohhmmTimeForamt(new Date(s.starts_at_utc))}</div>
            <div>
              {s.confirmed_seats}/{s.capacity} filled • {feeDisplay} per player
            </div>
            <div>Status: {s.status}</div>
          </div>
        </div>

        <div className="registration-card">
          {!hasMyReg ? (
            <>
              <label className="registration-title">Register</label>
              <FlashBanners />
              <div className="">
                <SeatsSelector value={seats} onChange={setSeats} />
              </div>

              {seats >= 2 && (
                <div className="form-group">
                  <label className="form-label-dark">Guest 1 Name</label>
                  <input
                    className="form-input-dark"
                    value={guest1}
                    placeholder="guest name"
                    onChange={(e) => setGuest1(e.target.value)}
                  />
                </div>
              )}

              {seats >= 3 && (
                <div className="form-group">
                  <label className="form-label-dark">Guest 2 Name</label>
                  <input
                    className="form-input-dark"
                    value={guest2}
                    placeholder="guest name"
                    onChange={(e) => setGuest2(e.target.value)}
                  />
                </div>
              )}

              <div className="cost-display">
                <div>
                  <div className="cost-label">Total</div>
                  <div className="cost-value">{totalDisplay}</div>
                </div>
              </div>

              <Button
                disabled={
                  !user || isProcessing || seats !== 1 + guestNames.length
                }
                onClick={handleRegistration}
              >
                {isProcessing ? "Processing..." : "Register Now"}
              </Button>
            </>
          ) : (
            <>
              <FlashBanners />
              <div
                className={
                  myRegs.some((r) => r.state === "waitlisted")
                    ? "warning-banner"
                    : "info-banner"
                }
                style={{ marginBottom: 8 }}
              >
                {registrationStatusMessage}
              </div>

              {isCancellationLocked && (
                <div className="warning-banner" style={{ marginTop: 8 }}>
                  🔒 Cancellation locked: Session starts within 1 hour
                </div>
              )}

              {hostReg && (
                <button
                  className="btn btn-danger"
                  style={{ marginTop: 8 }}
                  disabled={isCanceling || isCancellationLocked}
                  onClick={async () => {
                    if (isCancellationLocked) {
                      flashWarn(
                        "Cancellation is locked within 1 hour of session start"
                      );
                      return;
                    }
                    const warningMessage =
                      guestRegs.length > 0
                        ? `Are you sure you want to cancel your registration? This will also cancel ALL ${guestRegs.length} guest registration(s). This action cannot be undone.`
                        : "Are you sure you want to cancel your registration? This action cannot be undone.";
                    const confirmed = window.confirm(warningMessage);
                    if (confirmed) {
                      setIsCanceling(true);
                      try {
                        await cancelRegistration(hostReg.registration_id);

                        // Wait for backend to process
                        await new Promise((resolve) =>
                          setTimeout(resolve, 500)
                        );

                        // Refetch and wait for the data to update
                        await Promise.all([
                          qc.refetchQueries({ queryKey: ["session", id] }),
                          qc.refetchQueries({ queryKey: ["regs", id] }),
                          qc.refetchQueries({ queryKey: ["wallet", user?.id] }),
                        ]);

                        // Verify the cancellation was successful
                        const updatedRegs = await qc.fetchQuery({
                          queryKey: ["regs", id],
                          queryFn: () => listRegistrationsForSession(id),
                        });

                        const stillRegistered = updatedRegs?.some(
                          (r) =>
                            r.registration_id === hostReg.registration_id &&
                            r.state !== "canceled"
                        );

                        if (!stillRegistered) {
                          flashSuccess("Registration canceled successfully");
                        } else {
                          flashWarn(
                            "Cancellation is being processed. Please wait..."
                          );
                          // Try to refetch again after a delay
                          setTimeout(() => refetchAll(), 1000);
                        }
                      } catch (error) {
                        console.error("Cancellation error:", error);
                        flashWarn(
                          "Failed to cancel registration. Please try again."
                        );
                      } finally {
                        setIsCanceling(false);
                      }
                    }
                  }}
                >
                  {isCanceling ? "Canceling..." : "Cancel My Registration"}
                </button>
              )}

              {myActiveSeatCount < 3 && hostReg && (
                <AddGuestInline
                  hostRegistrationId={hostReg.registration_id}
                  currentSeats={myActiveSeatCount}
                  maxSeats={3}
                  onAdded={refetchAll}
                />
              )}

              {myActiveSeatCount >= 3 && (
                <div className="warning-banner" style={{ marginTop: 8 }}>
                  You've reached the maximum 2 guests.
                </div>
              )}

              {/* Individual Guest Registrations List */}
              {guestRegs.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div
                    style={{
                      fontWeight: 600,
                      marginBottom: 8,
                      fontSize: "14px",
                      color: "var(--dark)",
                    }}
                  >
                    Your Guests:
                  </div>
                  {guestRegs.map((guestReg) => (
                    <div
                      key={guestReg.registration_id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "10px 12px",
                        background: "white",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-sm)",
                        marginBottom: "8px",
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: "14px",
                            color: "var(--dark)",
                          }}
                        >
                          {guestReg.guest_names?.[0] || "Guest"}
                        </div>
                        <div
                          style={{
                            fontSize: "12px",
                            color: "var(--medium)",
                            marginTop: "2px",
                          }}
                        >
                          {guestReg.state === "confirmed" ? (
                            <span>✅ Confirmed</span>
                          ) : (
                            <span>
                              ⏳ Waitlisted
                              {guestReg.waitlist_pos
                                ? ` (position #${guestReg.waitlist_pos})`
                                : ""}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        className="action-btn danger"
                        disabled={isCanceling || isCancellationLocked}
                        onClick={async () => {
                          if (isCancellationLocked) {
                            flashWarn(
                              "Cancellation is locked within 1 hour of session start"
                            );
                            return;
                          }
                          const confirmed = window.confirm(
                            `Are you sure you want to cancel ${
                              guestReg.guest_names?.[0] || "this guest"
                            }'s registration?`
                          );
                          if (confirmed) {
                            setIsCanceling(true);
                            try {
                              await cancelRegistration(
                                guestReg.registration_id
                              );

                              // Wait for backend to process
                              await new Promise((resolve) =>
                                setTimeout(resolve, 500)
                              );

                              // Refetch data
                              await Promise.all([
                                qc.refetchQueries({
                                  queryKey: ["session", id],
                                }),
                                qc.refetchQueries({ queryKey: ["regs", id] }),
                                qc.refetchQueries({
                                  queryKey: ["wallet", user?.id],
                                }),
                              ]);

                              flashSuccess(
                                `${
                                  guestReg.guest_names?.[0] || "Guest"
                                }'s registration canceled successfully`
                              );
                            } catch (error) {
                              console.error("Cancellation error:", error);
                              flashWarn(
                                "Failed to cancel registration. Please try again."
                              );
                            } finally {
                              setIsCanceling(false);
                            }
                          }
                        }}
                      >
                        {isCanceling ? "..." : "Cancel"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          <div className="cancellation-note">
            <strong>⚠️ Cancellation Policy:</strong> Full refund before
            midnight. 50% penalty for same-day cancellation. Cancellations are
            locked 1 hour before session start.
          </div>
        </div>

        {/* Confirmed */}
        <div className="participants-section">
          <div className="section-header">
            <h2 className="section-title">Confirmed</h2>
            <span className="participant-count">{s.confirmed_seats}</span>
          </div>
          {isAdmin && (
            <div
              style={{
                fontSize: "12px",
                color: "var(--medium)",
                marginBottom: 8,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              Admin-only attendance tracker (stored locally on this device)
              {hasStarted ? "" : " • available once the session starts"}
              <button
                className="btn btn-secondary"
                style={{
                  padding: "4px 8px",
                  fontSize: "11px",
                  marginLeft: "auto",
                }}
                onClick={() => {
                  if (!attendanceKey) return;
                  setAttendance({});
                  try {
                    localStorage.removeItem(attendanceKey);
                  } catch {
                    // ignore
                  }
                }}
              >
                Reset attendance
              </button>
            </div>
          )}
          <div>
            {confirmedTopSix.map((r: RegRow) => (
              <div className="participant-card" key={r.registration_id}>
                <div className="participant-info" style={{ gap: 10 }}>
                  <div className="participant-avatar">
                    {r.host_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="participant-details">
                    <div className="participant-name">
                      {r.guest_names?.length ? `${r.host_name}` : r.host_name}
                    </div>
                    <div
                      className={
                        r.guest_names?.length
                          ? "participant-meta"
                          : "participant-name"
                      }
                    >
                      {r.guest_names?.length
                        ? `(Guest) ${r.guest_names.join(", ")}`
                        : ""}
                      {r.host_user_id === user?.id ? (
                        <span className="guest-badge"> You</span>
                      ) : null}
                    </div>
                  </div>
                  {isAdmin && hasStarted && (
                    <label
                      style={{
                        marginLeft: "auto",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        fontSize: "12px",
                        color: "var(--dark)",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={!!attendance[r.registration_id]}
                        onChange={() => toggleAttendance(r.registration_id)}
                      />
                      Attended
                    </label>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {confirmed.length > 6 && (
          <button
            className="btn btn-primary"
            onClick={() => setShowAll((s) => !s)}
          >
            {showAll ? "Show less" : `Show all ${confirmed.length}`}
          </button>
        )}

        {/* Waitlist */}
        <div className="participants-section">
          <div className="section-header">
            <h2 className="section-title">Waitlist</h2>
            <span className="participant-count">{waitlist.length}</span>
          </div>
          <div>
            {waitlist.map((r: RegRow) => (
              <div className="waitlist-item" key={r.registration_id}>
                <div className="waitlist-position">{r.waitlist_pos ?? "-"}</div>
                <div className="waitlist-info">
                  <div className="waitlist-details">
                    <div className="waitlist-name">{r.host_name}</div>
                    <div className="waitlist-meta">
                      {r.seats} seat(s)
                      {r.guest_names?.length
                        ? ` • ${r.guest_names.join(", ")}`
                        : ""}
                    </div>
                  </div>
                </div>
                {/* {r.host_user_id === user?.id && (
                  <button
                    className="action-btn danger"
                    disabled={isCanceling || isCancellationLocked}
                    onClick={async () => {
                      if (isCancellationLocked) {
                        flashWarn("Cancellation is locked within 1 hour of session start");
                        return;
                      }
                      const confirmed = window.confirm(
                        "Are you sure you want to cancel your waitlist registration?"
                      );
                      if (confirmed) {
                        setIsCanceling(true);
                        try {
                          await cancelRegistration(r.registration_id);

                          // Wait for backend to process
                          await new Promise((resolve) =>
                            setTimeout(resolve, 500)
                          );

                          // Refetch and wait for the data to update
                          await Promise.all([
                            qc.refetchQueries({ queryKey: ["session", id] }),
                            qc.refetchQueries({ queryKey: ["regs", id] }),
                            qc.refetchQueries({
                              queryKey: ["wallet", user?.id],
                            }),
                          ]);

                          // Verify the cancellation was successful
                          const updatedRegs = await qc.fetchQuery({
                            queryKey: ["regs", id],
                            queryFn: () => listRegistrationsForSession(id),
                          });

                          const stillInWaitlist = updatedRegs?.some(
                            (reg) =>
                              reg.registration_id === r.registration_id &&
                              reg.state === "waitlisted"
                          );

                          if (!stillInWaitlist) {
                            flashSuccess(
                              "Waitlist registration canceled successfully"
                            );
                          } else {
                            flashWarn(
                              "Cancellation is being processed. Please wait..."
                            );
                            // Try to refetch again after a delay
                            setTimeout(() => refetchAll(), 1000);
                          }
                        } catch (error) {
                          console.error("Cancellation error:", error);
                          flashWarn(
                            "Failed to cancel registration. Please try again."
                          );
                        } finally {
                          setIsCanceling(false);
                        }
                      }
                    }}
                  >
                    {isCanceling ? "..." : "Cancel"}
                  </button>
                )} */}
              </div>
            ))}
          </div>
        </div>

        {canceled.length > 0 && (
          <div className="participants-section">
            <div className="section-header">
              <h2 className="section-title">Canceled</h2>
              <span className="participant-count">{canceled.length}</span>
            </div>
            <div>
              {canceled.map((r: RegRow) => {
                // const canceledAtLabel = r.canceled_at
                //   ? new Date(r.canceled_at).toLocaleString(undefined, {
                //       month: "short",
                //       day: "numeric",
                //     })
                //   : "time unknown";
                return (
                  <div className="waitlist-item" key={r.registration_id}>
                    <div className="waitlist-info">
                      <div className="waitlist-details">
                        <div className="waitlist-name">{r.host_name}</div>
                        <div className="waitlist-meta">
                          {r.seats} seat(s)
                          {r.guest_names?.length
                            ? ` • ${r.guest_names.join(", ")}`
                            : ""}
                          {/* {" • "}
                          {canceledAtLabel} */}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Loading Overlay */}
      {isProcessing &&
        createPortal(
          <div className="loading-overlay">
            <div className="loading-spinner">
              <div className="spinner" />
              <div className="loading-text">
                Processing registration...
                <div
                  style={{ fontSize: "0.9em", marginTop: "8px", opacity: 0.8 }}
                >
                  This may take a few seconds
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </MobileShell>
  );
}
