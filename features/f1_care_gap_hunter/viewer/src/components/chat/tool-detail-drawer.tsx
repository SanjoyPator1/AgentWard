"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, Loader2, Plug, Wrench, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolCallFinishedData, ToolCallStartedData } from "@/lib/types";

export interface ToolDetail {
  started: ToolCallStartedData;
  finished: ToolCallFinishedData | null;
}

interface ToolDetailContextValue {
  open: (detail: ToolDetail) => void;
}

const ToolDetailContext = createContext<ToolDetailContextValue | null>(null);

export function useToolDetail(): ToolDetailContextValue {
  const ctx = useContext(ToolDetailContext);
  if (!ctx) throw new Error("useToolDetail must be used within a ToolDetailProvider");
  return ctx;
}

/**
 * One shared side panel for the whole app rather than one per trace, so a
 * click anywhere - chat or worklist - opens the same drawer instead of an
 * inline block competing for space in an already-scrolling trace list (see
 * craft-floor.md's note on overlays escaping their container).
 */
export function ToolDetailProvider({ children }: { children: React.ReactNode }) {
  const [detail, setDetail] = useState<ToolDetail | null>(null);

  const open = useCallback((next: ToolDetail) => setDetail(next), []);
  const close = useCallback(() => setDetail(null), []);

  useEffect(() => {
    if (!detail) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [detail, close]);

  return (
    <ToolDetailContext.Provider value={{ open }}>
      {children}
      {detail && createPortal(<ToolDetailDrawer detail={detail} onClose={close} />, document.body)}
    </ToolDetailContext.Provider>
  );
}

function prettyPrint(raw: string | undefined): { text: string; isJson: boolean } {
  if (!raw) return { text: "", isJson: false };
  try {
    return { text: JSON.stringify(JSON.parse(raw), null, 2), isJson: true };
  } catch {
    return { text: raw, isJson: false };
  }
}

function ToolDetailDrawer({ detail, onClose }: { detail: ToolDetail; onClose: () => void }) {
  const { started, finished } = detail;
  const running = finished === null;
  const isError = finished?.is_error ?? false;
  const args = prettyPrint(JSON.stringify(started.arguments));
  const result = prettyPrint(finished?.result_full ?? finished?.result_summary);
  const resultTruncated =
    !running && !!finished?.result_summary && !finished.result_full;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close detail"
        onClick={onClose}
        className="absolute inset-0 bg-black/25"
      />
      <div className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3.5">
          <div className="flex min-w-0 items-center gap-2">
            {started.source === "mcp" ? (
              <Plug className="size-4 shrink-0 text-info" />
            ) : (
              <Wrench className="size-4 shrink-0 text-primary" />
            )}
            <div className="min-w-0">
              <p className="truncate font-mono text-sm font-medium text-foreground">
                {started.tool_name}
              </p>
              <p className="text-xs text-foreground-faint">
                {started.source === "mcp" ? "MCP tool" : "Local tool"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-md p-1.5 text-foreground-faint hover:bg-surface-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex items-center gap-1.5 border-b border-border px-4 py-2.5 text-xs">
          {running ? (
            <>
              <Loader2 className="size-3.5 animate-spin text-warning" />
              <span className="text-foreground-muted">Running&hellip;</span>
            </>
          ) : isError ? (
            <>
              <XCircle className="size-3.5 text-danger" />
              <span className="text-danger">
                Failed &middot; {Math.round(finished!.duration_ms)}ms
              </span>
            </>
          ) : (
            <>
              <CheckCircle2 className="size-3.5 text-success" />
              <span className="text-foreground-muted">
                Succeeded &middot; {Math.round(finished!.duration_ms)}ms
              </span>
            </>
          )}
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-4 px-4 py-4">
          <DetailSection label="Arguments">
            <pre
              className={cn(
                "whitespace-pre-wrap break-words font-mono text-xs",
                args.isJson ? "text-foreground" : "text-foreground-muted",
              )}
            >
              {args.text || "{}"}
            </pre>
          </DetailSection>

          {finished && (
            <DetailSection label={isError ? "Error" : "Result"} grow>
              <pre
                className={cn(
                  "whitespace-pre-wrap break-words font-mono text-xs",
                  isError ? "text-danger" : result.isJson ? "text-foreground" : "text-foreground-muted",
                )}
              >
                {result.text}
              </pre>
              {resultTruncated && (
                <p className="mt-2 text-[11px] text-foreground-faint">
                  Truncated to 500 characters for this run&apos;s trace log.
                </p>
              )}
            </DetailSection>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailSection({
  label,
  children,
  grow = false,
}: {
  label: string;
  children: React.ReactNode;
  grow?: boolean;
}) {
  return (
    <div className={cn("flex min-h-0 flex-col gap-1.5", grow && "flex-1")}>
      <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-foreground-faint">
        {label}
      </span>
      <div
        className={cn(
          "min-h-0 overflow-y-auto rounded-md border border-border bg-surface-muted p-3 scrollbar-thin",
          grow ? "flex-1" : "max-h-[45vh]",
        )}
      >
        {children}
      </div>
    </div>
  );
}
