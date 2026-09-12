"use client";

import { Menu, ChevronLeft, ChevronRight } from "lucide-react";
import { SLIDES } from "@/lib/slides-meta";
import { cn } from "@/lib/utils";

export function TopBar({
  current,
  onMenu,
}: {
  current: number;
  onMenu: () => void;
}) {
  const total = SLIDES.length;
  return (
    <div className="flex shrink-0 items-center justify-between gap-3 px-4 pt-4 sm:px-8 sm:pt-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenu}
          aria-label="Open slide index"
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-paper-soft text-ink-soft transition-colors hover:border-brand/40 hover:text-brand-dark"
        >
          <Menu className="size-4" />
        </button>
        <div className="flex items-center gap-2 rounded-lg border border-line bg-paper-soft px-2.5 py-1.5 font-mono text-xs font-semibold text-ink">
          {String(current + 1).padStart(2, "0")}{" "}
          <span className="text-ink-faint">/ {String(total).padStart(2, "0")}</span>
        </div>
      </div>

      <div className="hidden flex-col items-end leading-none sm:flex">
        <span className="font-serif text-sm font-bold tracking-tight text-ink">AgentWard</span>
        <span className="font-mono text-[10px] tracking-[0.2em] text-ink-faint uppercase">Overview</span>
      </div>
    </div>
  );
}

export function ProgressRail({
  current,
  step = 0,
  totalSteps = 1,
}: {
  current: number;
  step?: number;
  totalSteps?: number;
}) {
  return (
    <div className="flex shrink-0 gap-1 px-4 pt-3 sm:px-8">
      {SLIDES.map((s, i) => {
        if (i === current && totalSteps > 1) {
          return (
            <div key={s.id} className="flex flex-1 gap-0.5">
              {Array.from({ length: totalSteps }).map((_, si) => (
                <div
                  key={si}
                  className={cn(
                    "h-[3px] flex-1 rounded-full transition-colors",
                    si <= step ? "bg-brand" : "bg-line"
                  )}
                />
              ))}
            </div>
          );
        }
        return (
          <div
            key={s.id}
            className={cn(
              "h-[3px] flex-1 rounded-full transition-colors",
              i <= current ? "bg-brand" : "bg-line"
            )}
          />
        );
      })}
    </div>
  );
}

export function NavArrows({
  onPrev,
  onNext,
  disablePrev,
  disableNext,
}: {
  onPrev: () => void;
  onNext: () => void;
  disablePrev: boolean;
  disableNext: boolean;
}) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-40 flex items-end justify-between px-4 sm:bottom-7 sm:px-8">
      <button
        onClick={onPrev}
        disabled={disablePrev}
        aria-label="Previous slide"
        className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-full border border-line bg-paper-soft text-ink shadow-[0_8px_20px_-10px_oklch(0.24_0.03_235_/_0.5)] transition-all hover:border-brand/40 hover:text-brand-dark disabled:pointer-events-none disabled:opacity-0"
      >
        <ChevronLeft className="size-5" />
      </button>
      <button
        onClick={onNext}
        disabled={disableNext}
        aria-label="Next slide"
        className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-full border border-brand/30 bg-brand text-paper-soft shadow-[0_8px_20px_-10px_oklch(0.24_0.03_235_/_0.5)] transition-all hover:bg-brand-dark disabled:pointer-events-none disabled:opacity-0"
      >
        <ChevronRight className="size-5" />
      </button>
    </div>
  );
}
