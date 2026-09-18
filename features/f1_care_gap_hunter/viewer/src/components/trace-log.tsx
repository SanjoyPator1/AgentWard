"use client";

import { useState } from "react";
import { Brain, ChevronRight, Cog, Loader2, Plug } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToolDetail } from "@/components/chat/tool-detail-drawer";
import type {
  LlmCallFinishedData,
  RunFinishedData,
  RunStartedData,
  ToolCallFinishedData,
  ToolCallStartedData,
  TrajectoryEvent,
} from "@/lib/types";

/**
 * Renders the TrajectoryEvent stream as a step timeline rather than a raw
 * log: each model turn ("thinking") is visually distinct from each tool
 * call ("doing"), tool calls are colored by outcome and shaped by source
 * (mcp vs local) so the two are never confused, and every tool call opens
 * the shared detail drawer to inspect its exact arguments and result -
 * nothing here is a summary or reconstruction, every value comes straight
 * off the event the backend emits (trajectory.py).
 */

interface ToolEntry {
  id: string;
  step: number | null;
  started: ToolCallStartedData;
  finished: ToolCallFinishedData | null;
}

type TimelineItem =
  | { kind: "run_started"; id: string; data: RunStartedData }
  | { kind: "run_finished"; id: string; data: RunFinishedData; isChat: boolean }
  | { kind: "thinking"; id: string; step: number | null; data: LlmCallFinishedData }
  | { kind: "thinking_pending"; id: string; step: number | null }
  | { kind: "tool"; id: string; entry: ToolEntry };

function buildTimeline(events: TrajectoryEvent[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  // Tool calls are issued and awaited one at a time within a step (see
  // f1_care_gap_hunter/harness/v1/loop.py), so started/finished for the
  // same tool always arrive adjacently - the most recent open entry for a
  // given tool name is always the right one to close.
  const openByName = new Map<string, ToolEntry>();
  // The chat agent (task_id "chat") always reports 0 findings and a
  // "submit" it never actually calls - see chat_agent.py, there's no
  // submit_findings tool in that path. Those two fields are meaningless
  // there, so the run_finished divider hides them for chat runs.
  let isChat = false;

  events.forEach((event, index) => {
    const id = `${index}`;
    switch (event.event_type) {
      case "run_started": {
        const data = event.data as unknown as RunStartedData;
        isChat = data.task_id === "chat";
        items.push({ kind: "run_started", id, data });
        break;
      }
      case "llm_call_started":
        items.push({ kind: "thinking_pending", id, step: event.step });
        break;
      case "llm_call_finished": {
        const pendingIndex = items.findIndex(
          (item) => item.kind === "thinking_pending" && item.step === event.step,
        );
        const resolved: TimelineItem = {
          kind: "thinking",
          id,
          step: event.step,
          data: event.data as unknown as LlmCallFinishedData,
        };
        if (pendingIndex >= 0) {
          items[pendingIndex] = resolved;
        } else {
          items.push(resolved);
        }
        break;
      }
      case "tool_call_started": {
        const data = event.data as unknown as ToolCallStartedData;
        const entry: ToolEntry = { id, step: event.step, started: data, finished: null };
        openByName.set(data.tool_name, entry);
        items.push({ kind: "tool", id, entry });
        break;
      }
      case "tool_call_finished": {
        const data = event.data as unknown as ToolCallFinishedData;
        const open = openByName.get(data.tool_name);
        if (open) {
          open.finished = data;
          openByName.delete(data.tool_name);
        }
        break;
      }
      case "run_finished":
        items.push({
          kind: "run_finished",
          id,
          data: event.data as unknown as RunFinishedData,
          isChat,
        });
        break;
    }
  });

  return items;
}

export function TraceLog({ events }: { events: TrajectoryEvent[] }) {
  if (events.length === 0) {
    return <p className="px-1 py-6 text-center text-sm text-foreground-faint">No activity yet.</p>;
  }

  const items = buildTimeline(events);

  return (
    <ol className="relative flex flex-col gap-2 pl-5 text-sm before:absolute before:left-[5px] before:top-1.5 before:bottom-1.5 before:w-px before:bg-border">
      {items.map((item) => {
        switch (item.kind) {
          case "run_started":
            return <RunDivider key={item.id} label={runStartedLabel(item.data)} />;
          case "run_finished":
            return (
              <RunDivider
                key={item.id}
                label={runFinishedLabel(item.data, item.isChat)}
                tone="final"
              />
            );
          case "thinking_pending":
            return <ThinkingPendingRow key={item.id} step={item.step} />;
          case "thinking":
            return <ThinkingRow key={item.id} step={item.step} data={item.data} />;
          case "tool":
            return <ToolCard key={item.id} entry={item.entry} />;
          default:
            return null;
        }
      })}
    </ol>
  );
}

function Node({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "absolute -left-5 top-0.5 flex size-2.5 items-center justify-center rounded-full bg-background",
        className,
      )}
    >
      {children}
    </span>
  );
}

