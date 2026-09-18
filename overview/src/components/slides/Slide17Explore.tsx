"use client";

import { useMemo, useState } from "react";
import { SlideLayout } from "@/components/deck/SlideLayout";
import { SlideTitle, Lede, Panel, VizTooltip, StatTile } from "@/components/deck/parts";
import { DotField, type DotNode } from "@/components/deck/DotField";
import { phyllotaxisScatter } from "@/components/deck/layouts";
import { GAP_TYPES, GAP_LABELS, colorForGapType, NEUTRAL_COLOR, type GapType } from "@/lib/gap-types";
import type { CohortData, CohortPatient } from "@/lib/viz-types";
import type { SlideProps } from "@/lib/slide-types";
import { cn } from "@/lib/utils";
import cohortDataRaw from "@/data/cohort.json";

const data = cohortDataRaw as CohortData;

type FilterKey = GapType | "multiGap";

const FILTERS: { key: FilterKey; label: string }[] = [
  ...GAP_TYPES.map((g) => ({ key: g, label: GAP_LABELS[g] })),
  { key: "multiGap", label: "2+ gaps" },
];

function matches(patient: CohortPatient, filters: Set<FilterKey>): boolean {
  if (filters.size === 0) return patient.gaps.length > 0;
  if (filters.has("multiGap") && patient.gaps.length >= 2) return true;
  return patient.gaps.some((g) => filters.has(g.gap_type as FilterKey));
}

export default function Slide17Explore(_props: SlideProps) {
  const [active, setActive] = useState<Set<FilterKey>>(new Set());

  const toggle = (key: FilterKey) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const nodes: DotNode[] = useMemo(() => {
    return data.patients.map((p) => {
      const hit = matches(p, active);
      const flagged = p.gaps.length > 0;
      const primaryColor = flagged ? colorForGapType(p.gaps[0].gap_type) : NEUTRAL_COLOR;
      return {
        id: p.id,
        r: hit ? 3.8 : 2.4,
        color: hit ? primaryColor : NEUTRAL_COLOR,
        opacity: active.size === 0 ? (flagged ? 0.85 : 0.25) : hit ? 0.92 : 0.06,
        meta: p,
      };
    });
  }, [active]);

  const shownCount = useMemo(() => data.patients.filter((p) => matches(p, active)).length, [active]);

  return (
    <SlideLayout>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SlideTitle eyebrow="Bonus · For Exploration" accent="Live, For Real">
          Explore The Cohort
        </SlideTitle>
      </div>
      <Lede>
        Every dot below is real. Toggle a filter, or just hover — this is the same{" "}
        {data.summary.totalPatients}-patient cohort every number in this deck traces back to.
      </Lede>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => toggle(f.key)}
            className={cn(
              "rounded-full border px-3 py-1.5 font-mono text-[11.5px] font-medium transition-colors",
              active.has(f.key)
                ? "border-flag bg-flag text-paper-soft"
                : "border-line bg-paper-soft text-ink-soft hover:border-flag/40 hover:text-flag-dark"
            )}
          >
            {f.label}
          </button>
        ))}
        {active.size > 0 ? (
          <button
            onClick={() => setActive(new Set())}
            className="rounded-full px-3 py-1.5 font-mono text-[11.5px] text-ink-faint underline-offset-2 hover:text-ink hover:underline"
          >
            clear
          </button>
        ) : null}
      </div>

      <Panel>
        <DotField
          nodes={nodes}
          layout={phyllotaxisScatter}
          width={900}
          height={360}
          ariaLabel={`${data.summary.totalPatients} patients; ${shownCount} currently match the selected filter`}
          renderTooltip={(node) => {
            const p = node.meta as CohortPatient;
            return (
              <VizTooltip
                title={p.name}
                subtitle={`age ${p.age ?? "?"} · ${p.sex}`}
                tone={p.gaps.length ? "flag" : "neutral"}
                rows={
                  p.gaps.length
                    ? p.gaps.map((g) => ({ text: g.rationale, tone: "flag" as const }))
                    : [{ text: "no care gaps found" }]
                }
              />
            );
          }}
        />
        <p className="mt-1 text-center font-mono text-[11px] text-ink-faint">
          {active.size === 0
            ? `showing all ${data.summary.totalPatients} — ${data.summary.flaggedPatients} carry at least one gap`
            : `${shownCount} of ${data.summary.totalPatients} match the selected filter`}
        </p>
      </Panel>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value={String(data.summary.totalPatients)} label="patients, all real" />
        <StatTile value={String(data.summary.flaggedPatients)} label="carry at least one gap" />
        <StatTile value={String(GAP_TYPES.length)} label="checks running today" />
        <StatTile value={String(Object.entries(data.summary.patientsByGapCount).filter(([k]) => Number(k) > 1).reduce((s, [, v]) => s + v, 0))} label="carry more than one" />
      </div>
    </SlideLayout>
  );
}
