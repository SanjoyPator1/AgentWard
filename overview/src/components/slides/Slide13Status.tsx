import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, CheckRow, Callout, Tag } from "@/components/deck/parts";

export default function Slide13Status(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="Wrap-up" accent="And What Comes Next">
        Where We Stand
      </SlideTitle>
      <Lede>
        We built the fake patient data and the tools first. The tools let an agent read that
        data. The next step is the actual agent that uses them — starting with the one that hunts
        for care gaps.
      </Lede>

      <TwoCol
        left={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-brand-dark uppercase">Done</p>
            <ul className="space-y-2.5">
              <CheckRow>Synthetic patient data — 217 generated, all 217 loaded &amp; verified</CheckRow>
              <CheckRow>Real FHIR server, resettable to a known state — HAPI + Postgres</CheckRow>
              <CheckRow>fhir-mcp, two tool tiers — 3 Level 1 + 4 Level 2, stateless 2026-07-28 spec</CheckRow>
              <CheckRow>Oracle for care gaps — 4 checks built and tested</CheckRow>
            </ul>
          </Panel>
        }
        right={
          <Panel className="h-full border-flag/25 bg-flag-soft/25">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-flag-dark uppercase">Next</p>
            <ul className="space-y-2.5">
              <CheckRow tone="bad">F1 agent — hunts care gaps using the MCP tools, not started</CheckRow>
              <CheckRow tone="bad">Experiments 1–3 — tool granularity, scale, serialisation</CheckRow>
            </ul>
            <p className="mt-4 mb-2 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">Later</p>
            <div className="flex flex-wrap gap-1.5">
              <Tag tone="neutral">F2 handoff brief</Tag>
              <Tag tone="neutral">F3 cohort query</Tag>
              <Tag tone="neutral">F4 prior auth</Tag>
              <Tag tone="neutral">F5 ICU triage</Tag>
            </div>
          </Panel>
        }
      />

      <Callout tone="flag" label="Non-negotiable, every slide of this deck:">
        synthetic data only, nothing produced here is clinical advice, and the oracle is always
        written before the agent.
      </Callout>

      <p className="pt-1 text-center font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
        github.com/SanjoyPator1/AgentWard
      </p>
    </SlideLayout>
  );
}
