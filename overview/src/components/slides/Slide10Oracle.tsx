import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Callout, StatTile, VizTooltip } from "@/components/deck/parts";
import { DotField, type DotNode } from "@/components/deck/DotField";
import { phyllotaxisScatter } from "@/components/deck/layouts";
import { NEUTRAL_COLOR } from "@/lib/gap-types";
import type { CohortData, CohortPatient } from "@/lib/viz-types";
import { ArrowDown } from "lucide-react";
import cohortDataRaw from "@/data/cohort.json";

const data = cohortDataRaw as CohortData;
const FLAG = "oklch(0.58 0.14 45)";

const oracleNodes: DotNode[] = data.patients.map((p) => {
  const flagged = p.gaps.length > 0;
  return {
    id: p.id,
    r: flagged ? 3.4 : 2.6,
    color: flagged ? FLAG : NEUTRAL_COLOR,
    opacity: flagged ? 0.9 : 0.3,
    meta: p,
  };
});

export default function Slide10Oracle(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="Evaluation" accent="Code Grades The Agent">
        Truth By Construction
      </SlideTitle>
      <Lede>
        For any question we want to ask an agent, the correct answer can be computed with plain
        code from the same bundles. The agent works the FHIR API like a real client; the oracle
        cheats by reading the raw data directly.
      </Lede>

      <Panel>
        <p className="text-center font-mono text-[12px] font-semibold text-ink">
          Synthea generates {data.summary.totalPatients} patients
        </p>
        <div className="flex justify-center py-1">
          <ArrowDown className="size-4 text-ink-faint" />
        </div>

        <DotField
          nodes={oracleNodes}
          layout={phyllotaxisScatter}
          width={900}
          height={190}
          ariaLabel={`The oracle's real answer: ${data.summary.flaggedPatients} of ${data.summary.totalPatients} patients flagged with at least one care gap`}
          renderTooltip={(node) => {
            const p = node.meta as CohortPatient;
            return (
              <VizTooltip
                title={p.name}
                subtitle={`age ${p.age ?? "?"} · ${p.sex}`}
                tone={p.gaps.length ? "flag" : "neutral"}
                rows={p.gaps.length ? [{ text: `${p.gaps.length} care gap${p.gaps.length > 1 ? "s" : ""}`, tone: "flag" as const }] : [{ text: "no gaps found" }]}
              />
            );
          }}
        />
        <p className="text-center font-mono text-[12px] text-ink">
          the oracle&apos;s real answer:{" "}
          <span className="font-semibold text-flag-dark">{data.summary.flaggedPatients} of {data.summary.totalPatients} flagged</span>
        </p>

        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-brand/30 bg-brand-soft/40 p-4">
            <p className="font-mono text-[11px] font-semibold tracking-wide text-brand-dark uppercase">The Agent</p>
            <p className="mt-1 text-[13px] leading-snug text-ink-soft">
              Gets FHIR API access. Must search, fetch, join, and reason — same as a real client.
            </p>
            <p className="mt-2 font-mono text-[12px] text-ink-faint">not built yet — its job is to reach this same number</p>
          </div>
          <div className="rounded-lg border border-flag/30 bg-flag-soft/40 p-4">
            <p className="font-mono text-[11px] font-semibold tracking-wide text-flag-dark uppercase">The Oracle</p>
            <p className="mt-1 text-[13px] leading-snug text-ink-soft">
              Plain Python over the raw bundles. No AI, no MCP. Loops and comparisons only.
            </p>
            <p className="mt-2 font-mono text-[12px] text-ink">
              &ldquo;{data.summary.flaggedPatients} patients match&rdquo; — done, verified above
            </p>
          </div>
        </div>

        <div className="flex justify-center py-1">
          <ArrowDown className="size-4 text-ink-faint" />
        </div>
        <p className="text-center text-[13px] font-medium text-ink">
          once an agent exists: graded automatically — which patients disagree, and why?{" "}
          <span className="text-ink-faint">→ a real bug report about the harness</span>
        </p>
      </Panel>

      <div className="grid grid-cols-3 gap-3">
        <StatTile value="0" label="human labelling needed" />
        <StatTile value="∞" label="graded tasks — the oracle is code" />
        <StatTile value="1st" label="the oracle is written, always, before the agent" />
      </div>

      <Callout tone="flag" label="The genuinely hard part — proving a negative:">
        &ldquo;no HbA1c exists&rdquo; is only true if the agent searched correctly and exhaustively. An
        agent that fails to find a resource and concludes it&apos;s absent produces a false gap — and a
        worklist full of false gaps is worse than no worklist, because staff stop reading it.
      </Callout>
    </SlideLayout>
  );
}
