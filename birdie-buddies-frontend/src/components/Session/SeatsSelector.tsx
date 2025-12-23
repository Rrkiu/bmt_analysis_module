type Props = { value: number; onChange: (n: number) => void; max?: number };
export default function SeatsSelector({ value, onChange, max = 3 }: Props) {
  return (
    <div className="seats-selector">
      {[1, 2, 3].slice(0, max).map((n) => (
        <button
          key={n}
          type="button"
          className={`seat-option ${value === n ? "selected" : ""}`}
          onClick={() => onChange(n)}
        >
          {/* <div style={{ fontSize: 16, fontWeight: 600 }}>{n}</div> */}
          <div style={{ fontSize: 11, opacity: 0.8 }}>
            {n === 1 ? "Just me" : n === 2 ? "+1 Guest" : "+2 Guests"}
          </div>
        </button>
      ))}
    </div>
  );
}
