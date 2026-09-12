"use client";

import { SlideLayout } from "@/components/deck/SlideLayout";
import { SlideTitle, Lede, Panel, Callout, Tag, VizTooltip, StatTile } from "@/components/deck/parts";
import { DotField, type DotNode, type PositionFn } from "@/components/deck/DotField";
import type { SlideProps } from "@/lib/slide-types";
import { useEntered } from "@/lib/use-entered";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";
import hba1cRaw from "@/data/hba1c-timeline.json";

type Hba1cObservation = { id: string; date: string; value: number; unit: string };
type Hba1cTimeline = {
  patientName: string;
  asOf: string;
  windowStart: string;
  windowEnd: string;
  observations: Hba1cObservation[];
  totalEver: number;
  totalInWindow: number;
};

const data = hba1cRaw as Hba1cTimeline;

const WIDTH = 900;
const HEIGHT = 220;
const PAD_X = 50;
const ROW_Y = HEIGHT * 0.42;

const firstDate = new Date(data.observations[0].date).getTime();
const paddedStart = firstDate - 1000 * 60 * 60 * 24 * 200; // ~6mo lead-in before the first real dot
const windowEndMs = new Date(data.windowEnd).getTime();
const paddedEnd = windowEndMs + 1000 * 60 * 60 * 24 * 60;
const span = paddedEnd - paddedStart;

function xForTime(t: number): number {
  return PAD_X + ((t - paddedStart) / span) * (WIDTH - PAD_X * 2);
}

const timelineLayout: PositionFn = (node) => {
  const obs = node.meta as Hba1cObservation;
  return { x: xForTime(new Date(obs.date).getTime()), y: ROW_Y };
};

const nodes: DotNode[] = data.observations.map((o) => ({
  id: o.id,
  r: 4,
  color: "oklch(0.44 0.075 195)",
  opacity: 0.85,
  meta: o,
}));

const windowX0 = xForTime(new Date(data.windowStart).getTime());
const windowX1 = xForTime(new Date(data.windowEnd).getTime());
const windowMidX = (windowX0 + windowX1) / 2;

function Slide11Absence(_props: SlideProps) {
  const reducedMotion = usePrefersReducedMotion();
  // The dots themselves fly in from a scatter (DotField's own entrance
  // behaviour). Holding the "empty window" reveal back until they've mostly
  // settled turns this into two beats — the reassuring history, then the
  // gap — instead of dumping the whole argument on screen at once.
  const revealed = useEntered(reducedMotion ? 0 : 1600);

  return (
    <SlideLayout>
      <SlideTitle eyebrow="Evaluation" accent="Absence Is The Evidence">
        Proving A Negative
      </SlideTitle>
      <Lede>
        {data.patientName} has been tested for HbA1c every year since {new Date(firstDate).getFullYear()} —{" "}
        {data.totalEver} results, like clockwork. That reliable history is exactly what makes the
        real gap easy to miss: the required window comes up empty anyway.
      </Lede>

      <Panel>
        <div className="relative">
          <DotField
            nodes={nodes}
            layout={timelineLayout}
            width={WIDTH}
            height={HEIGHT}
            annotations={[
              {
                id: "empty-window",
                x: windowMidX,
                boxY: ROW_Y - 66,
                lineToY: ROW_Y - 16,
                value: "0",
                tone: "flag",
                opacity: revealed ? 1 : 0,
              },
            ]}
            captions={[
              {
                id: "window-label",
                x: windowMidX,
                y: ROW_Y + 56,
                text: "required window — empty",
                opacity: revealed ? 1 : 0,
              },
            ]}
            ariaLabel={`${data.patientName}: ${data.totalEver} HbA1c results since ${new Date(firstDate).getFullYear()}, ${data.totalInWindow} of them in the required window ending ${data.windowEnd}`}
            renderTooltip={(node) => {
              const o = node.meta as Hba1cObservation;
              return <VizTooltip title={`HbA1c ${o.value}${o.unit}`} subtitle={o.date.slice(0, 10)} />;
            }}
          />
          {/* Static overlay: the timeline track (always visible — dots travel
              along it from the first frame) plus the empty-window band,
              revealed once the dots have mostly settled. Same coordinate
              space as the DotField above. */}
          <svg
            aria-hidden
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="pointer-events-none absolute inset-0 h-auto w-full"
            preserveAspectRatio="xMidYMid meet"
          >
            <line x1={PAD_X} y1={ROW_Y} x2={WIDTH - PAD_X} y2={ROW_Y} stroke="var(--line)" strokeWidth={1} />
            <rect
              x={windowX0}
              y={ROW_Y - 34}
              width={windowX1 - windowX0}
              height={68}
              rx={6}
              fill="var(--flag-soft)"
              fillOpacity={0.35}
              stroke="var(--flag)"
              strokeDasharray="4 3"
              strokeWidth={1.25}
              style={{ opacity: revealed ? 1 : 0, transition: reducedMotion ? undefined : "opacity 600ms ease" }}
            />
          </svg>
        </div>
        <p className="mt-1 text-center font-mono text-[11px] text-ink-faint">
          total_ever: <span className="font-semibold text-ink">{data.totalEver}</span> · total_in_window:{" "}
          <span className="font-semibold text-flag-dark">{data.totalInWindow}</span> · window:{" "}
          {data.windowStart} → {data.windowEnd}
        </p>
      </Panel>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile value={String(data.totalEver)} label="HbA1c results, ever" />
        <StatTile value="0" label="results in the required window" />
        <StatTile value="6 mo" label="the window this check enforces" />
      </div>

      <Callout tone="flag" label="The hard part:">
        &ldquo;no result exists&rdquo; is only true if the search was exhaustive. An agent that
        stops after finding the rich history above and never checks <em>when</em> the last one
        landed would miss this gap entirely — and a well-tracked patient would look, wrongly,
        like a safe one.
      </Callout>

      <div className="flex items-center gap-2">
        <Tag tone="brand">oracle checks the window, not just existence</Tag>
      </div>
    </SlideLayout>
  );
}

export default Slide11Absence;
