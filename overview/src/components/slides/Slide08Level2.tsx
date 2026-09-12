import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, StickyNote, Tag, Callout } from "@/components/deck/parts";

type Tool = {
  name: string;
  question: string;
  call: string;
  facts: string[];
};

const TOOLS: Tool[] = [
  {
    name: "get_active_medications",
    question: "What is this patient taking, and why?",
    call: 'patient_id="2685"',
    facts: [
      "5 active meds",
      "lisinopril 10mg → treats Condition/2735",
      "resolves the Medication reference agents miss most",
    ],
  },
  {
    name: "get_lab_trend",
    question: "Results for one lab code, over a window — and is that silence real?",
    call: 'code="LOINC 4548-4" (HbA1c), start_date="2026-02-28"',
    facts: [
      "total_ever: 50 — this patient has HbA1c history",
      "total_in_window: 0 — none in 6 months",
      "a real gap, not a missing page",
    ],
  },
  {
    name: "get_problem_list",
    question: "What's actually wrong, medically — not everything on file?",
    call: 'patient_id="2685"',
    facts: [
      "73 Condition entries on record",
      "21 active → 11 tagged an actual “(disorder)”",
      "filters out “received higher education”, etc.",
    ],
  },
  {
    name: "find_cohort",
    question: "Every patient with one condition, in an age range.",
    call: 'code="hypertension", min_age=60',
    facts: [
      "40 matching Condition records",
      "returned: 15 — deduplicated, age-filtered patients",
      "deliberately narrow: one code, one age range",
    ],
  },
];

export default function Slide08Level2(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="Tool Layer" accent="Task-Shaped Tools">
        fhir-mcp — Level 2
      </SlideTitle>
      <Lede>
        One call answers a question the agent actually has, doing the FHIR-specific plumbing —
        following references, filtering noise, computing dates — that would otherwise be on the
        agent to get right.
      </Lede>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {TOOLS.map((tool) => (
          <div key={tool.name} className={tool.name === "get_lab_trend" ? "relative" : undefined}>
            {tool.name === "get_lab_trend" ? (
              <StickyNote
                className="absolute -top-9 right-2 z-10 hidden sm:block"
                rotate="rotate-2"
              >
                two numbers, never one.
              </StickyNote>
            ) : null}
            <Panel className="flex h-full flex-col gap-2">
              <div className="flex items-center justify-between gap-2">
                <p className="font-mono text-[13px] font-semibold text-brand-dark">{tool.name}()</p>
                <Tag tone="neutral">real data</Tag>
              </div>
              <p className="text-[13px] leading-snug text-ink">{tool.question}</p>
              <p className="rounded-md bg-ink px-2.5 py-1.5 font-mono text-[11px] text-white/85">{tool.call}</p>
              <ul className="mt-1 space-y-1 border-l-2 border-brand/30 pl-2.5">
                {tool.facts.map((f) => (
                  <li key={f} className="text-[12px] leading-snug text-ink-soft">
                    {f}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        ))}
      </div>

      <Callout>
        Same shape, every time: the agent gets a plain sentence plus structured data, and every
        count comes in a pair — <span className="font-mono text-[12px]">total_matching</span> next
        to <span className="font-mono text-[12px]">returned</span> — so silence never gets mistaken
        for an answer.
      </Callout>
    </SlideLayout>
  );
}
