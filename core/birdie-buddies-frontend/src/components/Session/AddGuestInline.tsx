// src/components/Session/AddGuestInline.tsx
import React from "react";
import { addGuest } from "../../lib/api";
import { flashSuccess, flashError, flashInfo } from "../../lib/flash";

export default function AddGuestInline({
  hostRegistrationId,
  currentSeats, // seats = host (1) + guests
  maxSeats = 3, // host + up to 2 guests
  onAdded,
}: {
  hostRegistrationId: string;
  currentSeats: number;
  maxSeats?: number;
  onAdded?: () => void;
}) {
  const guestLimit = Math.max(0, maxSeats - 1); // 2
  const guestCount = Math.max(0, (currentSeats ?? 1) - 1); // seats - 1 (host)
  const remainingGuests = Math.max(0, guestLimit - guestCount); // 0..2
  const canAdd = remainingGuests > 0; // ✅ enabled if < 2 guests

  if (!canAdd) return null; // hide entirely when limit reached (or you can render disabled UI)

  const [name, setName] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const onSubmit = async () => {
    const n = name.trim();
    if (!n) return;
    setBusy(true);
    try {
      const res = await addGuest(hostRegistrationId, n);
      if (res.state === "confirmed") {
        flashSuccess(`✓ Guest added: ${n}`);
      } else {
        const pos =
          res.waitlist_pos != null ? ` (waitlist #${res.waitlist_pos})` : "";
        flashInfo(`Guest added to waitlist${pos}: ${n}`);
      }
      setName("");
      onAdded?.();
    } catch (e: any) {
      flashError(String(e?.message || "Failed to add guest"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="detail-container"
      style={{ marginTop: 12, border: "1px solid var(--primary)" }}
    >
      <div className="form-group">
        <label className="form-label">
          <b>{remainingGuests}</b> guest seats remaining
        </label>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <input
            className="form-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Guest name"
            disabled={busy}
          />
          <button
            className="btn btn-secondary"
            disabled={busy || !name.trim()}
            onClick={onSubmit}
          >
            {busy ? "Adding…" : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}
