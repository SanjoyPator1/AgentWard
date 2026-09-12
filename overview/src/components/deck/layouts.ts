import type { DotNode, PositionFn } from "@/components/deck/DotField";

// Reusable, pure layout functions — see DotField's contract: a layout is a
// pure function of (node, index, nodes, width, height) -> target {x, y}.

const GOLDEN_ANGLE = 137.50776 * (Math.PI / 180);

/** An organic, deterministic "cloud of dots" — a sunflower/phyllotaxis
 * spiral driven by index, not randomness, so the same cohort always packs
 * the same way. Elliptical (not circular) so it actually fills a wide,
 * short slide canvas instead of leaving the sides empty. Good for "here is
 * the whole population" states. */
export const phyllotaxisScatter: PositionFn = (_node, i, nodes, width, height) => {
  const cx = width / 2;
  const cy = height / 2;
  const n = Math.max(nodes.length, 1);
  const rNorm = Math.sqrt((i + 0.5) / n);
  const theta = i * GOLDEN_ANGLE;
  const rx = (width / 2 - 26) * rNorm;
  const ry = (height / 2 - 22) * rNorm;
  return { x: cx + rx * Math.cos(theta), y: cy + ry * Math.sin(theta) };
};

/** N evenly-spaced cluster centres across a horizontal band, indexed 0..n-1. */
export function rowClusterCenter(
  index: number,
  count: number,
  width: number,
  height: number,
  bandY: number,
  marginRatio = 0.11
): { x: number; y: number } {
  const margin = width * marginRatio;
  const usable = width - margin * 2;
  const x = margin + (usable * (index + 0.5)) / count;
  return { x, y: bandY };
}

/** Position at the average of several named cluster centres — this is what
 * makes a dot belonging to two categories visually sit "between" them. */
export function averagePoint(points: { x: number; y: number }[]): { x: number; y: number } {
  if (points.length === 0) return { x: 0, y: 0 };
  const x = points.reduce((s, p) => s + p.x, 0) / points.length;
  const y = points.reduce((s, p) => s + p.y, 0) / points.length;
  return { x, y };
}

export type { DotNode, PositionFn };