function RunDivider({ label, tone }: { label: string; tone?: "final" }) {
  return (
    <li className="relative -ml-5 flex items-center gap-2 py-1 pl-5">
      <Node className={tone === "final" ? "text-success" : "text-primary"}>
        <span className="size-1.5 rounded-full bg-current" />
      </Node>
      <span className="text-xs font-medium uppercase tracking-wide text-foreground-faint">
        {label}
      </span>
    </li>
  );
}

function runStartedLabel(data: RunStartedData) {
  return `Run started · patient ${data.task_id} · ${data.provider}/${data.model}`;
}

function runFinishedLabel(data: RunFinishedData, isChat: boolean) {
  const base = `Run finished · ${data.total_steps} steps · ${data.total_tokens} tok · ${Math.round(
    data.duration_ms,
  )}ms`;
  if (isChat) return base;
  return `Run finished · ${data.findings.length} finding${data.findings.length === 1 ? "" : "s"} · ${
    data.terminated_by
  } · ${data.total_steps} steps · ${data.total_tokens} tok · ${Math.round(data.duration_ms)}ms`;
}

function ThinkingPendingRow({ step }: { step: number | null }) {
  return (
    <li className="relative flex items-start gap-2 py-0.5">
      <Node className="text-primary">
        <Loader2 className="size-3 animate-spin" />
      </Node>
      <span className="italic text-foreground-faint">
        thinking{step != null ? ` · step ${step + 1}` : ""}&hellip;
      </span>
    </li>
  );
}

function ThinkingRow({ step, data }: { step: number | null; data: LlmCallFinishedData }) {
  const [expanded, setExpanded] = useState(false);
  const hasReasoning = Boolean(data.reasoning);
  const isFinal = data.tool_call_names.length === 0;

  return (
    <li className="relative py-0.5">
      <Node className="text-primary">
        <Brain className="size-3" />
      </Node>
      <button
        type="button"
        onClick={() => hasReasoning && setExpanded((v) => !v)}
        disabled={!hasReasoning}
        className={cn(
          "flex w-full items-start gap-1.5 text-left italic text-foreground-faint",
          hasReasoning && "cursor-pointer hover:text-foreground-muted",
        )}
      >
        {hasReasoning && (
          <ChevronRight
            className={cn("mt-0.5 size-3 shrink-0 not-italic transition-transform", expanded && "rotate-90")}
          />
        )}
        <span>
          {isFinal ? "reached a final answer" : `requested ${data.tool_call_names.join(", ")}`}
          {step != null ? ` · step ${step + 1}` : ""}
          {typeof data.prompt_tokens === "number" && (
            <span className="tabular-nums">
              {" "}
              · {data.prompt_tokens + (data.completion_tokens ?? 0)} tok · {Math.round(data.duration_ms)}ms
            </span>
          )}
        </span>
      </button>
      {expanded && hasReasoning && (
        <pre className="mt-1.5 whitespace-pre-wrap rounded-md border border-border bg-surface-muted p-2.5 font-mono text-xs not-italic text-foreground-muted">
          {data.reasoning}
        </pre>
      )}
      {!isFinal && data.content && (
        <p className="mt-1.5 whitespace-pre-wrap text-sm not-italic text-foreground">{data.content}</p>
      )}
    </li>
  );
}

function compactPreview(args: Record<string, unknown>): string {
  const entries = Object.entries(args).map(([key, value]) => `${key}: ${JSON.stringify(value)}`);
  const joined = entries.join(", ");
  return joined.length > 64 ? `${joined.slice(0, 64)}…` : joined;
}

// Shape says what kind of call this is (mcp vs local); color says what
// happened (running / succeeded / failed) - kept as two independent
// signals rather than one icon trying to carry both.
function ToolNodeIcon({ source }: { source: ToolCallStartedData["source"] }) {
  return source === "mcp" ? <Plug className="size-3" /> : <Cog className="size-3" />;
}

function ToolCard({ entry }: { entry: ToolEntry }) {
  const { open } = useToolDetail();
  const { started, finished } = entry;
  const running = finished === null;
  const isError = finished?.is_error ?? false;

  return (
    <li className="relative py-0.5">
      <Node className={running ? "text-warning" : isError ? "text-danger" : "text-success"}>
        {running ? <Loader2 className="size-3 animate-spin" /> : <ToolNodeIcon source={started.source} />}
      </Node>
      <button
        type="button"
        onClick={() => open({ started, finished })}
        className={cn(
          "flex w-full items-center gap-2 rounded-md border bg-surface px-2.5 py-1.5 text-left hover:bg-surface-muted",
          isError ? "border-danger/30" : "border-border",
        )}
      >
        <span
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
            started.source === "mcp"
              ? "bg-info-soft text-info"
              : "bg-primary-soft text-primary",
          )}
        >
          {started.source}
        </span>
        <span className="shrink-0 font-mono text-[13px] font-medium text-foreground">
          {started.tool_name}
        </span>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground-faint">
          {compactPreview(started.arguments)}
        </span>
        <span
          className={cn(
            "shrink-0 text-xs tabular-nums",
            running ? "text-warning" : isError ? "text-danger" : "text-foreground-faint",
          )}
        >
          {running ? "running…" : `${Math.round(finished!.duration_ms)}ms`}
        </span>
        <ChevronRight className="size-3 shrink-0 text-foreground-faint" />
      </button>
    </li>
  );
}
