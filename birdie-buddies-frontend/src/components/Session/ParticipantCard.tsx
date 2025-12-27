// import React from "react";
// import { Participant } from "../../lib/api";
// export default function ParticipantCard({
//   p,
//   onEdit,
//   onCancel,
// }: {
//   p: Participant;
//   onEdit?: () => void;
//   onCancel?: () => void;
// }) {
//   return (
//     <div className="participant-card">
//       <div className="participant-info">
//         <div className="participant-avatar">
//           {p.name.slice(0, 2).toUpperCase()}
//         </div>
//         <div className="participant-details">
//           <div className="participant-name">
//             {p.name} {p.isYou && <span className="guest-badge">You</span>}
//           </div>
//           <div className="participant-meta">
//             {p.seats} {p.seats > 1 ? "seats" : "seat"}{" "}
//             {p.guests?.length ? `• With ${p.guests.length} guest(s)` : ""}
//           </div>
//         </div>
//       </div>
//       {(onEdit || onCancel) && (
//         <div className="participant-actions">
//           {onEdit && (
//             <button className="action-btn" onClick={onEdit}>
//               Edit
//             </button>
//           )}
//           {onCancel && (
//             <button className="action-btn danger" onClick={onCancel}>
//               Cancel
//             </button>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }
