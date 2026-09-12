"use client";

import { useEffect, useState } from "react";

/** True starting `delayMs` after mount — the trigger for any "animate in
 * once the slide has settled a beat" effect. Resets to false on remount,
 * which is exactly what happens when Deck.tsx swaps the active slide, so
 * revisiting a slide replays its entrance every time. */
export function useEntered(delayMs = 30): boolean {
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setEntered(true), delayMs);
    return () => clearTimeout(t);
  }, [delayMs]);
  return entered;
}
