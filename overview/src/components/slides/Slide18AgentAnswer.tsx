import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Callout, CheckRow, Tag } from "@/components/deck/parts";
import { Lap, type Exchange } from "@/components/deck/Lap";

// Same saved run as the previous slide: laps 3 to 5 of 2026-09-21.

const LAP3: Exchange[] = [
  {
    call: "search Condition · patient 16529 · code 59621000",
    result: "Active: Essential hypertension (disorder), onset 2004-10-27 [Condition/16563]",
  },
];

const LAP4: Exchange[] = [
  {
    call: "get_active_medications(16529)",
    result:
      "Hydrochlorothiazide 25 MG Oral Tablet, started 2026-08-19, for Condition/16563 [MedicationRequest/24843]",
    tone: "flag",
  },
];

export default function Slide18AgentAnswer(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="A Real Run, Part Two">
        Two Holes, Then The Answer
      </SlideTitle>
      <Lede>
        The wide net missed two things. Watching the agent notice that and go back for them is
        more useful than watching it get everything right first time.
      </Lede>

      <div className="space-y-3">
        <Lap
          n={3}
          headline="The diagnosis was never in the results"
          note="Lap one asked for the newest five conditions and got recent admin notes. This diagnosis is from 2004, nowhere near the top of a list sorted newest first, so it asks again by code."
          exchanges={LAP3}
        />
        <Lap
          n={4}
          headline="A diagnosis alone is not treatment"
          note="The rule only counts if a medicine is linked to that condition. The raw search in lap one listed the drugs but not what they were for. This tool follows the reference and says so."
          exchanges={LAP4}
        />
      </div>

      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[11px] tracking-[0.15em] text-flag-dark uppercase">
            lap 5 · no tools asked for, so this is the answer
          </p>
          <Tag tone="flag">1 gap found</Tag>
        </div>
        <p className="mt-2 text-[13px] font-semibold text-ink">uncontrolled_bp_despite_therapy</p>
        <p className="mt-1 text-[13px] leading-snug text-ink-soft">
          Aron has essential hypertension (<code>Condition/16563</code>) and takes
          hydrochlorothiazide for it (<code>MedicationRequest/24843</code>). His latest reading
          (<code>Observation/24811</code>, 2026-08-19) is 122 over 92. The diastolic number is at
          the threshold of 90, so the gap holds.
        </p>
        <ul className="mt-3 space-y-2 border-t border-line/70 pt-3">
          <CheckRow>diabetic_missing_hba1c · clear, result on 2026-08-19</CheckRow>
          <CheckRow>diabetic_missing_eye_exam · clear, exam on 2026-04-12</CheckRow>
          <CheckRow>missing_colorectal_screening · clear, colonoscopy on 2022-08-17</CheckRow>
        </ul>
        <p className="mt-3 text-[12px] leading-snug text-ink-faint">
          It also worked out that Aron is diabetic without finding a diagnosis for it, going on
          the metformin and insulin prescriptions instead. Most diabetics in this cohort never
          got the diagnosis code, so an agent that looks only for that code misses nearly all of
          them.
        </p>
      </Panel>

      <Callout tone="flag" label="Three of the four came back clear:">
        that is not the agent taking the easy way out. Saying &ldquo;no gap&rdquo; costs the same
        work as finding one, because it only counts once the agent has gone looking and come back
        empty. Absence has to be checked for. It cannot be assumed from a quiet record.
      </Callout>
    </SlideLayout>
  );
}
