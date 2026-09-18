// Mirrors the Python shapes in harness/src/agentward_harness/trajectory.py
// and features/f1_care_gap_hunter/src/f1_care_gap_hunter/grading.py. Kept as
// an independent, hand-written copy rather than generated, since the surface
// is small and stable - see bundles.py/fhir_mcp's own precedent in this repo
// for independent implementations of the same small facts.

export const GAP_TYPES = [
  "diabetic_missing_hba1c",
  "diabetic_missing_eye_exam",
  "uncontrolled_bp_despite_therapy",
  "missing_colorectal_screening",
] as const;

export type GapType = (typeof GAP_TYPES)[number];

export const GAP_LABELS: Record<GapType, string> = {
  diabetic_missing_hba1c: "Missing HbA1c",
  diabetic_missing_eye_exam: "Missing eye exam",
  uncontrolled_bp_despite_therapy: "Uncontrolled BP",
  missing_colorectal_screening: "Missing colorectal screening",
};

export interface Evidence {
  reference: string;
  description: string;
}

export interface AgentFinding {
  gap_type: GapType | string;
  rationale: string;
  evidence: Evidence[];
}

export type TerminationReason = "submit" | "budget" | "malformed";

export interface PatientSummary {
  synthea_id: string;
  hapi_id: string | null;
  name: string;
  age: number | null;
  deceased: boolean;
}

export interface PatientRunOutcome {
  patient_synthea_id: string;
  patient_name?: string;
  findings: AgentFinding[];
  terminated_by: TerminationReason;
}

// One event from agentward_harness.trajectory.TrajectoryEvent, JSON-decoded.
export type EventType =
  | "run_started"
  | "llm_call_started"
  | "llm_call_finished"
  | "tool_call_started"
  | "tool_call_finished"
  | "run_finished";

export interface TrajectoryEvent {
  event_type: EventType;
  run_id: string;
  step: number | null;
  timestamp: number;
  data: Record<string, unknown>;
}

export interface RunStartedData {
  task_id: string;
  provider: string;
  model: string;
  config: Record<string, unknown>;
}

export interface LlmCallFinishedData {
  reasoning: string | null;
  content: string | null;
  tool_call_names: string[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
  duration_ms: number;
}

export interface ToolCallStartedData {
  tool_name: string;
  arguments: Record<string, unknown>;
  source: "mcp" | "local";
}

export interface ToolCallFinishedData {
  tool_name: string;
  is_error: boolean;
  result_summary: string;
  // Live SSE only - never present when replaying a persisted eval JSONL,
  // since it's stripped before that file is written (see trajectory.py's
  // _LIVE_ONLY_KEYS). Still capped (20k chars), just far more than the
  // 500-char result_summary allows.
  result_full?: string;
  duration_ms: number;
}

export interface RunFinishedData {
  findings: AgentFinding[];
  terminated_by: TerminationReason;
  total_steps: number;
  total_tokens: number;
  duration_ms: number;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_call_id?: string;
  tool_calls?: unknown[];
}
