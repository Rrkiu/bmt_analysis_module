// import { useState } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import {
//   adminCreateSession,
//   adminDeposit,
//   adminGetUser,
//   AdminUserDetail,
//   AdminUserRow,
//   adminListUsers,
//   adminPatchSession,
// } from "../lib/api";

// function cents(n: number) {
//   return `$${n.toFixed(2)}`;
// }

// function UserAdminPanel() {
//   const qc = useQueryClient();
//   const [q, setQ] = useState("");
//   const [selected, setSelected] = useState<AdminUserRow | null>(null);

//   const listQ = useQuery({
//     queryKey: ["admin-users", q],
//     queryFn: () => adminListUsers(q),
//   });

//   const detailQ = useQuery({
//     queryKey: ["admin-user", selected?.id],
//     queryFn: () =>
//       selected ? adminGetUser(selected.id) : Promise.resolve(null as any),
//     enabled: !!selected,
//   });

//   return (
//     <div style={{ display: "grid", gap: 12 }}>
//       <div style={{ display: "flex", gap: 8 }}>
//         <input
//           className="input-field"
//           placeholder="Search name or email"
//           value={q}
//           onChange={(e) => setQ(e.target.value)}
//         />
//         <button className="btn-primary" onClick={() => listQ.refetch()}>
//           Search
//         </button>
//       </div>

//       {listQ.isLoading ? (
//         <div>Loading users…</div>
//       ) : listQ.isError ? (
//         <div>Error loading users</div>
//       ) : (
//         <div className="session-card" style={{ padding: 12 }}>
//           <div className="section-header">
//             <div className="section-title">Users</div>
//             <span className="section-count">{listQ.data!.items.length}</span>
//           </div>
//           <div style={{ width: "100%", overflowX: "auto" }}>
//             <table style={{ width: "100%" }}>
//               <thead>
//                 <tr>
//                   <th>Name</th>
//                   <th>Email</th>
//                   <th>Posted</th>
//                   <th>Hold</th>
//                   <th>Avail</th>
//                   <th>Admin</th>
//                   <th>Joined</th>
//                 </tr>
//               </thead>
//               <tbody>
//                 {listQ.data!.items.map((u) => (
//                   <tr
//                     key={u.id}
//                     onClick={() => setSelected(u)}
//                     style={{ cursor: "pointer" }}
//                   >
//                     <td>{u.name}</td>
//                     <td>{u.email}</td>
//                     <td>{cents(u.posted_cents)}</td>
//                     <td>{cents(u.holds_cents)}</td>
//                     <td>
//                       <b>{cents(u.available_cents)}</b>
//                     </td>
//                     <td>{u.is_admin ? "✓" : ""}</td>
//                     <td>{new Date(u.created_at).toLocaleString()}</td>
//                   </tr>
//                 ))}
//               </tbody>
//             </table>
//           </div>
//         </div>
//       )}

//       {selected && (
//         <div className="session-card" style={{ padding: 12 }}>
//           <h4 className="session-title" style={{ marginBottom: 8 }}>
//             User: {selected.name}{" "}
//             <small style={{ color: "#666", fontWeight: 400 }}>
//               ({selected.email})
//             </small>
//           </h4>
//           {detailQ.isLoading ? (
//             "Loading..."
//           ) : detailQ.isError ? (
//             "Error"
//           ) : (
//             <UserDetailView detail={detailQ.data!} />
//           )}
//         </div>
//       )}
//     </div>
//   );
// }

// function UserDetailView({ detail }: { detail: AdminUserDetail }) {
//   return (
//     <div>
//       <div className="session-info" style={{ marginBottom: 8 }}>
//         <div className="info-item">
//           <div className="info-value">{cents(detail.wallet.posted_cents)}</div>
//           <div className="info-label">Deposited</div>
//         </div>
//         <div className="info-item">
//           <div className="info-value">{cents(detail.wallet.holds_cents)}</div>
//           <div className="info-label">On Hold</div>
//         </div>
//         <div className="info-item">
//           <div className="info-value">
//             {cents(detail.wallet.available_cents)}
//           </div>
//           <div className="info-label">Available</div>
//         </div>
//       </div>

