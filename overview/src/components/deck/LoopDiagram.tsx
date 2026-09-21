import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// LoopDiagram - the agent loop as one picture.
//
// Drawn as a single SVG rather than laid-out boxes with arrows placed on top.
// The two things this picture exists to show are the arc that returns to the
// start and the split into several tool calls at once, and both are curves
// that would drift away from their boxes the moment a flex row reflowed.
// One viewBox means the whole thing scales as a unit instead.
// ---------------------------------------------------------------------------

const BOX_Y = 88;
const BOX_H = 132;

const CHIPS = ["get_resource_by_id", "search Condition", "search Observation"];

function Box({
  x,
  w,
  n,
  title,
  subtitle,
}: {
  x: number;
  w: number;
  n: number;
  title: string;
  subtitle?: string;
}) {
  return (
    <g>
      <rect
        x={x}
        y={BOX_Y}
        width={w}
        height={BOX_H}
        rx={14}
        fill="var(--paper-soft)"
        stroke="var(--line)"
        strokeWidth={1.5}
      />
      <circle cx={x + 24} cy={BOX_Y + 26} r={12} fill="var(--brand)" />
      <text
        x={x + 24}
        y={BOX_Y + 31}
        textAnchor="middle"
        fontSize={13}
        fontWeight={700}
        fill="var(--paper-soft)"
      >
        {n}
      </text>
      <text x={x + 46} y={BOX_Y + 31} fontSize={16} fontWeight={600} fill="var(--ink)">
        {title}
      </text>
      {subtitle ? (
        <text x={x + 20} y={BOX_Y + 56} fontSize={13.5} fill="var(--ink-soft)">
          {subtitle}
        </text>
      ) : null}
    </g>
  );
}

export function LoopDiagram({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 1000 344"
      className={cn("w-full", className)}
      role="img"
      aria-label={
        "The agent loop. Your question and the four rules go in. Step one, the model decides what " +
        "to look up. Step two, the tools run, and it can ask for several in the same turn. Step " +
        "three, the results join the conversation, and the loop goes round to step one again. When " +
        "the model asks for no tools, it writes the answer instead, with a FHIR id behind every claim."
      }
    >
      <defs>
        <marker
          id="loop-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--ink-faint)" />
        </marker>
      </defs>

      {/* what goes in */}
      <rect
        x={8}
        y={119}
        width={150}
        height={70}
        rx={12}
        fill="var(--brand-soft)"
        stroke="var(--brand)"
        strokeWidth={1.5}
        strokeDasharray="5 4"
      />
      <text x={83} y={147} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--brand-dark)">
        Your question
      </text>
      <text x={83} y={169} textAnchor="middle" fontSize={13} fill="var(--brand-dark)">
        and the four rules
      </text>

      <line x1={162} y1={154} x2={190} y2={154} stroke="var(--ink-faint)" strokeWidth={1.5} markerEnd="url(#loop-arrow)" />

      <Box x={196} w={200} n={1} title="It decides" subtitle="what to look up next" />
      <Box x={436} w={220} n={2} title="The tools run" />
      <Box x={690} w={230} n={3} title="Results come back" subtitle="into the conversation" />

      {/* the tool chips: the fan-out is the whole point of box 2 */}
      {CHIPS.map((chip, i) => (
        <g key={chip}>
          <rect
            x={452}
            y={130 + i * 28}
            width={188}
            height={21}
            rx={6}
            fill="var(--paper-deep)"
            stroke="var(--line)"
          />
          <text x={462} y={144 + i * 28} fontSize={11.5} fontFamily="ui-monospace, monospace" fill="var(--ink-soft)">
            {chip}
          </text>
        </g>
      ))}
      <text x={546} y={238} textAnchor="middle" fontSize={13} fill="var(--flag-dark)">
        it can ask for several at once
      </text>

      <line x1={400} y1={154} x2={430} y2={154} stroke="var(--ink-faint)" strokeWidth={1.5} markerEnd="url(#loop-arrow)" />
      <line x1={660} y1={154} x2={684} y2={154} stroke="var(--ink-faint)" strokeWidth={1.5} markerEnd="url(#loop-arrow)" />

      {/* round again */}
      <path
        d="M 805 88 C 805 14, 296 14, 296 84"
        fill="none"
        stroke="var(--brand)"
        strokeWidth={1.8}
        markerEnd="url(#loop-arrow)"
      />
      <rect x={424} y={18} width={250} height={26} rx={8} fill="var(--paper)" />
      <text x={549} y={36} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--brand-dark)">
        still wants more, so round again
      </text>

      {/* the way out */}
      <line x1={296} y1={224} x2={296} y2={264} stroke="var(--ink-faint)" strokeWidth={1.5} markerEnd="url(#loop-arrow)" />
      <text x={282} y={246} textAnchor="end" fontSize={13} fill="var(--ink-soft)">
        when it asks for no tools
      </text>
      <rect
        x={196}
        y={268}
        width={320}
        height={62}
        rx={12}
        fill="var(--brand)"
        stroke="var(--brand-dark)"
      />
      <text x={216} y={294} fontSize={15} fontWeight={600} fill="var(--paper-soft)">
        It writes the answer
      </text>
      <text x={216} y={316} fontSize={13} fill="var(--paper-soft)" opacity={0.85}>
        with a FHIR id behind every claim
      </text>
    </svg>
  );
}
