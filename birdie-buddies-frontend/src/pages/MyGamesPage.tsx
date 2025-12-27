import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import MobileShell from "../components/MobileShell/MobileShell";
import {
  myRegistrations,
  type MyRegistration,
  UTCtohhmmTimeForamt,
} from "../lib/api";

type GroupedSession = {
  session_id: string;
  session_title: string | null;
  starts_at_utc: string;
  confirmedCount: number;
  waitlistedCount: number;
  lowestWaitlistPos: number | null;
};

export default function MyGamesPage() {
  const [showPastSessions, setShowPastSessions] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["me/registrations", showPastSessions],
    queryFn: () => myRegistrations(showPastSessions),
    staleTime: 0, // Always consider data stale
    refetchOnMount: true, // Always refetch when component mounts
  });

  // Group registrations by session
  const groupedSessions = useMemo(() => {
    if (!data) return [];

    const sessionMap = new Map<string, GroupedSession>();

    data.forEach((r: MyRegistration) => {
      const existing = sessionMap.get(r.session_id);

      if (!existing) {
        sessionMap.set(r.session_id, {
          session_id: r.session_id,
          session_title: r.session_title ?? null,
          starts_at_utc: r.starts_at_utc,
          confirmedCount: r.state === "confirmed" ? r.seats : 0,
          waitlistedCount: r.state === "waitlisted" ? r.seats : 0,
          lowestWaitlistPos:
            r.state === "waitlisted" ? (r.waitlist_pos ?? null) : null,
        });
      } else {
        if (r.state === "confirmed") {
          existing.confirmedCount += r.seats;
        } else if (r.state === "waitlisted") {
          existing.waitlistedCount += r.seats;
          // Track the lowest waitlist position
          if (r.waitlist_pos) {
            if (!existing.lowestWaitlistPos || r.waitlist_pos < existing.lowestWaitlistPos) {
              existing.lowestWaitlistPos = r.waitlist_pos;
            }
          }
        }
      }
    });

    return Array.from(sessionMap.values());
  }, [data]);

  return (
    <MobileShell>
      <div className="page-header">
        <h1 className="page-title">
          {showPastSessions ? "Past Games" : "My Games"}
        </h1>

        <label className="toggle-container">
          <span className="toggle-label">Past Sessions</span>
          <input
            type="checkbox"
            checked={showPastSessions}
            onChange={() => setShowPastSessions(!showPastSessions)}
            className="toggle-checkbox"
          />
          <span className="toggle-slider"></span>
        </label>
      </div>

      {isLoading && <div className="skeleton" />}
      {error && <div className="error">Failed to load.</div>}

      <div className="sessions-grid">
        {groupedSessions.map((session) => {
          const hasConfirmed = session.confirmedCount > 0;
          const hasWaitlisted = session.waitlistedCount > 0;

          // Determine status badge
          let statusClass = "open";
          let statusText = "";

          if (hasConfirmed && !hasWaitlisted) {
            statusClass = "open";
            statusText = `${session.confirmedCount} confirmed`;
          } else if (!hasConfirmed && hasWaitlisted) {
            statusClass = "closed";
            statusText = `${session.waitlistedCount} waitlisted${
              session.lowestWaitlistPos ? ` (#${session.lowestWaitlistPos})` : ""
            }`;
          } else if (hasConfirmed && hasWaitlisted) {
            statusClass = "open";
            statusText = `${session.confirmedCount} confirmed, ${session.waitlistedCount} waitlisted`;
          }

          const totalSeats = session.confirmedCount + session.waitlistedCount;

          return (
            <Link
              key={session.session_id}
              to={`/sessions/${session.session_id}`}
              className="session-card animate-in"
              style={{ textDecoration: "none" }}
            >
              <span className={`session-status ${statusClass}`}>
                {statusText}
              </span>
              <h3 className="session-title">
                {session.session_title || "Badminton Session"}
              </h3>
              <div className="session-datetime">
                {UTCtohhmmTimeForamt(new Date(session.starts_at_utc))}
              </div>
              <div className="session-stats">
                <div className="stat-item">
                  <div className="stat-value">{totalSeats}</div>
                  <div className="stat-label">
                    {totalSeats === 1 ? "Seat" : "Seats"}
                  </div>
                </div>
                {hasConfirmed && (
                  <div className="stat-item">
                    <div className="stat-value">{session.confirmedCount}</div>
                    <div className="stat-label">Confirmed</div>
                  </div>
                )}
                {hasWaitlisted && (
                  <div className="stat-item">
                    <div className="stat-value">{session.waitlistedCount}</div>
                    <div className="stat-label">Waitlisted</div>
                  </div>
                )}
              </div>
            </Link>
          );
        })}
        {!isLoading && groupedSessions.length === 0 && (
          <div className="empty-state">
            {showPastSessions
              ? "No past games yet."
              : "No upcoming games. Register for a session to get started!"}
          </div>
        )}
      </div>
    </MobileShell>
  );
}
