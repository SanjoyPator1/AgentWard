"use client";

import { useEffect, useMemo } from "react";
import { SlideLayout } from "@/components/deck/SlideLayout";
import { SlideTitle, Lede, Panel, Callout, Tag, VizTooltip } from "@/components/deck/parts";
import { DotField, type DotNode, type DotAnnotation, type DotCaption, type PositionFn } from "@/components/deck/DotField";
import { phyllotaxisScatter, rowClusterCenter, averagePoint } from "@/components/deck/layouts";
import { GAP_TYPES, GAP_LABELS, colorForGapType, NEUTRAL_COLOR } from "@/lib/gap-types";
import type { CohortData, CohortPatient } from "@/lib/viz-types";
import type { SlideProps } from "@/lib/slide-types";
import { cn } from "@/lib/utils";
import cohortDataRaw from "@/data/cohort.json";

const data = cohortDataRaw as CohortData;

const VIEW_W = 900;
const VIEW_H = 420;
const CLUSTER_BAND_Y = VIEW_H * 0.44;

const CHECK_BLURBS: Record<string, string> = {
  missing_colorectal_screening:
    "Aged 45 to 75, with no screening inside its own interval. A colonoscopy counts for 10 years, an FOBT for 1.",
  uncontrolled_bp_despite_therapy:
    "Already on blood pressure medication, and the latest reading is still 140 over 90 or higher.",
  diabetic_missing_eye_exam: "Diabetic, with no retinal eye exam on file in the last 12 months.",
  diabetic_missing_hba1c: "Diabetic, with no HbA1c result in the last 6 months.",
};

function clusterCenterFor(gapType: string) {
  const idx = GAP_TYPES.indexOf(gapType as (typeof GAP_TYPES)[number]);
  if (idx === -1) return { x: VIEW_W / 2, y: CLUSTER_BAND_Y };
  return rowClusterCenter(idx, GAP_TYPES.length, VIEW_W, VIEW_H, CLUSTER_BAND_Y);
}

const scatterLayout: PositionFn = phyllotaxisScatter;

const byGapTypeLayout: PositionFn = (node, i, nodes, w, h) => {
  const p = node.meta as CohortPatient;
  if (!p.gaps.length) return scatterLayout(node, i, nodes, w, h);
  const centers = [...new Set(p.gaps.map((g) => g.gap_type))].map(clusterCenterFor);
  return averagePoint(centers);
};

function StepPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 font-mono text-[12px] font-medium transition-colors",
        active
          ? "border-brand bg-brand text-paper-soft"
          : "border-line bg-paper-soft text-ink-soft hover:border-brand/40 hover:text-brand-dark"
      )}
    >
      {children}
    </button>
  );
}

function Slide12F1({ step, onStepChange }: SlideProps) {
  useEffect(() => {
    if (step !== 0) return;
    const t = setTimeout(() => onStepChange(1), 1400);
    return () => clearTimeout(t);
    // Only re-arm the auto-advance when the slide is freshly at step 0 (i.e.
    // on mount, or after the viewer manually steps back) — not on every
    // onStepChange identity change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const nodes: DotNode[] = useMemo(() => {
    return data.patients.map((p) => {
      const flagged = p.gaps.length > 0;
      const color = step === 1 && flagged ? colorForGapType(p.gaps[0].gap_type) : NEUTRAL_COLOR;
      const opacity = step === 0 ? 0.55 : flagged ? 0.92 : 0.08;
      const r = step === 1 && flagged ? 3.8 : 3;
      return { id: p.id, r, color, opacity, meta: p };
    });
  }, [step]);

  const layout = step === 0 ? scatterLayout : byGapTypeLayout;

  const annotations: DotAnnotation[] = useMemo(
    () =>
      step === 1
        ? GAP_TYPES.map((g) => {
            const c = clusterCenterFor(g);
            return {
              id: g,
              x: c.x,
              boxY: c.y - 82,
              lineToY: c.y - 22,
              value: String(data.summary.gapTypeCounts[g] ?? 0),
              tone: "flag" as const,
            };
          })
        : [],
    [step]
  );

  const captions: DotCaption[] = useMemo(
    () =>
      step === 1
        ? GAP_TYPES.map((g) => {
            const c = clusterCenterFor(g);
            return { id: g, x: c.x, y: c.y + 62, text: GAP_LABELS[g] };
          })
        : [],
    [step]
  );

  const pct = Math.round((data.summary.flaggedPatients / data.summary.totalPatients) * 100);
  const multiGapCount = Object.entries(data.summary.patientsByGapCount)
    .filter(([count]) => Number(count) > 1)
    .reduce((sum, [, n]) => sum + n, 0);

  return (
    <SlideLayout>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SlideTitle eyebrow="The Agent" accent="Care Gap Hunter">
          F1
        </SlideTitle>
        <div className="flex gap-2">
          <Tag tone="brand">oracle: done</Tag>
          <Tag tone="brand">agent: live</Tag>
        </div>
      </div>
      <Lede>
        A care gap is easy to describe and hard to prove. Someone was due for a test or a check,
        and there is no record that they ever got it. F1 goes through the whole cohort looking
        for those people, and shows the FHIR record behind every call it makes. Proving that
        something <em>did not</em> happen is the difficult half.
      </Lede>

      <div className="flex items-center gap-2">
        <StepPill active={step === 0} onClick={() => onStepChange(0)}>
          ① The cohort
        </StepPill>
        <StepPill active={step === 1} onClick={() => onStepChange(1)}>
          ② What it found
        </StepPill>
      </div>

      <Panel>
        <DotField
          nodes={nodes}
          layout={layout}
          width={VIEW_W}
          height={VIEW_H}
          annotations={annotations}
          captions={captions}
          ariaLabel={`${data.summary.totalPatients} patients in the cohort; ${data.summary.flaggedPatients} flagged with at least one care gap across four checks: ${GAP_TYPES.map((g) => `${GAP_LABELS[g]} (${data.summary.gapTypeCounts[g]})`).join(", ")}.`}
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
                    : [{ text: "No care gaps found" }]
                }
              />
            );
          }}
        />
        <p className="mt-1 text-center font-mono text-[11px] text-ink-faint">
          {step === 0
            ? `every dot is one real patient. ${data.summary.totalPatients} of them. hover to see who`
            : `${data.summary.flaggedPatients} of ${data.summary.totalPatients} flagged (${pct}%) · ${multiGapCount} carry more than one gap`}
        </p>
      </Panel>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
        {GAP_TYPES.map((g) => (
          <div key={g} className="rounded-lg border border-line bg-paper-soft p-2.5">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colorForGapType(g) }} />
              <span className="font-mono text-[10.5px] font-semibold text-ink">{GAP_LABELS[g]}</span>
            </div>
            <p className="mt-1 text-[11px] leading-snug text-ink-soft">{CHECK_BLURBS[g]}</p>
          </div>
        ))}
      </div>

      <Callout tone="flag" label="Why the false ones matter so much:">
        a worklist full of gaps that turn out to be nothing is worse than no worklist at all.
        Staff stop opening it after the second or third wasted call, and then the real gaps sit
        there unread too.
      </Callout>
    </SlideLayout>
  );
}

Slide12F1.steps = 2;

export default Slide12F1;