//       <div className="participants-section">
//         <div className="section-header">
//           <h3 className="section-title">Ledger</h3>
//           <span className="section-count">{detail.ledger.length}</span>
//         </div>
//         <div style={{ overflowX: "auto" }}>
//           <table style={{ width: "100%" }}>
//             <thead>
//               <tr>
//                 <th>ID</th>
//                 <th>Kind</th>
//                 <th>Amount</th>
//                 <th>Session</th>
//                 <th>Reg</th>
//                 <th>Time</th>
//               </tr>
//             </thead>
//             <tbody>
//               {detail.ledger.map((l) => (
//                 <tr key={l.id}>
//                   <td>{l.id}</td>
//                   <td>{l.kind}</td>
//                   <td>{cents(l.amount_cents)}</td>
//                   <td>{l.session_id || ""}</td>
//                   <td>{l.registration_id || ""}</td>
//                   <td>{new Date(l.created_at).toLocaleString()}</td>
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         </div>
//       </div>

//       <div className="participants-section">
//         <div className="section-header">
//           <h3 className="section-title">Registrations</h3>
//           <span className="section-count">{detail.registrations.length}</span>
//         </div>
//         <div style={{ overflowX: "auto" }}>
//           <table style={{ width: "100%" }}>
//             <thead>
//               <tr>
//                 <th>Session</th>
//                 <th>Starts</th>
//                 <th>Seats</th>
//                 <th>State</th>
//                 <th>WL Pos</th>
//               </tr>
//             </thead>
//             <tbody>
//               {detail.registrations.map((r) => (
//                 <tr key={r.registration_id}>
//                   <td>{r.session_title || r.session_id}</td>
//                   <td>
//                     {new Date(r.starts_at_utc).toLocaleString()} ({r.timezone})
//                   </td>
//                   <td>{r.seats}</td>
//                   <td>{r.state}</td>
//                   <td>{r.waitlist_pos ?? ""}</td>
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         </div>
//       </div>
//     </div>
//   );
// }

// export default function Admin() {
//   const qc = useQueryClient();
//   // Create session
//   const [title, setTitle] = useState("");
//   const [starts, setStarts] = useState("");
//   const [tz, setTz] = useState("America/Vancouver");
//   const [cap, setCap] = useState(16);
//   const [fee, setFee] = useState(800);
//   const create = useMutation({
//     mutationFn: () =>
//       adminCreateSession({
//         title: title || undefined,
//         starts_at_utc: starts,
//         timezone: tz,
//         capacity: cap,
//         fee_cents: fee,
//       }),
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["sessions"] });
//     },
//   });

//   // Patch session
//   const [patchId, setPatchId] = useState("");
//   const [patchCap, setPatchCap] = useState<number | "">("");
//   const [patchStatus, setPatchStatus] = useState<
//     "" | "scheduled" | "closed" | "canceled"
//   >("");
//   const patch = useMutation({
//     mutationFn: () =>
//       adminPatchSession(patchId, {
//         capacity: patchCap === "" ? undefined : Number(patchCap),
//         status: patchStatus || (undefined as any),
//       }),
//     onSuccess: () => {
//       qc.invalidateQueries({ queryKey: ["sessions"] });
//     },
//   });

//   // Deposit
//   const [depUser, setDepUser] = useState("");
//   const [depAmt, setDepAmt] = useState<number>(0);
//   const deposit = useMutation({
//     mutationFn: () =>
//       adminDeposit(depUser, depAmt, `ui-${crypto.randomUUID()}`),
//   });

