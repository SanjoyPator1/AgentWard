import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Callout, Tag, StickyNote } from "@/components/deck/parts";

type Part = {
  n: number;
  name: string;
  what: string;
  detail: string;
};

const PARTS: Part[] = [
  {
    n: 1,
    name: "A model",
    what: "Gemini 3.5 Flash Lite, in these runs",
    detail:
      "Nothing about the setup is tied to it. Swap in another model and the rest of the code does not change.",
  },
  {
    n: 2,
    name: "A prompt",
    what: "about 10,000 characters of plain text",
    detail:
      "Today's date, the four gap rules with their cutoff dates already worked out, and a list of the traps that make agents wrong on this data.",
  },
  {
    n: 3,
    name: "Eight tools",
    what: "7 from fhir-mcp, 1 running locally",
    detail:
      "The three Level 1 and four Level 2 tools from earlier in this deck, plus a local code lookup so it never has to recall a SNOMED code from memory.",
  },
  {
    n: 4,
    name: "A loop",
    what: "326 lines of Python, comments included",
    detail:
      "Call the model, run whatever tools it asked for, hand back the results, ask it again. That is the whole engine.",
  },
];

export default function Slide13AgentParts(_props: SlideProps) {
  return (
    <SlideLayout>
      <div className="flex flex-wrap items-center gap-3">
        <SlideTitle eyebrow="The Agent" accent="Four Plain Parts">
          What An Agent Actually Is
        </SlideTitle>
        <Tag tone="brand">agent: live</Tag>
      </div>
      <Lede>
        The word agent makes people picture something clever and hard to build. This one is four
        pieces, and you can read all of them in an afternoon.
      </Lede>

      <div className="relative">
        <StickyNote className="absolute -top-6 right-0 z-10 hidden lg:block" rotate="rotate-2">
          no magic in here.
        </StickyNote>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PARTS.map((part) => (
            <Panel key={part.n} className="flex h-full flex-col gap-1.5">
              <div className="flex items-baseline gap-2">
                <span className="font-serif text-2xl font-bold text-brand">{part.n}</span>
                <span className="text-[15px] font-semibold text-ink">{part.name}</span>
              </div>
              <p className="font-mono text-[11.5px] text-brand-dark">{part.what}</p>
              <p className="text-[13px] leading-snug text-ink-soft">{part.detail}</p>
            </Panel>
          ))}
        </div>
      </div>

      <Callout tone="flag" label="Worth saying out loud:">
        none of the answers exist before you ask. There is no table of results sitting in a
        database waiting to be looked up. Every reply is built during the conversation, from tool
        calls made while you wait.
      </Callout>
    </SlideLayout>
  );
}
