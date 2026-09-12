"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { forceSimulation, forceX, forceY, forceCollide, type Simulation, type ForceX, type ForceY } from "d3-force";
import { cn } from "@/lib/utils";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";

// ---------------------------------------------------------------------------
// DotField — the one primitive most of the deck's visualizations reuse.
//
// One dot is always one real record (a patient, a resource, a condition).
// A "layout" is a pure function of (node, index, nodes, width, height) that
// returns where that dot *wants* to be; a d3-force simulation nudges every
// dot toward that target and keeps them from overlapping, which is what
// produces the "fly to the new arrangement" transition when layout changes.
// Position is written straight to the DOM on every tick — never through
// React state — so 217 dots animating doesn't mean 217 re-renders a frame.
// ---------------------------------------------------------------------------

export type DotNode = {
  id: string;
  r?: number;
  color: string;
  opacity?: number;
  meta?: unknown;
};

export type PositionFn = (
  node: DotNode,
  index: number,
  nodes: DotNode[],
  width: number,
  height: number
) => { x: number; y: number };

export type DotAnnotation = {
  id: string;
  x: number;
  boxY: number;
  lineToY: number;
  value: string;
  tone?: "brand" | "flag" | "neutral";
  opacity?: number;
};

export type DotCaption = {
  id: string;
  x: number;
  y: number;
  text: string;
  align?: "start" | "middle" | "end";
  opacity?: number;
};

type SimNode = DotNode & { x: number; y: number; vx?: number; vy?: number };

const TONE_STROKE: Record<string, string> = {
  brand: "var(--brand)",
  flag: "var(--flag)",
  neutral: "var(--line)",
};

