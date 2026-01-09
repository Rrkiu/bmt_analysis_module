import { useQuery } from "@tanstack/react-query";
import MobileShell from "../components/MobileShell/MobileShell";
import {
  getMyWallet,
  getMyWalletLedger,
  type WalletLedgerRow,
  formatDollarsFromCents,
} from "../lib/api";

/** Normalize backend kind strings to the desired display set */
function displayKind(kind: string) {
  const k = (kind || "").toLowerCase();
  if (k === "deposit_in" || k === "deposit-in") return "Deposit";
  if (k === "fee_capture") return "Paid";
  if (k === "refund") return "Refund";
  if (k === "penalty") return "Penalty";
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
function isHiddenKind(kind: string) {
  return /^(fee[_-]?hold|hold[_-]?release|hold)$/i.test(kind || "");
}

export default function WalletPage() {
  const w = useQuery({ queryKey: ["wallet/me"], queryFn: getMyWallet });
  const ledger = useQuery({
    queryKey: ["wallet/me/ledger"],
    queryFn: () => getMyWalletLedger(50),
  });

  const rows = (ledger.data ?? []).filter((e) => !isHiddenKind(e.kind));

  return (
    <MobileShell>
      <h1 className="page-title">Wallet</h1>
      {/* Deposit Information */}
      <div className="info-banner" style={{ marginBottom: 16 }}>
        <strong>💰 Deposit Funds</strong>
        <div style={{ marginTop: 4, fontSize: "0.9em" }}>
          Send e-transfer to: <strong>bdbirdies@gmail.com</strong>
        </div>
      </div>
      <div className="detail-container">
        {/* Summary */}
        <div className="cost-display" style={{ marginBottom: 16 }}>
          <div>
            <div className="cost-label">Available</div>
            <div className="cost-value">
              {formatDollarsFromCents(w.data?.available_cents)}
            </div>
          </div>
          {/* <div>
            <div className="cost-label">Posted</div>
            <div className="cost-value">
              {formatDollarsFromCents(w.data?.posted_cents)}
            </div>
          </div> */}
          <div>
            <div className="cost-label">Waitlist Holds</div>
            <div className="cost-value">
              {formatDollarsFromCents(w.data?.holds_cents)}
            </div>
          </div>
        </div>

        {/* Ledger */}
        <div className="participants-section">
          <div className="section-header">
            <h2 className="section-title">History</h2>
            <span className="participant-count">{rows.length}</span>
          </div>

          {ledger.isLoading && <div className="skeleton" />}
          {ledger.error && (
            <div className="error">Failed to load wallet history.</div>
          )}

          <div>
            {rows.map((e: WalletLedgerRow) => {
              // Build label with session title if available
              let label = "";
              const sessionDate = e.starts_at_utc
                ? mmdd(e.starts_at_utc)
                : null;
              const transactionDate = mmdd(e.created_at);
              const kindLabel =
                displayKind(e.kind) != "Deposit"
                  ? displayKind(e.kind)
                  : e.amount_cents >= 0
                  ? displayKind(e.kind)
                  : "Admin withdrawal";

              if (kindLabel === "Paid") {
                label = `${kindLabel} for session - ${sessionDate}`;
              } else {
                label = `${kindLabel}`;
              }

              const sign = e.amount_cents >= 0 ? "+" : "-";
              const amt = formatDollarsFromCents(Math.abs(e.amount_cents));
              return (
                <div
                  className="waitlist-item"
                  key={e.id}
                  style={{ alignItems: "center" }}
                >
                  <div className="waitlist-info">
                    <div className="waitlist-name">{label}</div>
                    <div
                      className="waitlist-seats"
                      style={{ fontSize: "0.85em", color: "var(--medium)" }}
                    >
                      {`Processed on: ${transactionDate}`}
                    </div>
                  </div>
                  <div className="stat-value" style={{ marginLeft: "auto" }}>
                    {sign}
                    {amt}
                  </div>
                </div>
              );
            })}
            {!ledger.isLoading && rows.length === 0 && (
              <div className="empty-state">No transactions yet.</div>
            )}
          </div>
        </div>
      </div>
    </MobileShell>
  );
}
