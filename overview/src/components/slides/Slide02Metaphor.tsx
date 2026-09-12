import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import { SlideTitle, Lede, Panel, StickyNote, CheckRow, Callout } from "@/components/deck/parts";
import type { SlideProps } from "@/lib/slide-types";

export default function Slide02Metaphor(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Idea" accent="Competing For Attention">
        A Ward Is Patients
      </SlideTitle>
      <Lede>
        A ward is a set of patients competing for a limited amount of attention. Every feature in
        this project is really about that: an agent that has to decide what deserves attention
        first, and defend that decision with evidence.
      </Lede>

      <TwoCol
        ratio="left-heavy"
        left={
          <Panel>
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
              The equation the whole project is an instance of
            </p>
            <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
              <div className="rounded-lg border border-line bg-paper-deep/60 px-4 py-3 text-center">
                <p className="font-serif text-lg font-bold text-ink">Agent</p>
              </div>
              <span className="text-center font-serif text-xl text-ink-faint sm:text-2xl">=</span>
              <div className="rounded-lg border border-line bg-paper-deep/60 px-4 py-3 text-center">
                <p className="font-serif text-lg font-bold text-ink">Model</p>
                <p className="text-[11px] text-ink-faint">fixed, rented</p>
              </div>
              <span className="text-center font-serif text-xl text-ink-faint sm:text-2xl">+</span>
              <div className="rounded-lg border border-brand/30 bg-brand-soft/60 px-4 py-3 text-center">
                <p className="font-serif text-lg font-bold text-brand-dark">Harness</p>
                <p className="text-[11px] text-ink-faint">loop, tools, context, memory,<br />verification, permissions, evals</p>
              </div>
            </div>
            <p className="mt-4 text-[13px] leading-relaxed text-ink-soft">
              The model is the same rented intelligence anyone can call. Everything AgentWard
              actually builds — the tool layer, the evals, the oracle, the eval-before-agent
              discipline — is the harness half of that equation.
            </p>
          </Panel>
        }
        right={
          <div className="space-y-4">
            <StickyNote rotate="rotate-1" className="ml-auto">
              Your harness is the moat, not the model.
            </StickyNote>
            <Panel>
              <ul className="space-y-2.5">
                <CheckRow>Every task graded by a code oracle, not a model judging its own homework.</CheckRow>
                <CheckRow>Narrow, deeply supervised, single-workflow agents ship. Broad autonomous ones stall.</CheckRow>
                <CheckRow>The oracle is written before the agent — every single task, no exceptions.</CheckRow>
                <CheckRow tone="bad">Synthetic data only. Nothing here is clinical advice, ever.</CheckRow>
              </ul>
            </Panel>
          </div>
        }
      />

      <Callout label="Why narrow tasks win:">
        per-step reliability of 90% compounds to ~53% after 6 steps, ~28% after 12, and ~4% after
        30 — effectively never works. Every AgentWard feature is scoped short on purpose, and each
        one ends in a check.
      </Callout>
    </SlideLayout>
  );
}
