import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import MobileShell from "../components/MobileShell/MobileShell";
import {
  listSessions,
  adminListSessionHistory,
  type Session,
  formatDollarsFromCents,
  UTCtohhmmTimeForamt,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { Link } from "react-router-dom";

export default function SessionsPage() {
  const { user } = useAuth();
  const [showPastSessions, setShowPastSessions] = useState(false);
  const [pastSessions, setPastSessions] = useState<Session[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const limit = 15;

  const {
    data: upcomingSessions,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });

  const {
    data: pastSessionsData,
    isLoading: isLoadingPast,
    error: pastError,
  } = useQuery({
    queryKey: ["sessions", "history", offset],
    queryFn: () => adminListSessionHistory(limit, offset),
    enabled: user?.is_admin === true && showPastSessions,
    staleTime: 0, // Always consider data stale
    refetchOnMount: true, // Always refetch when component mounts
  });

  // Update past sessions when data changes
  useEffect(() => {
    if (pastSessionsData) {
      if (offset === 0) {
        setPastSessions(pastSessionsData);
      } else {
        setPastSessions((prev) => [...prev, ...pastSessionsData]);
      }
      setHasMore(pastSessionsData.length === limit);
    }
  }, [pastSessionsData, offset, limit]);

  // Reset state when toggling OFF past sessions
  useEffect(() => {
    if (!showPastSessions) {
      setPastSessions([]);
      setOffset(0);
      setHasMore(true);
    }
  }, [showPastSessions]);

  const handleToggle = () => {
    setShowPastSessions(!showPastSessions);
  };

  const handleLoadMore = () => {
    setOffset((prev) => prev + limit);
  };

  // Use query data directly when offset is 0, otherwise use accumulated state
  const displayData = showPastSessions
    ? offset === 0
      ? pastSessionsData ?? pastSessions
      : pastSessions
    : upcomingSessions;
  const displayLoading = showPastSessions ? isLoadingPast : isLoading;
  const displayError = showPastSessions ? pastError : error;

  return (
    <MobileShell>
      <div className="page-header">
        <h1 className="page-title">
          {showPastSessions ? "Past Sessions" : "Upcoming Sessions"}
        </h1>

        {user?.is_admin && (
          <label className="toggle-container">
            <span className="toggle-label">Past Sessions</span>
            <input
              type="checkbox"
              checked={showPastSessions}
              onChange={handleToggle}
              className="toggle-checkbox"
            />
            <span className="toggle-slider"></span>
          </label>
        )}
      </div>

      {displayLoading && offset === 0 && <div className="skeleton" />}
      {displayError && <div className="error">Failed to load sessions.</div>}

      <div className="sessions-grid">
        {(displayData ?? []).map((s: Session) => (
          <Link
            key={s.id}
            to={`/sessions/${s.id}`}
            className="session-card animate-in"
            style={{ textDecoration: "none" }}
          >
            <span
              className={`session-status ${
                s.status === "scheduled"
                  ? "open"
                  : s.status === "closed"
                  ? "closed"
                  : "canceled"
              }`}
            >
              {s.status === "scheduled" ? "Open" : s.status}
            </span>
            <h3 className="session-title">{s.title || "Badminton Session"}</h3>
            <div className="session-datetime">
              {UTCtohhmmTimeForamt(new Date(s.starts_at_utc))}
            </div>
            <div className="session-stats">
              <div className="stat-item">
                <div className="stat-value">
                  {s.confirmed_seats}/{s.capacity}
                </div>
                <div className="stat-label">Registered</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{s.waitlist_seats}</div>
                <div className="stat-label">Waitlist</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">
                  {formatDollarsFromCents(s.fee_cents)}
                </div>
                <div className="stat-label">Per Player</div>
              </div>
            </div>
          </Link>
        ))}
        {!displayLoading && (displayData?.length ?? 0) === 0 && (
          <div className="empty-state">
            {showPastSessions ? "No past sessions yet." : "No Sessions yet."}
          </div>
        )}
      </div>

      {showPastSessions &&
        hasMore &&
        !isLoadingPast &&
        (displayData?.length ?? 0) > 0 && (
          <button onClick={handleLoadMore} className="load-more-button">
            Load More
          </button>
        )}

      {showPastSessions && isLoadingPast && offset > 0 && (
        <div className="loading-more">Loading...</div>
      )}
    </MobileShell>
  );
}
