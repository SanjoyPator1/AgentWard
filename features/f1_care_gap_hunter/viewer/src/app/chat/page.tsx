"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Nav } from "@/components/nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PatientSelector } from "@/components/chat/patient-selector";
import { MessageBubble, type ChatTurnDisplay } from "@/components/chat/message-bubble";
import { streamSSE } from "@/lib/api";
import type { ChatMessage, PatientSummary, TrajectoryEvent } from "@/lib/types";

const EXAMPLE_PROMPTS = [
  "What are the care gaps for this patient?",
  "Top 5 diabetics with a care gap",
  "Which patients are overdue for colorectal screening?",
];

export default function ChatPage() {
  const [turns, setTurns] = useState<ChatTurnDisplay[]>([]);
  const [apiMessages, setApiMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<PatientSummary | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(rawText: string) {
    const text = rawText.trim();
    if (!text || sending) return;

    // selectedPatient.hapi_id can only be null for a patient the backend's
    // id map hasn't resolved yet (see viewer_api.py's startup hook, which
    // builds it eagerly for exactly this reason) - never fall back to
    // synthea_id here. That id means nothing to the agent or to HAPI, and
    // sending it produces a confusing failure several layers downstream
    // instead of a clear one here.
    if (selectedPatient && !selectedPatient.hapi_id) {
      setError(`${selectedPatient.name}'s server id hasn't resolved yet - try again shortly.`);
      return;
    }

    const messageForAgent = selectedPatient
      ? `Regarding patient ${selectedPatient.hapi_id} (${selectedPatient.name}): ${text}`
      : text;

    setTurns((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", trace: [], pending: true },
    ]);
    setInput("");
    setSending(true);
    setError(null);

    const trace: TrajectoryEvent[] = [];

    try {
      await streamSSE(
        "/chat",
        { messages: apiMessages, message: messageForAgent },
        (eventType, data) => {
          if (eventType === "chat_reply") {
            const parsed = JSON.parse(data) as { reply: string; messages: ChatMessage[] };
            setApiMessages(parsed.messages);
            setTurns((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                role: "assistant",
                content: parsed.reply || "(no reply)",
                trace,
                pending: false,
              };
              return next;
            });
            return;
          }
          if (eventType === "error") {
            // Without this, a backend failure left the pending bubble
            // spinning forever with nothing visible - confirmed live.
            const parsed = JSON.parse(data) as { message: string };
            setTurns((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                role: "assistant",
                content: `Something went wrong: ${parsed.message}`,
                trace,
                pending: false,
                isError: true,
              };
              return next;
            });
            return;
          }
          trace.push(JSON.parse(data) as TrajectoryEvent);
          setTurns((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], trace: [...trace] };
            return next;
          });
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "The chat request failed.");
      setTurns((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full min-h-full flex-col">
      <Nav />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6">
        <div className="mb-4 flex flex-col gap-2">
          <h1 className="text-xl font-semibold text-foreground">Chat</h1>
          <PatientSelector selected={selectedPatient} onSelect={setSelectedPatient} />
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {turns.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <p className="text-sm text-foreground-faint">
                Ask about one patient or the whole cohort.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => send(prompt)}
                    className="rounded-full border border-border px-3 py-1.5 text-xs text-foreground-muted hover:bg-surface-muted"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4 pb-4">
              {turns.map((turn, index) => (
                <MessageBubble key={index} turn={turn} />
              ))}
            </div>
          )}
        </div>

        {error && <p className="mb-2 text-sm text-danger">{error}</p>}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex items-center gap-2 border-t border-border pt-3"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a patient or the cohort..."
            disabled={sending}
          />
          <Button type="submit" disabled={sending || !input.trim()}>
            <Send className="size-3.5" />
          </Button>
        </form>
      </main>
    </div>
  );
}
