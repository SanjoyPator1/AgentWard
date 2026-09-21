import { Search } from "lucide-react";
import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Tag, Callout } from "@/components/deck/parts";

const COHORT_PROMPTS = [
  "Top 5 diabetics with a care gap",
  "Which patients are overdue for colorectal screening?",
];

// Both numbers are from saved runs of the current build, so the two bars are
// measuring the same agent on the same cohort, not an estimate.
const COST = [
  { label: "One named patient", laps: 5, calls: 11, width: "31%", tone: "brand" as const },
  { label: "The whole cohort", laps: 17, calls: 16, width: "100%", tone: "flag" as const },
];

export default function Slide16AgentAsk(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="Two Ways To Ask">
        One Patient, Or All Of Them
      </SlideTitle>
      <Lede>
        The chat box takes either kind of question. Same agent, same rules, same tools. What
        changes is how much work one answer costs.
      </Lede>

      <TwoCol
        left={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
              Pick a patient first
            </p>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-paper-deep/40 px-3 py-2">
              <Search className="size-3.5 shrink-0 text-ink-faint" />
              <span className="font-mono text-[13px] text-ink">aron</span>
            </div>
            <div className="mt-1.5 rounded-lg border border-brand/30 bg-brand-soft/60 px-3 py-2">
              <p className="text-[12.5px] font-medium text-ink">Aron520 Myles862 Kozey370</p>
              <p className="text-[11px] text-ink-faint">59M · Patient/16529</p>
            </div>
            <p className="mt-3 text-[13px] leading-snug text-ink-soft">Then ask in plain English:</p>
            <Tag tone="brand">What are the care gaps for this patient?</Tag>
          </Panel>
        }
        right={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
              Or skip the patient
            </p>
            <div className="flex flex-col gap-2">
              {COHORT_PROMPTS.map((prompt) => (
                <div key={prompt} className="rounded-full border border-line bg-paper-deep/40 px-3 py-1.5">
                  <span className="text-[12.5px] text-ink-soft">{prompt}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[13px] leading-snug text-ink-soft">
              There is no shortcut waiting behind these. The agent has to rule each candidate in
              or out by reading their record, one at a time, in the same conversation.
            </p>
          </Panel>
        }
      />

      <Panel>
        <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
          what each one cost · bars show laps, to scale
        </p>
        <div className="space-y-2.5">
          {COST.map((row) => (
            <div key={row.label} className="flex items-center gap-3">
              <span className="w-36 shrink-0 text-[12.5px] text-ink-soft">{row.label}</span>
              <div className="h-6 flex-1 overflow-hidden rounded-md bg-paper-deep/50">
                <div
                  className={row.tone === "brand" ? "h-full rounded-md bg-brand/70" : "h-full rounded-md bg-flag/70"}
                  style={{ width: row.width }}
                />
              </div>
              <span className="w-40 shrink-0 text-right font-mono text-[11.5px] text-ink-faint">
                {row.laps} laps · {row.calls} tool calls
              </span>
            </div>
          ))}
        </div>
      </Panel>

      <Callout tone="flag" label="The honest version:">
        the cohort answer works, but the whole cohort lands in one growing conversation. Ask
        about enough patients and the agent is carrying every one of them in its head at once.
        That is a real limit of this design, and the next version is where it gets addressed.
      </Callout>
    </SlideLayout>
  );
}
