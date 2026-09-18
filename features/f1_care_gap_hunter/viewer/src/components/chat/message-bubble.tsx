"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ListTree } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { TraceLog } from "@/components/trace-log";
import type { TrajectoryEvent } from "@/lib/types";

// The model's replies are markdown (headings, bold, numbered lists, inline
// code for FHIR references) - rendered plain, that showed up as literal
// "**text**" and "1." syntax instead of formatting. User messages are typed
// text, not markdown, so only assistant content goes through this.
const MARKDOWN_COMPONENTS = {
  p: (props: React.ComponentProps<"p">) => <p className="mb-2 last:mb-0" {...props} />,
  ul: (props: React.ComponentProps<"ul">) => (
    <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0" {...props} />
  ),
  ol: (props: React.ComponentProps<"ol">) => (
    <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0" {...props} />
  ),
  strong: (props: React.ComponentProps<"strong">) => (
    <strong className="font-semibold" {...props} />
  ),
  code: (props: React.ComponentProps<"code">) => (
    <code className="rounded bg-surface-muted px-1 py-0.5 font-mono text-[0.85em]" {...props} />
  ),
  a: (props: React.ComponentProps<"a">) => (
    <a className="text-primary underline underline-offset-2" {...props} />
  ),
};

export interface ChatTurnDisplay {
  role: "user" | "assistant";
  content: string;
  trace?: TrajectoryEvent[];
  pending?: boolean;
  isError?: boolean;
}

export function MessageBubble({ turn }: { turn: ChatTurnDisplay }) {
  // Collapsible once the turn is fully done and successful (so a long trace
  // doesn't clutter the conversation once you have your answer). Forced open
  // while pending (nothing else to look at yet) AND on error - the steps
  // already completed before a failure are exactly the useful diagnostic
  // info, not something to hide behind a click.
  const [userToggledOpen, setUserToggledOpen] = useState<boolean | null>(null);
  const traceOpen = userToggledOpen ?? (Boolean(turn.pending) || Boolean(turn.isError));
  const isUser = turn.role === "user";
  const hasTrace = !isUser && !!turn.trace && turn.trace.length > 0;

  return (
    <div className={cn("flex flex-col gap-1.5", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3.5 py-2.5 text-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : turn.isError
              ? "border border-danger/40 bg-danger-soft text-danger"
              : "border border-border bg-surface text-foreground",
        )}
      >
        {turn.content ? (
          isUser ? (
            turn.content
          ) : (
            <ReactMarkdown components={MARKDOWN_COMPONENTS}>{turn.content}</ReactMarkdown>
          )
        ) : turn.pending ? (
          <ThinkingDots />
        ) : null}
      </div>

      {hasTrace && (
        <div className="w-full max-w-[85%]">
          <button
            type="button"
            onClick={() => setUserToggledOpen(!traceOpen)}
            className="flex items-center gap-1.5 text-xs font-medium text-foreground-faint hover:text-foreground-muted"
          >
            {traceOpen ? (
              <ChevronDown className="size-3" />
            ) : (
              <ChevronRight className="size-3" />
            )}
            <ListTree className="size-3" />
            {turn.pending
              ? "Working"
              : turn.isError
                ? "Trace before the error"
                : `${turn.trace!.length} event${turn.trace!.length === 1 ? "" : "s"}`}
          </button>
          {traceOpen && (
            <div className="mt-1.5 max-h-80 overflow-y-auto rounded-md border border-border bg-background p-2.5 scrollbar-thin">
              <TraceLog events={turn.trace!} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ThinkingDots() {
  return (
    <span className="flex items-center gap-1 text-foreground-faint">
      <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-current" />
    </span>
  );
}
