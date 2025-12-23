// src/lib/sse.ts
import { useEffect } from "react";

// /events/sessions/{session_id} (session-level updates) :contentReference[oaicite:21]{index=21}
export function useSessionSSE(
  sessionId: string | undefined,
  onAnyEvent: (e: MessageEvent) => void
) {
  useEffect(() => {
    if (!sessionId) return;
    const url = new URL(
      `/events/sessions/${sessionId}`,
      import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
    );
    const es = new EventSource(url.toString(), { withCredentials: true });
    es.addEventListener("message", onAnyEvent);
    return () => es.close();
  }, [sessionId, onAnyEvent]);
}

// /events/requests/{request_id} (registration flow status) :contentReference[oaicite:22]{index=22}
export function useRequestSSE(
  requestId: string | undefined,
  onAnyEvent: (e: MessageEvent) => void
) {
  useEffect(() => {
    if (!requestId) return;
    const url = new URL(
      `/events/requests/${requestId}`,
      import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
    );
    const es = new EventSource(url.toString(), { withCredentials: true });
    es.addEventListener("message", onAnyEvent);
    return () => es.close();
  }, [requestId, onAnyEvent]);
}
