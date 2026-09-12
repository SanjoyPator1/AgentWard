"use client";

import { useMemo } from "react";
import { SlideLayout } from "@/components/deck/SlideLayout";
import { Kicker, Callout, StatTile, VizTooltip } from "@/components/deck/parts";
import { DotField, type DotNode } from "@/components/deck/DotField";
import { phyllotaxisScatter } from "@/components/deck/layouts";
import { NEUTRAL_COLOR } from "@/lib/gap-types";
import type { CohortData, CohortPatient } from "@/lib/viz-types";
import type { SlideProps } from "@/lib/slide-types";
import { useEntered } from "@/lib/use-entered";
import cohortDataRaw from "@/data/cohort.json";

const data = cohortDataRaw as CohortData;

const FLAG_COLOR = "oklch(0.58 0.14 45)";

export default function Slide01Title(_props: SlideProps) {
  // Dots fly in from a scatter (DotField's own entrance behaviour) already
  // teal-and-clay; holding every dot neutral for the first beat, then
  // revealing which ones are flagged, adds the colour change on top of the
  // position settle instead of showing both at once.
  const revealed = useEntered(700);

  const nodes: DotNode[] = useMemo(
    () =>
      data.patients.map((p) => {
        const flagged = p.gaps.length > 0;
        return {
          id: p.id,
          r: flagged ? 3.4 : 2.6,
          color: revealed && flagged ? FLAG_COLOR : NEUTRAL_COLOR,
          opacity: revealed ? (flagged ? 0.85 : 0.4) : 0.32,
          meta: p,
        };
      }),
    [revealed]
  );

  return (
    <SlideLayout className="justify-center gap-10 pt-4 sm:pt-6">
      <div className="flex flex-col items-start gap-6">
        <Kicker>Synthetic patients · Real FHIR · Code-graded evals</Kicker>

        <h1 className="font-serif text-[3rem] leading-[0.95] font-black tracking-tight text-ink sm:text-[4.5rem] lg:text-[5.5rem]">
          Agent<span className="text-brand">Ward</span>
        </h1>

        <p className="max-w-2xl text-base leading-relaxed text-ink-soft sm:text-lg">
          An AI agent harness for synthetic patients. A hospital ward staffed by agents is the
          metaphor: a ward is a set of patients competing for a limited amount of attention —
          which is what every feature here is really about.
        </p>

        <p className="max-w-2xl text-sm leading-relaxed text-ink-faint">
          Synthea-generated FHIR data, behind our own MCP tool layer, with every task graded by a
          code oracle written against the same underlying data — not by a model judging its own
          homework.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value={String(data.summary.totalPatients)} label="synthetic patients generated" />
        <StatTile value="3 + 4" label="MCP tools shipped, two tiers" />
        <StatTile value="4" label="care-gap checks, oracle done" />
        <StatTile value="0" label="lines of real patient data" />
      </div>

      <div className="flex flex-col gap-2">
        <DotField
          nodes={nodes}
          layout={phyllotaxisScatter}
          width={1000}
          height={140}
          ariaLabel={`${data.summary.totalPatients} synthetic patients; ${data.summary.flaggedPatients} already carry a care gap F1 is built to find`}
          renderTooltip={(node) => {
            const p = node.meta as CohortPatient;
            return (
              <VizTooltip
                title={p.name}
                subtitle={`age ${p.age ?? "?"} · ${p.sex}`}
                tone={p.gaps.length ? "flag" : "neutral"}
                rows={p.gaps.length ? [{ text: `${p.gaps.length} care gap${p.gaps.length > 1 ? "s" : ""} found`, tone: "flag" as const }] : undefined}
              />
            );
          }}
        />
        <p className="font-mono text-[11px] leading-snug text-ink-faint">
          each dot is a real patient — the {data.summary.flaggedPatients} lit up are what F1 is built to find
        </p>
      </div>

      <Callout tone="flag" label="Synthetic only.">
        No real patient data goes in this project, ever. Nothing produced here is clinical advice
        or validated for clinical use.
      </Callout>
    </SlideLayout>
  );
}
