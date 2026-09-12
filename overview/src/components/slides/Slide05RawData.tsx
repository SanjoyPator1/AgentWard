"use client";

import { useMemo } from "react";
import { SlideLayout } from "@/components/deck/SlideLayout";
import { SlideTitle, Lede, Panel, Tag, PullQuote, VizTooltip } from "@/components/deck/parts";
import { DotField, type DotNode, type PositionFn } from "@/components/deck/DotField";
import { phyllotaxisScatter } from "@/components/deck/layouts";
import { colorForResourceType, RESOURCE_TYPE_ORDER, OTHER_RESOURCE_COLOR } from "@/lib/resource-colors";
import { NEUTRAL_COLOR } from "@/lib/gap-types";
import type { BundleProfile, BundleResource } from "@/lib/viz-types";
import type { SlideProps } from "@/lib/slide-types";
import { cn } from "@/lib/utils";
import bundleProfileRaw from "@/data/bundle-profile.json";

const data = bundleProfileRaw as BundleProfile;

const AMBER = "oklch(0.62 0.1 65)";
const FLAG = "oklch(0.58 0.14 45)";

const activeInfo = new Map(data.conditionBreakdown.conditions.map((c) => [c.id, c]));

const STEP_LABELS = ["All 462 Resources", "Isolate 24 Conditions", "Which Are Real Problems?"];

const conditionCluster: PositionFn = (_node, _i, _nodes, width, height) => ({
  x: width / 2,
  y: height / 2,
});

function styleForStep(node: BundleResource, step: number): { color: string; opacity: number; r: number } {
  const isCondition = node.resourceType === "Condition";

  if (step === 0) {
    return { color: colorForResourceType(node.resourceType), opacity: 0.75, r: 2.6 };
  }
  if (step === 1) {
    return isCondition
      ? { color: FLAG, opacity: 0.92, r: 3.6 }
      : { color: OTHER_RESOURCE_COLOR, opacity: 0.05, r: 2 };
  }
  // step === 2
  if (!isCondition) return { color: OTHER_RESOURCE_COLOR, opacity: 0.04, r: 2 };
  const info = activeInfo.get(node.id);
  if (!info) return { color: NEUTRAL_COLOR, opacity: 0.15, r: 2.4 };
  return info.isRealProblem
    ? { color: FLAG, opacity: 0.95, r: 4.2 }
    : { color: AMBER, opacity: 0.55, r: 3 };
}

function Slide05RawData({ step, onStepChange }: SlideProps) {
  const nodes: DotNode[] = useMemo(
    () =>
      data.resources.map((r) => {
        const s = styleForStep(r, step);
        return { id: `${r.resourceType}-${r.id}`, r: s.r, color: s.color, opacity: s.opacity, meta: r };
      }),
    [step]
  );

  const layout = step === 0 ? phyllotaxisScatter : conditionCluster;

  const runningCount =
    step === 0
      ? `${data.totalResources} resources`
      : step === 1
        ? `${data.conditionBreakdown.totalAllConditions} conditions`
        : `${data.conditionBreakdown.totalActive} active → ${data.conditionBreakdown.totalRealProblems} real diagnoses`;

  return (
    <SlideLayout>
      <SlideTitle eyebrow="The Data" accent="One JSON Bundle Per Patient">
        What Synthea Actually Outputs
      </SlideTitle>
      <Lede>
        {data.patientName}&apos;s entire record, one JSON file, {data.totalResources} FHIR
        resources — and nothing in it separates a diagnosis from a life detail until you filter
        for it yourself.
      </Lede>

      <div className="flex flex-wrap items-center gap-2">
        {STEP_LABELS.map((label, i) => (
          <button
            key={label}
            onClick={() => onStepChange(i)}
            className={cn(
              "rounded-full border px-3 py-1.5 font-mono text-[12px] font-medium transition-colors",
              step === i
                ? "border-brand bg-brand text-paper-soft"
                : "border-line bg-paper-soft text-ink-soft hover:border-brand/40 hover:text-brand-dark"
            )}
          >
            {i + 1}. {label}
          </button>
        ))}
      </div>

      <Panel>
        <DotField
          nodes={nodes}
          layout={layout}
          width={900}
          height={340}
          ariaLabel={`${data.patientName}'s bundle: ${runningCount}`}
          renderTooltip={(node) => {
            const r = node.meta as BundleResource;
            const info = r.resourceType === "Condition" ? activeInfo.get(r.id) : undefined;
            return (
              <VizTooltip
                title={r.label}
                subtitle={`${r.resourceType}${r.date ? ` · ${r.date.slice(0, 10)}` : ""}`}
                tone={info?.isRealProblem ? "flag" : "neutral"}
                rows={
                  r.resourceType === "Condition"
                    ? [{ text: info ? (info.isRealProblem ? "active · real diagnosis" : "active · not a diagnosis") : "not active", tone: info?.isRealProblem ? ("flag" as const) : undefined }]
                    : undefined
                }
              />
            );
          }}
        />
        <p className="mt-1 text-center font-mono text-[11px] text-ink-faint">{runningCount}</p>
      </Panel>

      {step === 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {RESOURCE_TYPE_ORDER.map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-paper-soft px-2.5 py-1">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colorForResourceType(t) }} />
              <span className="font-mono text-[10.5px] text-ink-soft">{t}</span>
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-paper-soft px-2.5 py-1">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: OTHER_RESOURCE_COLOR }} />
            <span className="font-mono text-[10.5px] text-ink-soft">everything else (billing, provenance…)</span>
          </span>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="flex flex-wrap items-center gap-3">
          <Tag tone="flag">● real diagnosis</Tag>
          <Tag tone="neutral">● active, not a diagnosis</Tag>
          <span className="text-[12px] text-ink-faint">
            e.g. &ldquo;{data.conditionBreakdown.conditions.find((c) => !c.isRealProblem)?.text}&rdquo; — active, but not what a
            clinician would call a diagnosis
          </span>
        </div>
      ) : null}

      <PullQuote>
        One patient&apos;s {data.conditionBreakdown.totalAllConditions} Condition entries hide{" "}
        {data.conditionBreakdown.totalRealProblems} real diagnoses — same resource type, same
        category, no field that tells them apart. That gap is exactly what the Level 2 tools have
        to close.
      </PullQuote>
    </SlideLayout>
  );
}

Slide05RawData.steps = STEP_LABELS.length;

export default Slide05RawData;
