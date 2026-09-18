"use client";

import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface RunControlsProps {
  limit: number;
  onLimitChange: (limit: number) => void;
  provider: "ollama" | "gemini" | "groq";
  onProviderChange: (provider: "ollama" | "gemini" | "groq") => void;
  running: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function RunControls({
  limit,
  onLimitChange,
  provider,
  onProviderChange,
  running,
  onStart,
  onStop,
}: RunControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-sm text-foreground-muted">
        Patients
        <Input
          type="number"
          min={1}
          max={217}
          value={limit}
          disabled={running}
          onChange={(e) => onLimitChange(Number(e.target.value) || 1)}
          className="w-20"
        />
      </label>

      <label className="flex items-center gap-2 text-sm text-foreground-muted">
        Model
        <select
          value={provider}
          disabled={running}
          onChange={(e) => onProviderChange(e.target.value as "ollama" | "gemini" | "groq")}
          className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
        >
          <option value="ollama">Ollama (qwen3:8b)</option>
          <option value="gemini">Gemini</option>
          <option value="groq">Groq (gpt-oss-120b)</option>
        </select>
      </label>

      {running ? (
        <Button variant="secondary" onClick={onStop}>
          <Square className="size-3.5" /> Stop
        </Button>
      ) : (
        <Button onClick={onStart}>
          <Play className="size-3.5" /> Run
        </Button>
      )}

      <p className="text-xs text-foreground-faint">
        A full 217-patient run on a local model can take hours &mdash; start small.
      </p>
    </div>
  );
}