//   return (
//     <div style={{ display: "grid", gap: 16 }}>
//       <section className="session-card" style={{ padding: 16 }}>
//         <div className="section-header">
//           <h3 className="section-title">Create Session</h3>
//         </div>
//         <div
//           style={{
//             display: "grid",
//             gap: 8,
//             gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))",
//           }}
//         >
//           <input
//             className="input-field"
//             placeholder="Title (optional)"
//             value={title}
//             onChange={(e) => setTitle(e.target.value)}
//           />
//           <input
//             className="input-field"
//             placeholder="Starts (UTC ISO)"
//             value={starts}
//             onChange={(e) => setStarts(e.target.value)}
//           />
//           <input
//             className="input-field"
//             placeholder="Timezone"
//             value={tz}
//             onChange={(e) => setTz(e.target.value)}
//           />
//           <input
//             className="input-field"
//             type="number"
//             placeholder="Capacity"
//             value={cap}
//             onChange={(e) => setCap(Number(e.target.value))}
//           />
//           <input
//             className="input-field"
//             type="number"
//             placeholder="Fee (cents)"
//             value={fee}
//             onChange={(e) => setFee(Number(e.target.value))}
//           />
//         </div>
//         <div style={{ marginTop: 8 }}>
//           <button
//             className="btn-primary"
//             onClick={() => create.mutate()}
//             disabled={create.isPending}
//           >
//             {create.isPending ? "Creating…" : "Create"}
//           </button>
//         </div>
//       </section>

//       <section className="session-card" style={{ padding: 16 }}>
//         <div className="section-header">
//           <h3 className="section-title">Patch Session</h3>
//         </div>
//         <div
//           style={{
//             display: "grid",
//             gap: 8,
//             gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))",
//           }}
//         >
//           <input
//             className="input-field"
//             placeholder="Session ID"
//             value={patchId}
//             onChange={(e) => setPatchId(e.target.value)}
//           />
//           <input
//             className="input-field"
//             type="number"
//             placeholder="Capacity (blank = no change)"
//             value={patchCap as any}
//             onChange={(e) =>
//               setPatchCap(e.target.value === "" ? "" : Number(e.target.value))
//             }
//           />
//           <select
//             className="input-field"
//             value={patchStatus}
//             onChange={(e) => setPatchStatus(e.target.value as any)}
//           >
//             <option value="">Status (no change)</option>
//             <option value="scheduled">scheduled</option>
//             <option value="closed">closed</option>
//             <option value="canceled">canceled</option>
//           </select>
//         </div>
//         <div style={{ marginTop: 8 }}>
//           <button
//             className="btn-primary"
//             onClick={() => patch.mutate()}
//             disabled={patch.isPending || !patchId}
//           >
//             {patch.isPending ? "Patching…" : "Patch"}
//           </button>
//         </div>
//       </section>

//       <section className="session-card" style={{ padding: 16 }}>
//         <div className="section-header">
//           <h3 className="section-title">Deposit</h3>
//         </div>
//         <div
//           style={{
//             display: "grid",
//             gap: 8,
//             gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))",
//           }}
//         >
//           <input
//             className="input-field"
//             placeholder="User ID"
//             value={depUser}
//             onChange={(e) => setDepUser(e.target.value)}
//           />
//           <input
//             className="input-field"
//             type="number"
//             placeholder="Amount (cents)"
//             value={depAmt}
//             onChange={(e) => setDepAmt(Number(e.target.value))}
//           />
//         </div>
//         <div style={{ marginTop: 8 }}>
//           <button
//             className="btn-primary"
//             onClick={() => deposit.mutate()}
//             disabled={deposit.isPending}
//           >
//             {deposit.isPending ? "Depositing…" : "Deposit"}
//           </button>
//         </div>
//       </section>

//       <section>
//         <h3 className="section-title" style={{ marginBottom: 8 }}>
//           User management
//         </h3>
//         <UserAdminPanel />
//       </section>
//     </div>
//   );
// }
