import { cn } from "@/lib/utils";
import { Panel } from "@/components/deck/parts";

// ---------------------------------------------------------------------------
// Lap - one turn of the loop, as it appears in a saved run.
//
// The left column is what the model asked for, in the shape it asked for it.
// The right column is what the tool handed back, word for word. Calls are set
// in mono and results are not, because the results really are readable prose
// now, and putting them in a code font would hide the one thing they show.
// ---------------------------------------------------------------------------

export type Exchange = {
  call: string;
  result: string;
  tone?: "brand" | "flag" | "muted";
};

export function Lap({
  n,
  headline,
  note,
  exchanges,
  className,
}: {
  n: number;
  headline: string;
  note?: string;
  exchanges: Exchange[];
  className?: string;
}) {
  return (
    <Panel className={cn("flex flex-col gap-2.5", className)}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="rounded-md bg-ink px-2 py-0.5 font-mono text-[11px] font-semibold text-paper-soft">
          lap {n}
        </span>
        <span className="text-[14px] font-semibold text-ink">{headline}</span>
      </div>
      {note ? <p className="text-[12.5px] leading-snug text-ink-soft">{note}</p> : null}
      <div className="overflow-hidden rounded-lg border border-line">
        {exchanges.map((ex, i) => (
          <div
            key={ex.call}
            className={cn(
              "grid grid-cols-1 gap-1 px-2.5 py-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)] sm:gap-3",
              i > 0 && "border-t border-line/70"
            )}
          >
            <code
              className={cn(
                "font-mono text-[11.5px] leading-snug break-words",
                ex.tone === "flag" ? "text-flag-dark" : "text-brand-dark"
              )}
            >
              {ex.call}
            </code>
            <p
              className={cn(
                "text-[12px] leading-snug",
                ex.tone === "flag"
                  ? "font-medium text-flag-dark"
                  : ex.tone === "muted"
                    ? "text-ink-faint italic"
                    : "text-ink-soft"
              )}
            >
              {ex.result}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
}
