import { Search } from "lucide-react";
import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Tag } from "@/components/deck/parts";

const COHORT_PROMPTS = ["Top 5 diabetics with a care gap", "Which patients are overdue for colorectal screening?"];

export default function Slide14AgentAsk(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="Ask A Patient, Or Ask The Cohort">
        Two Ways In
      </SlideTitle>
      <Lede>
        The chat window takes either kind of question — same agent, same rules, same tools
        underneath. What changes is how much work one answer costs.
      </Lede>

      <TwoCol
        left={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
              Pick a patient
            </p>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-paper-deep/40 px-3 py-2">
              <Search className="size-3.5 shrink-0 text-ink-faint" />
              <span className="font-mono text-[13px] text-ink">aron</span>
            </div>
            <div className="mt-1.5 rounded-lg border border-brand/30 bg-brand-soft/60 px-3 py-2">
              <p className="text-[12.5px] font-medium text-ink">Aron520 Myles862 Kozey370</p>
              <p className="text-[11px] text-ink-faint">59M · Patient/16529</p>
            </div>
            <p className="mt-3 text-[13px] leading-snug text-ink-soft">then, in plain English:</p>
            <Tag tone="brand">What are the care gaps for this patient?</Tag>
          </Panel>
        }
        right={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
              Or ask about the cohort
            </p>
            <div className="flex flex-col gap-2">
              {COHORT_PROMPTS.map((prompt) => (
                <div key={prompt} className="rounded-full border border-line bg-paper-deep/40 px-3 py-1.5">
                  <span className="text-[12.5px] text-ink-soft">{prompt}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[13px] leading-snug text-ink-soft">
              no patient selected — no fast path either. There&rsquo;s no precomputed cohort
              answer, so a question like this costs one full investigation per candidate patient
              it has to rule in or out.
            </p>
          </Panel>
        }
      />

      <p className="text-center text-[12px] text-ink-faint">
        this slide is about the door you walk through — the next slide follows one real question
        all the way to its answer
      </p>
    </SlideLayout>
  );
}
