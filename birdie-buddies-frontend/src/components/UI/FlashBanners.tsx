import React from "react";
import Banner from "./Banner";
import { FLASH_EVENT, type FlashKind } from "../../lib/flash";

type Item = {
  id: string;
  kind: FlashKind;
  message: string;
  timeoutMs?: number;
};

export default function FlashBanners() {
  const [items, setItems] = React.useState<Item[]>([]);

  React.useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{
        kind: FlashKind;
        message: string;
        timeoutMs?: number;
      }>;
      const id = crypto?.randomUUID?.() ?? String(Date.now() + Math.random());
      setItems((prev) => [
        {
          id,
          kind: ce.detail.kind,
          message: ce.detail.message,
          timeoutMs: ce.detail.timeoutMs,
        },
        ...prev,
      ]);
    };
    window.addEventListener(FLASH_EVENT, handler as any);
    return () => window.removeEventListener(FLASH_EVENT, handler as any);
  }, []);

  return (
    <div className="">
      {items.map((it) => (
        <Banner
          key={it.id}
          kind={it.kind}
          timeoutMs={it.timeoutMs}
          onClose={() => setItems((prev) => prev.filter((x) => x.id !== it.id))}
        >
          {it.message}
        </Banner>
      ))}
    </div>
  );
}
