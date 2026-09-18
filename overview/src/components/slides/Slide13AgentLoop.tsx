import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Callout, Tag, NumberedStep, FlowStep, FlowArrow } from "@/components/deck/parts";

export default function Slide13AgentLoop(_props: SlideProps) {
  return (
    <SlideLayout>
      <div className="flex items-center gap-3">
        <SlideTitle eyebrow="The Agent" accent="How The Chat Agent Works">
          One Loop, No Lookup Table
        </SlideTitle>
        <Tag tone="brand">agent: live</Tag>
      </div>
      <Lede>
        The agent has no precomputed answers. Every reply comes from it calling the same fhir-mcp
        tools shown earlier in this deck, reading what comes back, and deciding whether it needs
        to look at anything else before it can answer.
      </Lede>

      <Panel>
        <div className="flex flex-col items-stretch gap-1.5 sm:flex-row sm:items-center">
          <FlowStep label="You ask" />
          <FlowArrow className="sm:rotate-0" />
          <FlowStep label="Agent calls tools" detail="often several at once" />
          <FlowArrow />
          <FlowStep label="Reads the results" />
          <FlowArrow />
          <FlowStep label="More tools if needed" detail="retries, follow-ups" />
          <FlowArrow />
          <FlowStep label="Answers with citations" active />
        </div>
        <p className="mt-3 text-center text-[12px] leading-snug text-ink-faint">
          the middle three steps repeat as many times as it takes — the loop itself doesn&rsquo;t
          count or plan ahead, it just keeps going until the model stops asking for tools
        </p>
      </Panel>

      <Panel>
        <div className="space-y-3.5">
          <NumberedStep n={1} title="Independent lookups get batched">
            asking for HbA1c, blood pressure, and a colonoscopy history all in the same turn costs
            one round trip, not three.
          </NumberedStep>
          <NumberedStep n={2} title="A tool error doesn&apos;t stop the loop">
            if the FHIR server rejects a call, that just becomes another result to read — the
            agent tries again with a correction.
          </NumberedStep>
          <NumberedStep n={3} title="It only answers once it has positively checked">
            every gap type it reports on — found or clear — gets a FHIR reference, not a guess.
          </NumberedStep>
        </div>
      </Panel>

      <Callout tone="brand" label="Deliberately simple:">
        the loop itself is a plain read-tools-then-answer cycle — no planning step, no memory
        beyond this conversation. All of the reasoning lives in what the model does with the tool
        results, not in the orchestration around it.
      </Callout>
    </SlideLayout>
  );
}
