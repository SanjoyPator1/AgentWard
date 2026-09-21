import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Callout, NumberedStep } from "@/components/deck/parts";
import { LoopDiagram } from "@/components/deck/LoopDiagram";

export default function Slide14AgentLoop(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="The Loop">
        Round And Round Until It Is Done
      </SlideTitle>
      <Lede>
        The loop never decides anything about medicine. It calls the model, runs whatever the
        model asked for, and hands the results back. Then it does that again. The judgement all
        happens inside the model; the code around it just keeps the conversation moving.
      </Lede>

      <Panel>
        <LoopDiagram />
      </Panel>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Panel className="h-full">
          <NumberedStep n={1} title="Several questions, one trip">
            Once it knows the patient is diabetic, the HbA1c lookup, the eye exam search and the
            blood pressure search do not depend on each other. It can send all of them together.
            On the run in the next slides, lap one is four calls and lap two is five.
          </NumberedStep>
        </Panel>
        <Panel className="h-full">
          <NumberedStep n={2} title="An error is just a result">
            When the FHIR server rejects a call, the error text goes back to the model the same
            way a normal answer would. There is no retry logic in the loop at all. The model reads
            what went wrong and tries something else on the next lap.
          </NumberedStep>
        </Panel>
        <Panel className="h-full">
          <NumberedStep n={3} title="It stops when it stops asking">
            Nothing counts the laps down or plans how many are left. The loop keeps going while
            the model keeps asking for tools, and the moment a reply comes back with no tool
            calls in it, that reply is the answer.
          </NumberedStep>
        </Panel>
      </div>

      <Callout tone="brand" label="Kept deliberately dull:">
        no planner, no scratchpad, no memory outside the current chat. Every version of this that
        adds something gets measured against this one first, so we can tell whether the extra
        piece actually helped.
      </Callout>
    </SlideLayout>
  );
}
