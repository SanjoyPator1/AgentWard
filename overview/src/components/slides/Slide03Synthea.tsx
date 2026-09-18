import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, CheckRow, Callout, Tag } from "@/components/deck/parts";

export default function Slide03Synthea(_props: SlideProps) {
  return (
    <SlideLayout>
      <TwoCol
        ratio="left-heavy"
        left={
          <div className="flex h-full flex-col justify-between gap-6">
            <div className="space-y-3">
              <SlideTitle eyebrow="The Data" accent="Not Real Records">
                Why Synthetic Patients
              </SlideTitle>
              <Lede>
                The obvious alternative, MIMIC-IV, needs CITI training, a signed data-use
                agreement, and a wait measured in weeks. Synthea needs one command.
              </Lede>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Tag tone="brand">FHIR-AgentBench also uses Synthea cohorts</Tag>
              <Tag tone="neutral">200 → 2,000 → 20,000 patients</Tag>
              <Tag tone="neutral">v4.0.0 pinned, never a moving target</Tag>
            </div>
          </div>
        }
        right={
          <div className="space-y-4">
            <Panel>
              <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-brand-dark uppercase">
                What Synthea gives
              </p>
              <ul className="space-y-2.5">
                <CheckRow>Real FHIR R4/R5, US Core profiles, ~150 resource types</CheckRow>
                <CheckRow>Whole lifetimes — birth to death, decades of encounters</CheckRow>
                <CheckRow>Unlimited volume. One command produces 20,000 patients</CheckRow>
                <CheckRow>Ground truth is knowable by construction, from disease modules</CheckRow>
              </ul>
            </Panel>
            <Panel className="border-flag/25 bg-flag-soft/30">
              <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-flag-dark uppercase">
                What it doesn&apos;t — the honest list
              </p>
              <ul className="space-y-2.5">
                <CheckRow tone="bad">No waveforms, no minute-by-minute vitals</CheckRow>
                <CheckRow tone="bad">No mess — real records are messier, far more fields left blank</CheckRow>
                <CheckRow tone="bad">Diseases don&apos;t interact — modules run in isolation</CheckRow>
                <CheckRow tone="bad">The leakage trap — a capable agent can learn the generator, not the medicine</CheckRow>
              </ul>
            </Panel>
          </div>
        }
      />

      <Callout tone="flag">
        Synthea is excellent for engineering the harness and worthless as evidence of clinical
        validity. That is exactly the right trade for this project, and stating it plainly is part
        of the deliverable.
      </Callout>
    </SlideLayout>
  );
}
