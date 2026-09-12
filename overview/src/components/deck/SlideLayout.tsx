import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function SlideLayout({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 pt-5 pb-28 sm:gap-6 sm:px-8 sm:pt-7",
        className
      )}
    >
      {children}
    </div>
  );
}

export function TwoCol({
  left,
  right,
  ratio = "even",
}: {
  left: ReactNode;
  right: ReactNode;
  ratio?: "even" | "left-heavy" | "right-heavy";
}) {
  const cols =
    ratio === "left-heavy"
      ? "lg:grid-cols-[1.4fr_1fr]"
      : ratio === "right-heavy"
        ? "lg:grid-cols-[1fr_1.4fr]"
        : "lg:grid-cols-2";
  return (
    <div className={cn("grid grid-cols-1 gap-5 lg:gap-8", cols)}>
      <div className="min-w-0 space-y-4">{left}</div>
      <div className="min-w-0 space-y-4">{right}</div>
    </div>
  );
}
