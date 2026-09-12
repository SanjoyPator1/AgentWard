// The four F1 gap checks, ordered by how common they are in this cohort
// (matches gapTypeCounts' order in cohort.json). One shared place for the
// label/colour every gap-type visualization needs, so they never drift.

export const GAP_TYPES = [
  "missing_colorectal_screening",
  "uncontrolled_bp_despite_therapy",
  "diabetic_missing_eye_exam",
  "diabetic_missing_hba1c",
] as const;

export type GapType = (typeof GAP_TYPES)[number];

export const GAP_LABELS: Record<GapType, string> = {
  missing_colorectal_screening: "Colorectal Screening",
  uncontrolled_bp_despite_therapy: "Uncontrolled BP",
  diabetic_missing_eye_exam: "Diabetic Eye Exam",
  diabetic_missing_hba1c: "HbA1c",
};

// A warm ramp within the deck's existing "flag" family (clay/rust/amber) —
// every flagged dot reads as "part of the same warning", distinguishable by
// hue rather than by switching to an unrelated colour family.
export const GAP_COLORS: Record<GapType, string> = {
  missing_colorectal_screening: "oklch(0.58 0.14 45)",
  uncontrolled_bp_despite_therapy: "oklch(0.56 0.15 25)",
  diabetic_missing_eye_exam: "oklch(0.62 0.13 70)",
  diabetic_missing_hba1c: "oklch(0.52 0.12 15)",
};

// Cool, low-contrast — for any patient with no gap. Never used for a gap.
export const NEUTRAL_COLOR = "oklch(0.7 0.012 235)";

export function colorForGapType(gapType: string): string {
  return GAP_COLORS[gapType as GapType] ?? NEUTRAL_COLOR;
}

export function labelForGapType(gapType: string): string {
  return GAP_LABELS[gapType as GapType] ?? gapType;
}
