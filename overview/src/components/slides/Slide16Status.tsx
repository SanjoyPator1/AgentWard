import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, CheckRow, Callout } from "@/components/deck/parts";

export default function Slide16Status(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="Wrap-up">Where We Stand</SlideTitle>
      <Lede>
        We built the fake patient data and the tools first. The tools let an agent read that
        data. Then we built the actual agent that uses them — the one that hunts for care gaps.
      </Lede>

      <Panel>
        <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-brand-dark uppercase">Done</p>
        <ul className="space-y-2.5">
          <CheckRow>Synthetic patient data — 217 generated, all 217 loaded &amp; verified</CheckRow>
          <CheckRow>Real FHIR server, resettable to a known state — HAPI + Postgres</CheckRow>
          <CheckRow>fhir-mcp, two tool tiers — 3 Level 1 + 4 Level 2, stateless 2026-07-28 spec</CheckRow>
          <CheckRow>Oracle for care gaps — 4 checks built and tested</CheckRow>
          <CheckRow>Chat agent — conversational care-gap investigation over the MCP tools, live</CheckRow>
        </ul>
      </Panel>

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
