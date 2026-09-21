import { SlideLayout } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Callout, StatTile, Tag } from "@/components/deck/parts";

type Row = {
  label: string;
  before: string;
  after: string;
};

// Measured on two saved runs of the same question about the same patient,
// one before the narrative default and one after it.
const ROWS: Row[] = [
  { label: "average result", before: "2,437 chars", after: "591 chars" },
  { label: "largest result", before: "3,819 chars", after: "967 chars" },
  { label: "results that got trimmed", before: "4 of 10", after: "0 of 11" },
];

export default function Slide15AgentGuards(_props: SlideProps) {
  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Agent" accent="Limits That Bite">
        What Stops It Running Forever
      </SlideTitle>
      <Lede>
        A loop that keeps going until a model says stop needs a few hard edges. There are only
        two, and one of them almost stopped mattering once the tools changed how they talk.
      </Lede>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value="24" label="laps allowed in one chat turn" />
        <StatTile value="5" label="laps the real run actually used" />
        <StatTile value="4,000" label="characters allowed per tool result" />
        <StatTile value="0" label="results trimmed on that run" />
      </div>

      <Panel>
        <p className="font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
          when a result is too big
        </p>
        <p className="mt-2 text-[13.5px] leading-snug text-ink-soft">
          Cutting the text at 4,000 characters used to slice a resource in half and cost the
          agent a second call to read the field it lost. So the cap drops whole records instead,
          newest first, and tells the agent in the result how many it dropped and how to avoid it
          next time. Every check here is some version of &ldquo;did this happen recently&rdquo;,
          so the newest records are the ones worth keeping.
        </p>
      </Panel>

      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
            then the tools started answering in prose
          </p>
          <Tag tone="brand">same question, same patient</Tag>
        </div>
        <div className="mt-3 overflow-hidden rounded-lg border border-line">
          <div className="grid grid-cols-[1.3fr_1fr_1fr] bg-paper-deep/60 px-3 py-2">
            <span className="text-[11.5px] font-semibold text-ink-soft"> </span>
            <span className="text-center font-mono text-[11px] text-ink-faint">raw JSON</span>
            <span className="text-center font-mono text-[11px] text-brand-dark">narrative</span>
          </div>
          {ROWS.map((row) => (
            <div
              key={row.label}
              className="grid grid-cols-[1.3fr_1fr_1fr] items-center border-t border-line/70 px-3 py-2"
            >
              <span className="text-[12.5px] text-ink-soft">{row.label}</span>
              <span className="text-center font-mono text-[12.5px] text-ink-faint">{row.before}</span>
              <span className="text-center font-mono text-[12.5px] font-semibold text-brand-dark">
                {row.after}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-2.5 text-[12px] leading-snug text-ink-faint">
          Every Level 2 tool now writes its answer as a sentence unless something asks it not to.
          Results came back about four times smaller, and the cap stopped firing.
        </p>
      </Panel>

      <Callout tone="flag" label="The part people miss:">
        those four trimmed results were not a warning on screen. They were older records quietly
        dropped out of what the agent could see, on a task whose whole job is proving that
        nothing was recorded.
      </Callout>
    </SlideLayout>
  );
}
