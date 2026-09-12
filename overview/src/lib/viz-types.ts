// Shape of the committed JSON snapshots in src/data/, produced by
// overview/scripts/build_viz_data.py. Keep in sync with that script.

export type GapFinding = {
  patient_synthea_id: string;
  patient_name: string;
  gap_type: string;
  rationale: string;
  evidence: { reference: string; description: string }[];
};

export type CohortPatient = {
  id: string;
  name: string;
  age: number | null;
  sex: string;
  deceased: boolean;
  gaps: GapFinding[];
};

export type CohortSummary = {
  asOf: string;
  totalPatients: number;
  alivePatients: number;
  deceasedPatients: number;
  totalFindings: number;
  flaggedPatients: number;
  gapTypeCounts: Record<string, number>;
  patientsByGapCount: Record<string, number>;
};

export type CohortData = {
  summary: CohortSummary;
  patients: CohortPatient[];
};

export type BundleResource = {
  resourceType: string;
  id: string;
  label: string;
  date: string | null;
};

export type ConditionRow = {
  id: string;
  text: string;
  tag: string | null;
  isRealProblem: boolean;
  onsetDate: string | null;
};

export type ConditionBreakdown = {
  totalAllConditions: number;
  totalActive: number;
  totalRealProblems: number;
  conditions: ConditionRow[];
};

export type BundleProfile = {
  patientFile: string;
  patientName: string;
  totalResources: number;
  resourceCounts: Record<string, number>;
  resources: BundleResource[];
  conditionBreakdown: ConditionBreakdown;
};
