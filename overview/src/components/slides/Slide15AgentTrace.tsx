import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import {
  SlideTitle,
  Lede,
  Panel,
  BrowserWindow,
  CodeBlock,
  Callout,
  CheckRow,
  Tag,
} from "@/components/deck/parts";
import { cn } from "@/lib/utils";

const STEP0_CALLS = `get_resource_by_id(Patient/16529)
get_problem_list(16529)
search_resources(Observation, code=4548-4)   # HbA1c
search_resources(Observation, code=85354-9)  # BP panel
… +5 more, batched in the same turn`;

const STEP1_CALLS = `search_resources(Observation, code=4548-4)   # HbA1c — retry
search_resources(Observation, code=85354-9)  # BP panel — retry
search_resources(Procedure, code=73761001)   # colonoscopy — retry
… +3 more, batched in the same turn`;

function StepPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 font-mono text-[12px] font-medium transition-colors",
        active
          ? "border-brand bg-brand text-paper-soft"
          : "border-line bg-paper-soft text-ink-soft hover:border-brand/40 hover:text-brand-dark"
      )}
    >
      {children}
    </button>
  );
}

export default function Slide15AgentTrace({ step, onStepChange }: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="Watching It Think">
        A Real Investigation
      </SlideTitle>
      <Lede>
        This is an actual saved run, trimmed to fit the screen — nothing here is staged.
      </Lede>
      <Tag tone="brand">
        &ldquo;Regarding patient 16529 (Aron520 Myles862 Kozey370): What are the care gaps for
        this patient?&rdquo;
      </Tag>

      <div className="flex flex-wrap items-center gap-2">
        <StepPill active={step === 0} onClick={() => onStepChange(0)}>
          ① Step 1 · Investigate
        </StepPill>
        <StepPill active={step === 1} onClick={() => onStepChange(1)}>
          ② Step 2 · Retry
        </StepPill>
        <StepPill active={step === 2} onClick={() => onStepChange(2)}>
          ③ Step 3 · Answer
        </StepPill>
      </div>

      {step === 0 ? (
        <>
          <BrowserWindow title="tool calls · step 1" tone="dark">
            <CodeBlock code={STEP0_CALLS} />
          </BrowserWindow>
          <div className="flex flex-wrap gap-1.5">
            <Tag tone="brand">Patient lookup → 59M, married, Weymouth MA</Tag>
            <Tag tone="brand">Problem list → 20 active, incl. Diabetes mellitus type 2, Essential hypertension</Tag>
            <Tag tone="flag">Observation/Procedure searches → rejected: unknown param &quot;count&quot;</Tag>
          </div>
          <p className="text-center text-[12px] text-ink-faint">
            9 tool calls issued in one turn — 3 succeeded, 6 were rejected by the FHIR server for
            an unsupported <code>count</code> parameter.
          </p>
        </>
      ) : null}

      {step === 1 ? (
        <>
          <BrowserWindow title="tool calls · step 2" tone="dark">
            <CodeBlock code={STEP1_CALLS} />
          </BrowserWindow>
          <div className="flex flex-wrap gap-1.5">
            <Tag tone="brand">HbA1c: 3.09% on 2026-08-19</Tag>
            <Tag tone="brand">
              BP panel: 122/<strong>92</strong> mmHg on 2026-08-19
            </Tag>
            <Tag tone="brand">Colonoscopy: 2022-08-17</Tag>
            <Tag tone="brand">FOBT: none found</Tag>
          </div>
          <p className="text-center text-[12px] text-ink-faint">
            same calls, <code>count</code> dropped — this time every search succeeds. The loop
            doesn&rsquo;t distinguish &ldquo;retry&rdquo; from &ldquo;first try&rdquo; — it&rsquo;s
            just another turn.
          </p>
        </>
      ) : null}

      {step === 2 ? (
        <>
          <Panel>
            <p className="font-mono text-[11px] tracking-[0.15em] text-flag-dark uppercase">
              uncontrolled_bp_despite_therapy — gap identified
            </p>
            <p className="mt-1.5 text-[13px] leading-snug text-ink-soft">
              Patient has essential hypertension (<code>Condition/16563</code>) and is on therapy
              (Hydrochlorothiazide, <code>MedicationRequest/24843</code>). Latest BP panel
              (<code>Observation/24811</code>, 2026-08-19) shows diastolic 92 mmHg — meets the
              ≥90 threshold.
            </p>
            <ul className="mt-3 space-y-2 border-t border-line/70 pt-3">
              <CheckRow>diabetic_missing_hba1c — no gap (HbA1c 2026-08-19)</CheckRow>
              <CheckRow>diabetic_missing_eye_exam — no gap (exam 2026-04-12)</CheckRow>
              <CheckRow>missing_colorectal_screening — no gap (colonoscopy 2022-08-17)</CheckRow>
            </ul>
          </Panel>
          <Callout tone="flag" label="The core lesson:">
            three of four checks came back clean. That&rsquo;s not the agent being lazy — a
            correct &ldquo;no gap&rdquo; costs exactly as much work as a correct gap, since it had
            to positively confirm the absence, not just fail to find one.
          </Callout>
        </>
      ) : null}
    </SlideLayout>
  );
}

Slide15AgentTrace.steps = 3;
