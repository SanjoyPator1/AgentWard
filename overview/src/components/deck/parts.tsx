import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ArrowRight, Check, AlertTriangle } from "lucide-react";

// ---------------------------------------------------------------------------
// Small text atoms
// ---------------------------------------------------------------------------

export function Kicker({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 font-mono text-[11px] font-medium tracking-[0.2em] text-brand-dark uppercase",
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-flag" />
      {children}
    </div>
  );
}

export function SlideTitle({
  eyebrow,
  children,
  accent,
  className,
}: {
  eyebrow?: string;
  children: ReactNode;
  accent?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      {eyebrow ? <Kicker>{eyebrow}</Kicker> : null}
      <h1 className="font-serif text-[2rem] leading-[1.05] font-bold tracking-tight text-ink sm:text-[2.5rem] lg:text-[3rem]">
        {children}
        {accent ? (
          <>
            <br />
            <span className="relative inline-block text-brand">
              {accent}
              <svg
                aria-hidden
                viewBox="0 0 200 12"
                className="absolute -bottom-1.5 left-0 h-2.5 w-full text-flag/70"
                preserveAspectRatio="none"
              >
                <path
                  d="M2 8 C 40 2, 70 10, 100 6 C 130 2, 160 10, 198 5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
              </svg>
            </span>
          </>
        ) : null}
      </h1>
    </div>
  );
}

export function Lede({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("max-w-2xl text-sm leading-relaxed text-ink-soft sm:text-base", className)}>
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Sticky note
// ---------------------------------------------------------------------------

export function StickyNote({
  children,
  className,
  rotate = "-rotate-2",
}: {
  children: ReactNode;
  className?: string;
  rotate?: string;
}) {
  return (
    <div
      className={cn(
        "relative w-fit rounded-sm bg-note px-4 pt-5 pb-3 shadow-[0_6px_16px_-6px_oklch(0.3_0.05_235_/_0.35)]",
        rotate,
        className
      )}
    >
      <span className="washi-tape absolute -top-2.5 left-1/2 h-4 w-14 -translate-x-1/2 -rotate-1 rounded-[2px] opacity-90" />
      <p className="font-hand text-lg leading-tight text-ink/90 sm:text-xl">{children}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mock browser / terminal window frame
// ---------------------------------------------------------------------------

export function BrowserWindow({
  title,
  children,
  className,
  tone = "light",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  tone?: "light" | "dark";
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-line shadow-[0_10px_30px_-14px_oklch(0.24_0.03_235_/_0.4)]",
        tone === "dark" ? "bg-ink" : "bg-paper-soft",
        className
      )}
    >
      <div
        className={cn(
          "flex items-center gap-1.5 border-b px-3 py-2",
          tone === "dark" ? "border-white/10 bg-black/20" : "border-line bg-paper-deep/60"
        )}
      >
        <span className="h-2.5 w-2.5 rounded-full bg-flag/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-note-tape" />
        <span className="h-2.5 w-2.5 rounded-full bg-brand/50" />
        {title ? (
          <span
            className={cn(
              "ml-2 truncate font-mono text-[11px] tracking-wide",
              tone === "dark" ? "text-white/50" : "text-ink-faint"
            )}
          >
            {title}
          </span>
        ) : null}
      </div>
      <div className={cn(tone === "dark" ? "text-white" : "text-ink")}>{children}</div>
    </div>
  );
}

export function CodeBlock({
  code,
  className,
  compact,
}: {
  code: string;
  className?: string;
  compact?: boolean;
}) {
  return (
    <pre
      className={cn(
        "scrollbar-none overflow-auto whitespace-pre font-mono text-white",
        compact ? "px-3 py-2.5 text-[11px] leading-[1.55]" : "px-4 py-3 text-[12px] leading-[1.6]",
        className
      )}
    >
      {code}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Numbered steps
// ---------------------------------------------------------------------------

export function StepBadge({ n }: { n: number | string }) {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-brand bg-paper-soft font-serif text-sm font-bold text-brand-dark">
      {n}
    </span>
  );
}

export function NumberedStep({
  n,
  title,
  children,
}: {
  n: number | string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <StepBadge n={n} />
      <div className="pt-0.5">
        <p className="text-sm font-semibold text-ink">{title}</p>
        {children ? <p className="mt-0.5 text-[13px] leading-snug text-ink-soft">{children}</p> : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Checklist rows, tags, callouts
// ---------------------------------------------------------------------------

export function CheckRow({ children, tone = "good" }: { children: ReactNode; tone?: "good" | "bad" }) {
  return (
    <li className="flex items-start gap-2.5 text-[13px] leading-snug text-ink-soft sm:text-sm">
      <span
        className={cn(
          "mt-0.5 flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-[4px]",
          tone === "good" ? "bg-brand-soft text-brand-dark" : "bg-flag-soft text-flag-dark"
        )}
      >
        {tone === "good" ? <Check className="size-3" strokeWidth={3} /> : <AlertTriangle className="size-3" strokeWidth={2.5} />}
      </span>
      <span>{children}</span>
    </li>
  );
}

export function Tag({ children, tone = "brand" }: { children: ReactNode; tone?: "brand" | "flag" | "neutral" }) {
  const map = {
    brand: "border-brand/25 bg-brand-soft text-brand-dark",
    flag: "border-flag/30 bg-flag-soft text-flag-dark",
    neutral: "border-line bg-paper-deep text-ink-soft",
  } as const;
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10.5px] tracking-wide", map[tone])}>
      {children}
    </span>
  );
}

export function Callout({
  children,
  tone = "brand",
  label,
}: {
  children: ReactNode;
  tone?: "brand" | "flag";
  label?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border px-4 py-3",
        tone === "brand" ? "border-brand/25 bg-brand-soft/70" : "border-flag/30 bg-flag-soft/70"
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
          tone === "brand" ? "bg-brand text-paper-soft" : "bg-flag text-paper-soft"
        )}
      >
        !
      </span>
      <p className="text-[13px] leading-snug text-ink sm:text-sm">
        {label ? <span className="font-semibold">{label} </span> : null}
        {children}
      </p>
    </div>
  );
}

export function PullQuote({ children, tone = "flag" }: { children: ReactNode; tone?: "brand" | "flag" }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <div className={cn("mx-auto mb-2 h-px w-10", tone === "brand" ? "bg-brand/40" : "bg-flag/40")} />
      <p className="font-serif text-lg leading-snug font-semibold text-ink italic sm:text-xl">
        &ldquo;{children}&rdquo;
      </p>
      <div className={cn("mx-auto mt-2 h-px w-10", tone === "brand" ? "bg-brand/40" : "bg-flag/40")} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline / flow diagram
// ---------------------------------------------------------------------------

export function FlowStep({
  label,
  detail,
  active,
  className,
}: {
  label: string;
  detail?: string;
  active?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-[9.5rem] flex-1 flex-col gap-0.5 rounded-lg border px-3 py-2.5 text-center",
        active ? "border-brand/40 bg-brand-soft/70" : "border-line bg-paper-soft",
        className
      )}
    >
      <span className="font-mono text-[12px] font-semibold text-ink">{label}</span>
      {detail ? <span className="text-[11px] leading-snug text-ink-faint">{detail}</span> : null}
    </div>
  );
}

