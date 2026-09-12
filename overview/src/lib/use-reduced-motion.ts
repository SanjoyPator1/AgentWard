"use client";

import { useEffect, useState } from "react";

/** Shared by DotField and any slide that animates outside it (bar fills,
 * staggered reveals) so "skip straight to the final state" is consistent
 * everywhere, not just inside the dot simulation. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    // Browser-only API — can't read this during the SSR pass, so the initial
    // client render intentionally matches the server's `false` and corrects
    // itself here on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
