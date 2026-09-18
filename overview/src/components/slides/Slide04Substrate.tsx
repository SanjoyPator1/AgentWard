import { SlideLayout } from "@/components/deck/SlideLayout";
import {
  SlideTitle,
  Lede,
  Panel,
  FlowStep,
  FlowArrow,
  StickyNote,
  StatTile,
  Callout,
  VizTooltip,
} from "@/components/deck/parts";
import { DotField, type DotNode, type PositionFn } from "@/components/deck/DotField";
import { rowClusterCenter, packedCluster } from "@/components/deck/layouts";
import type { CohortData, CohortPatient } from "@/lib/viz-types";
import type { SlideProps } from "@/lib/slide-types";
import cohortDataRaw from "@/data/cohort.json";

const data = cohortDataRaw as CohortData;

const STAGES = [
  { label: "synthea -p 200", detail: "one command → 217 patients" },
  { label: "HAPI FHIR", detail: "Docker + Postgres, resettable" },
  { label: "fhir-mcp", detail: "our MCP server, 2 tool tiers" },
  { label: "the agent", detail: "F1 next, F2–F5 later" },
];

const BAND_Y = 120;
const BRAND_DOT = "oklch(0.44 0.075 195)";

const nodes: DotNode[] = data.patients.map((p) => ({
  id: p.id,
  r: 2.6,
  color: BRAND_DOT,
  opacity: 0.6,
  meta: p,
}));

function stageLayout(step: number): PositionFn {
  return (node, i, nodes, width, height) => {
    const center = rowClusterCenter(step, STAGES.length, width, height, height * (BAND_Y / 220));
    return packedCluster(center.x, center.y, i, nodes.length, node.r ?? 2.6);
  };
}

function Slide04Substrate({ step }: SlideProps) {
  const layout = stageLayout(step);

  return (
    <SlideLayout>
      <div className="flex items-start justify-between gap-6">
        <SlideTitle eyebrow="Architecture" accent="Built First, Shared By Everything">
          The Substrate Pipeline
        </SlideTitle>
        <StickyNote className="hidden shrink-0 sm:block" rotate="rotate-2">
          One reset script → the same known-good state, every eval run.
        </StickyNote>
      </div>
      <Lede>
        Do not hand an agent JSON files off disk. Stand up a real FHIR server so the agent talks
        to the same API a hospital system exposes — this is the shared foundation every one of the
        five features runs on.
      </Lede>

      <Panel>
        <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
          {STAGES.map((s, i) => (
            <div key={s.label} className="flex flex-1 items-center gap-2">
              <FlowStep label={s.label} detail={s.detail} active={step === i} className="w-full" />
              {i < STAGES.length - 1 ? <FlowArrow className="hidden shrink-0 sm:flex" /> : null}
            </div>
          ))}
        </div>

        <DotField
          className="mt-3"
          nodes={nodes}
          layout={layout}
          width={900}
          height={220}
          forceStrength={0.09}
          ariaLabel={`All ${data.summary.totalPatients} patients moving through stage ${step + 1} of ${STAGES.length}: ${STAGES[step].label}`}
          renderTooltip={(node) => {
            const p = node.meta as CohortPatient;
            return <VizTooltip title={p.name} subtitle={`age ${p.age ?? "?"} · ${p.sex}`} />;
          }}
        />
        <p className="mt-1 text-center font-mono text-[11px] text-ink-faint">
          the same {data.summary.totalPatients} patients, one stage at a time — currently at{" "}
          <span className="font-semibold text-brand-dark">{STAGES[step].label}</span>
        </p>
      </Panel>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value="217" label="patients loaded & verified" />
        <StatTile value="v8.10.0" label="HAPI FHIR, Postgres-backed" />
        <StatTile value="2026-07-28" label="stateless MCP spec, dogfooded" />
        <StatTile value="L1 + L2" label="tool tiers shipped so far" />
      </div>

      <Callout>
        Every eval run starts the same way: <span className="font-mono text-[12px]">./reset.sh</span> wipes
        the Postgres volume, then <span className="font-mono text-[12px]">./load_synthea_data.sh</span> reloads
        the same known-good cohort — no matter what a previous run created, updated, or deleted.
      </Callout>
    </SlideLayout>
  );
}

Slide04Substrate.steps = STAGES.length;

export default Slide04Substrate;