export function FlowArrow({ className }: { className?: string }) {
  return (
    <div className={cn("flex shrink-0 items-center justify-center px-1 text-ink-faint", className)}>
      <ArrowRight className="size-4" />
    </div>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-line", className)} />;
}

export function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col rounded-lg border border-line bg-paper-soft px-3 py-2.5">
      <span className="font-serif text-xl font-bold text-brand-dark">{value}</span>
      <span className="text-[11px] leading-tight text-ink-faint">{label}</span>
    </div>
  );
}

export function VizTooltip({
  title,
  subtitle,
  rows,
  tone = "neutral",
}: {
  title: string;
  subtitle?: string;
  rows?: { text: string; tone?: "flag" | "neutral" }[];
  tone?: "flag" | "neutral";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-paper-soft px-3 py-2 text-left shadow-[0_8px_20px_-10px_oklch(0.24_0.03_235_/_0.5)]",
        tone === "flag" ? "border-flag/40" : "border-line"
      )}
    >
      <p className="font-mono text-[11px] font-semibold text-ink">{title}</p>
      {subtitle ? <p className="text-[10.5px] text-ink-faint">{subtitle}</p> : null}
      {rows && rows.length > 0 ? (
        <ul className="mt-1 space-y-0.5 border-t border-line/70 pt-1">
          {rows.map((r, i) => (
            <li
              key={i}
              className={cn(
                "text-[10.5px] leading-snug",
                r.tone === "flag" ? "text-flag-dark" : "text-ink-soft"
              )}
            >
              {r.text}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-xl border border-line bg-paper-soft p-4 sm:p-5", className)}>
      {children}
    </div>
  );
}