export function DotField({
  nodes,
  layout,
  width = 900,
  height = 460,
  annotations = [],
  captions = [],
  renderTooltip,
  className,
  ariaLabel,
}: {
  nodes: DotNode[];
  layout: PositionFn;
  width?: number;
  height?: number;
  annotations?: DotAnnotation[];
  captions?: DotCaption[];
  renderTooltip?: (node: DotNode) => ReactNode;
  className?: string;
  ariaLabel: string;
}) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const circleRefs = useRef(new Map<string, SVGCircleElement>());
  const simDataRef = useRef(new Map<string, SimNode>());
  const simRef = useRef<Simulation<SimNode, undefined> | null>(null);
  const fxRef = useRef<ForceX<SimNode> | null>(null);
  const fyRef = useRef<ForceY<SimNode> | null>(null);

  const [hover, setHover] = useState<{ node: DotNode; x: number; y: number } | null>(null);
  const reducedMotion = usePrefersReducedMotion();

  const targets = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    nodes.forEach((n, i) => map.set(n.id, layout(n, i, nodes, width, height)));
    return map;
  }, [nodes, layout, width, height]);

  useEffect(() => {
    const dataMap = simDataRef.current;
    const nextIds = new Set(nodes.map((n) => n.id));
    for (const id of Array.from(dataMap.keys())) {
      if (!nextIds.has(id)) dataMap.delete(id);
    }
    for (const n of nodes) {
      const t = targets.get(n.id) ?? { x: width / 2, y: height / 2 };
      const existing = dataMap.get(n.id);
      if (existing) {
        existing.r = n.r ?? 3.5;
      } else {
        // A brand-new node (this id's first appearance in this mounted
        // instance) starts at a scattered position and flies to its target
        // via the same force that drives every later layout change — so a
        // slide's first paint is a transition too, not a pop-in. Skipped
        // under reduced motion, where it would just start at rest.
        const startX = reducedMotion ? t.x : Math.random() * width;
        const startY = reducedMotion ? t.y : Math.random() * height;
        dataMap.set(n.id, { ...n, x: startX, y: startY, r: n.r ?? 3.5 });
      }
    }
    const simNodes = nodes.map((n) => dataMap.get(n.id)!);

    const xAccessor = (d: SimNode) => targets.get(d.id)?.x ?? d.x;
    const yAccessor = (d: SimNode) => targets.get(d.id)?.y ?? d.y;

    const draw = () => {
      for (const d of simNodes) {
        const el = circleRefs.current.get(d.id);
        if (el) {
          el.setAttribute("cx", String(d.x));
          el.setAttribute("cy", String(d.y));
        }
      }
    };

    if (!simRef.current) {
      // Gentle strength + slow decay: a settle that takes a little over a
      // second and is visibly a *flight*, not a snap. Tuned to be seen, not
      // just technically present — this is a presentation, not a spinner.
      const fx = forceX<SimNode>(xAccessor).strength(0.02);
      const fy = forceY<SimNode>(yAccessor).strength(0.02);
      fxRef.current = fx;
      fyRef.current = fy;
      simRef.current = forceSimulation<SimNode>(simNodes)
        .force("x", fx)
        .force("y", fy)
        .force(
          "collide",
          forceCollide<SimNode>((d) => (d.r ?? 3.5) + 1.4).strength(0.85)
        )
        // Default velocityDecay (0.4) lets velocity compound tick over tick,
        // which made even a weak force snap into place within a few frames.
        // Damping harder keeps the motion at the speed the strength implies
        // instead of a spring-like sprint.
        .velocityDecay(0.82)
        .alphaDecay(0.018)
        .on("tick", draw);
    } else {
      simRef.current.nodes(simNodes);
      fxRef.current?.x(xAccessor);
      fyRef.current?.y(yAccessor);
    }

    const sim = simRef.current;
    if (reducedMotion) {
      sim.stop();
      sim.alpha(1);
      for (let i = 0; i < 300; i++) sim.tick();
      draw();
    } else {
      sim.alpha(0.9).restart();
    }
  }, [nodes, targets, width, height, reducedMotion]);

  useEffect(() => {
    return () => {
      simRef.current?.stop();
    };
  }, []);

  const toneStroke = (tone?: string) => TONE_STROKE[tone ?? "neutral"] ?? TONE_STROKE.neutral;

  return (
    <div ref={wrapperRef} className={cn("relative w-full", className)}>
      <span className="sr-only">{ariaLabel}</span>
      <svg
        aria-hidden
        viewBox={`0 0 ${width} ${height}`}
        className="block h-auto w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {annotations.map((a) => (
          <g
            key={`ann-${a.id}`}
            style={{
              opacity: a.opacity ?? 1,
              transition: reducedMotion ? undefined : "opacity 500ms ease",
            }}
          >
            <line
              x1={a.x}
              y1={a.boxY + 11}
              x2={a.x}
              y2={a.lineToY}
              stroke={toneStroke(a.tone)}
              strokeWidth={1}
              opacity={0.55}
            />
            <rect
              x={a.x - 22}
              y={a.boxY - 11}
              width={44}
              height={22}
              rx={4}
              fill="var(--paper-soft)"
              stroke={toneStroke(a.tone)}
              strokeWidth={1.25}
            />
            <text
              x={a.x}
              y={a.boxY + 4}
              textAnchor="middle"
              className="font-mono text-[11px] font-semibold"
              fill="var(--ink)"
            >
              {a.value}
            </text>
          </g>
        ))}

        {nodes.map((n) => (
          <circle
            key={n.id}
            ref={(el) => {
              if (el) circleRefs.current.set(n.id, el);
              else circleRefs.current.delete(n.id);
            }}
            r={n.r ?? 3.5}
            style={{
              fill: n.color,
              opacity: n.opacity ?? 1,
              transition: reducedMotion ? undefined : "fill 500ms ease, opacity 500ms ease",
              cursor: renderTooltip ? "pointer" : undefined,
            }}
            onMouseEnter={(e) => {
              if (!renderTooltip) return;
              const rect = wrapperRef.current?.getBoundingClientRect();
              if (!rect) return;
              setHover({ node: n, x: e.clientX - rect.left, y: e.clientY - rect.top });
            }}
            onMouseMove={(e) => {
              if (!renderTooltip || !hover || hover.node.id !== n.id) return;
              const rect = wrapperRef.current?.getBoundingClientRect();
              if (!rect) return;
              setHover({ node: n, x: e.clientX - rect.left, y: e.clientY - rect.top });
            }}
            onMouseLeave={() => setHover(null)}
          />
        ))}

        {captions.map((c) => (
          <text
            key={`cap-${c.id}`}
            x={c.x}
            y={c.y}
            textAnchor={c.align ?? "middle"}
            className="font-mono text-[11px] uppercase tracking-wide"
            fill="var(--ink-faint)"
            style={{
              opacity: c.opacity ?? 1,
              transition: reducedMotion ? undefined : "opacity 500ms ease",
            }}
          >
            {c.text}
          </text>
        ))}
      </svg>

      {hover && renderTooltip ? (
        <div
          className="pointer-events-none absolute z-20 max-w-[240px] -translate-x-1/2 -translate-y-full pb-2"
          style={{ left: hover.x, top: hover.y }}
        >
          {renderTooltip(hover.node)}
        </div>
      ) : null}
    </div>
  );
}
