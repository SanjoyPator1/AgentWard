"use client";

import { SLIDES } from "@/lib/slides-meta";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

export function Sidebar({
  open,
  onOpenChange,
  current,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  current: number;
  onSelect: (index: number) => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[300px] bg-paper-soft p-0 sm:max-w-[300px]">
        <SheetHeader className="border-b border-line px-5 pt-6 pb-4">
          <SheetTitle className="font-serif text-lg font-bold text-ink">AgentWard</SheetTitle>
          <SheetDescription className="font-mono text-[11px] tracking-wide text-ink-faint uppercase">
            Jump to a topic
          </SheetDescription>
        </SheetHeader>

        <nav className="scrollbar-none flex-1 overflow-y-auto px-2.5 py-3">
          {SLIDES.map((slide, i) => {
            const showSection = i === 0 || slide.section !== SLIDES[i - 1].section;
            return (
              <div key={slide.id}>
                {showSection ? (
                  <div className="mt-4 mb-1 px-2.5 font-mono text-[10px] font-semibold tracking-[0.18em] text-ink-faint uppercase first:mt-1">
                    {slide.section}
                  </div>
                ) : null}
                <button
                  onClick={() => {
                    onSelect(i);
                    onOpenChange(false);
                  }}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                    i === current
                      ? "bg-brand-soft font-semibold text-brand-dark"
                      : "text-ink-soft hover:bg-paper-deep hover:text-ink"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px]",
                      i === current ? "bg-brand text-paper-soft" : "bg-paper-deep text-ink-faint"
                    )}
                  >
                    {i + 1}
                  </span>
                  {slide.title}
                </button>
              </div>
            );
          })}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
