"use client";

import { useRef, useState } from "react";
import { Nav } from "@/components/nav";
import { RunControls } from "@/components/worklist/run-controls";
import { FindingCard } from "@/components/worklist/finding-card";
import { TraceLog } from "@/components/trace-log";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { streamSSE } from "@/lib/api";
import type { PatientRunOutcome, TrajectoryEvent } from "@/lib/types";

export default function WorklistPage() {
  const [limit, setLimit] = useState(10);
  const [provider, setProvider] = useState<"ollama" | "gemini" | "groq">("ollama");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<TrajectoryEvent[]>([]);
  const [outcomes, setOutcomes] = useState<PatientRunOutcome[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const flaggedCount = outcomes.filter((o) => o.findings.length > 0).length;

  async function handleStart() {
    setOutcomes([]);
    setEvents([]);
    setError(null);
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamSSE(
        "/runs",
        { limit, provider },
        (eventType, data) => {
          if (eventType === "patient_done") {
            setOutcomes((prev) => [...prev, JSON.parse(data) as PatientRunOutcome]);
            return;
          }
          if (eventType === "run_complete") {
            return;
          }
          if (eventType === "error") {
            const parsed = JSON.parse(data) as { message: string };
            setError(parsed.message);
            return;
          }
          setEvents((prev) => [...prev, JSON.parse(data) as TrajectoryEvent]);
        },
        controller.signal,
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : "The run failed unexpectedly.");
      }
    } finally {
      setRunning(false);
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setRunning(false);
  }

  return (
    <div className="min-h-full">
      <Nav />
      <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Worklist</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Runs the agent live against each patient &mdash; not the eval pipeline&apos;s
            checkpointed batch, an on-demand run for exploring what it finds.
          </p>
        </div>

        <Card>
          <CardContent className="pt-4">
            <RunControls
              limit={limit}
              onLimitChange={setLimit}
              provider={provider}
              onProviderChange={setProvider}
              running={running}
              onStart={handleStart}
              onStop={handleStop}
            />
          </CardContent>
        </Card>

        {error && (
          <Card className="border-danger/40 bg-danger-soft">
            <CardContent className="pt-4 text-sm text-danger">{error}</CardContent>
          </Card>
        )}

        {(running || outcomes.length > 0) && (
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-foreground-muted">
                  {outcomes.length} of {limit} patients checked
                  {outcomes.length > 0 && ` · ${flaggedCount} flagged`}
                </h2>
              </div>
              {outcomes.length === 0 ? (
                <p className="py-8 text-center text-sm text-foreground-faint">
                  Waiting for the first result&hellip;
                </p>
              ) : (
                outcomes
                  .slice()
                  .sort((a, b) => b.findings.length - a.findings.length)
                  .map((outcome) => (
                    <FindingCard key={outcome.patient_synthea_id} outcome={outcome} />
                  ))
              )}
            </div>

            <Card className="h-fit lg:sticky lg:top-20">
              <CardHeader>
                <CardTitle>Live trace</CardTitle>
              </CardHeader>
              <CardContent className="max-h-[70vh] overflow-y-auto scrollbar-thin">
                <TraceLog events={events} />
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
