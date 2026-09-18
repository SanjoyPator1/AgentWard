"use client";

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { fetchPatients } from "@/lib/api";
import type { PatientSummary } from "@/lib/types";

interface PatientSelectorProps {
  selected: PatientSummary | null;
  onSelect: (patient: PatientSummary | null) => void;
}

/**
 * Optional context for a chat turn - picking a patient here just prefixes
 * the next message with their id, it does not change which tools the chat
 * agent has (it can always look up any patient). Purely a convenience so
 * you don't have to remember or type a bare patient id.
 */
export function PatientSelector({ selected, onSelect }: PatientSelectorProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSummary[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handle = setTimeout(() => {
      fetchPatients(query).then(setResults).catch(() => setResults([]));
    }, 200);
    return () => clearTimeout(handle);
  }, [query, open]);

  if (selected) {
    return (
      <div className="flex items-center gap-2">
        <Badge tone="primary">{selected.name}</Badge>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="text-foreground-faint hover:text-foreground"
          aria-label="Clear selected patient"
        >
          <X className="size-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-foreground-faint" />
        <Input
          placeholder="Optional: pick a patient to focus on"
          value={query}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-8"
        />
      </div>
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-border bg-surface shadow-md">
          {results.map((patient) => (
            <li key={patient.synthea_id}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface-muted"
                onClick={() => {
                  onSelect(patient);
                  setOpen(false);
                  setQuery("");
                }}
              >
                <span className="text-foreground">{patient.name}</span>
                <span className="text-xs text-foreground-faint">
                  {patient.age != null ? `${patient.age}y` : "age unknown"}
                  {patient.deceased ? " · deceased" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
