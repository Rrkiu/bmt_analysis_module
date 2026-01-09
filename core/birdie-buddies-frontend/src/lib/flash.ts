export type FlashKind = "success" | "error" | "info" | "warning";

type FlashDetail = { kind: FlashKind; message: string; timeoutMs?: number };

const EVENT_NAME = "app:flash";

export function flash(detail: FlashDetail) {
  window.dispatchEvent(new CustomEvent<FlashDetail>(EVENT_NAME, { detail }));
}

export const flashSuccess = (message: string, timeoutMs = 6000) =>
  flash({ kind: "success", message, timeoutMs });

export const flashError = (message: string, timeoutMs = 6000) =>
  flash({ kind: "error", message, timeoutMs });

export const flashInfo = (message: string, timeoutMs = 6000) =>
  flash({ kind: "info", message, timeoutMs });

export function flashWarn(message: string, timeoutMs = 8000) {
  window.dispatchEvent(
    new CustomEvent(FLASH_EVENT, {
      detail: { kind: "warning", message, timeoutMs },
    })
  );
}

export const FLASH_EVENT = EVENT_NAME;
