import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Tag, StickyNote, Callout } from "@/components/deck/parts";
import { Lap, type Exchange } from "@/components/deck/Lap";

// Every call and every result on this slide is copied out of one saved run,
// 2026-09-21, gemini-3.5-flash-lite, 5 laps and 11 tool calls end to end.
// Results are shortened to the first line or two, never reworded.

const LAP1: Exchange[] = [
  {
    call: "get_resource_by_id(Patient, 16529)",
    result: "Aron520 Myles862 Kozey370: born 1967-08-09, male, living [Patient/16529]",
  },
  {
    call: "search Condition · patient 16529 · newest 5",
    result:
      "Active: Limited social contact. Then three Medication review due, and Social isolation. 179 conditions on file.",
    tone: "muted",
  },
  {
    call: "search MedicationRequest · newest 5",
    result:
      "Active: Metformin 500 MG, started 2026-08-19. Hydrochlorothiazide 25 MG. Insulin, Humulin 70/30.",
  },
  {
    call: "search Observation · code 4548-4 · newest 5",
    result: "Hemoglobin A1c: 2026-08-19, 3.09 % [Observation/24806], and four older ones.",
  },
];

const LAP2: Exchange[] = [
  {
    call: "search Procedure · code 722161008",
    result: "Diabetic retinal eye exam, performed 2026-04-12 [Procedure/24497]",
  },
  {
    call: "search Procedure · code 700070005",
    result: "Optical coherence tomography of retina, performed 2026-04-12 [Procedure/24498]",
  },
  {
    call: "search Observation · code 85354-9",
    result:
      "Blood pressure panel: 2026-08-19, Diastolic 92 mm[Hg], Systolic 122 mm[Hg] [Observation/24811]",
    tone: "flag",
  },
  {
    call: "search Procedure · code 73761001",
    result: "Colonoscopy, performed 2022-08-17 [Procedure/20011]. One older one in 2017.",
  },
  {
    call: "search Procedure · code 104435004",
    result: "No Procedure resources.",
    tone: "muted",
  },
];

export default function Slide17AgentTrace(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="A Real Run, Part One">
        Casting A Wide Net
      </SlideTitle>
      <Lede>
        One saved run, shortened to fit but never reworded. Five laps, eleven tool calls, and it
        spends the first two of them asking for almost everything at once.
      </Lede>
      <Tag tone="brand">
        &ldquo;Regarding patient 16529 (Aron520 Myles862 Kozey370): What are the care gaps for
        this patient?&rdquo;
      </Tag>

      <div className="relative">
        <StickyNote className="absolute top-2 right-3 z-10 hidden xl:block" rotate="-rotate-2">
          it never asked for prose. that is just how the tools answer now.
        </StickyNote>
        <div className="space-y-3">
          <Lap
            n={1}
            headline="Who is this, and what are they on?"
            note="Four calls in a single turn. Nothing here depends on anything else here, so there is no reason to wait."
            exchanges={LAP1}
          />
          <Lap
            n={2}
            headline="Now check the four rules"
            note="Five more, again all at once. Two codes for the eye exam because either one clears it, and both screening methods for the bowel check."
            exchanges={LAP2}
          />
        </div>
      </div>

      <Callout tone="brand" label="Nine calls, two laps:">
        run these one at a time and the same work takes nine round trips to the model. The saving
        is not cleverness in the loop. The model was simply told that it may ask for more than
        one thing per turn.
      </Callout>
    </SlideLayout>
  );
}
