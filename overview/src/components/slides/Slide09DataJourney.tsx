"use client";

import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, NumberedStep, Callout, Tag } from "@/components/deck/parts";
import { useEntered } from "@/lib/use-entered";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";

const SERIALIZATIONS = [
  { label: "nested", bytes: 996, tone: "brand" as const, detail: "baseline — the resource as FHIR gave it" },
  { label: "compact", bytes: 818, tone: "brand" as const, detail: "drops narrative text, meta, top-level extensions" },
  { label: "flattened", bytes: 1076, tone: "flag" as const, detail: "dotted paths — repeats the prefix on every leaf" },
];
const MAX_BYTES = Math.max(...SERIALIZATIONS.map((s) => s.bytes));

export default function Slide09DataJourney(_props: SlideProps) {
  const reducedMotion = usePrefersReducedMotion();
  const filled = useEntered(reducedMotion ? 0 : 200);

  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Data" accent="Same HbA1c Value, Four Shapes">
        One Fact, Four Transformations
      </SlideTitle>
      <Lede>
        Follow one real fact — Patient/2685&apos;s last HbA1c result — from the disk file Synthea wrote
        to the sentence an agent eventually reads.
      </Lede>

      <Panel>
        <div className="grid gap-5 sm:grid-cols-2">
          <NumberedStep n={1} title="Generated">
            Synthea writes it into a static FHIR bundle on disk — one <span className="font-mono text-[12px]">Observation</span> among
            462 resources. This patient has 50 HbA1c results, every one dated 2013.
          </NumberedStep>
          <NumberedStep n={2} title="Stored">
            Loaded into HAPI FHIR / Postgres. HAPI mints its own numeric id and indexes it, so
            <span className="font-mono text-[12px]"> _total=accurate</span> and{" "}
            <span className="font-mono text-[12px]">_sort=-date</span> both work over real REST calls.
          </NumberedStep>
          <NumberedStep n={3} title="Shaped">
            <span className="font-mono text-[12px]">get_lab_trend</span> runs two searches — ever vs.
            window — decides gap-or-not, and passes the result through a serialisation strategy
            before it ever reaches a model.
          </NumberedStep>
          <NumberedStep n={4} title="Consumed">
            The agent gets both <span className="font-mono text-[12px]">content</span> (a plain sentence) and{" "}
            <span className="font-mono text-[12px]">structuredContent</span> (JSON) — and later, F1&apos;s
            worklist cites this exact Observation id as evidence.
          </NumberedStep>
        </div>
      </Panel>

      <div className="flex flex-wrap items-center gap-2">
        <Tag tone="brand">the oracle reads stage 1 directly</Tag>
        <p className="text-[12.5px] text-ink-faint">
          — skipping HAPI and fhir-mcp entirely, so a bug shared by both would go uncaught by
          neither.
        </p>
      </div>

      <Panel>
        <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
          The same real Condition, three serialisation strategies
        </p>
        <div className="space-y-2.5">
          {SERIALIZATIONS.map((s, i) => (
            <div key={s.label} className="flex items-center gap-3">
              <span className="w-20 shrink-0 font-mono text-[12px] text-ink-soft">{s.label}</span>
              <div className="h-5 flex-1 overflow-hidden rounded-full bg-paper-deep">
                <div
                  className={`h-full w-full origin-left rounded-full ${s.tone === "flag" ? "bg-flag" : "bg-brand/70"}`}
                  style={{
                    transform: `scaleX(${filled ? s.bytes / MAX_BYTES : 0})`,
                    transition: reducedMotion ? undefined : `transform 800ms ease-out ${i * 220}ms`,
                  }}
                />
              </div>
              <span className="w-16 shrink-0 text-right font-mono text-[12px] font-semibold text-ink">
                {s.bytes.toLocaleString()}B
              </span>
              <span className="hidden w-56 shrink-0 text-[11px] text-ink-faint sm:inline">{s.detail}</span>
            </div>
          ))}
        </div>
      </Panel>

      <Callout tone="flag" label="Serialisation is a real cost decision, not a formality:">
        flattening made the same Condition <em>larger</em>, not smaller — repeating a dotted path
        on every leaf costs more than the nesting it replaces. Whether that trade helps or hurts
        accuracy is what Experiment 3 measures.
      </Callout>
    </SlideLayout>
  );
}
