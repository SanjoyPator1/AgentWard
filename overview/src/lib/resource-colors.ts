// A muted "earth tone" ramp for FHIR resource types, used wherever a slide
// shows a mixed bundle of resources as dots. Deliberately not
// d3.schemeCategory10 — those saturated primaries would read as generic;
// this stays inside the deck's own quiet palette. Administrative resource
// types (claims, billing, provenance) share one neutral colour so the
// legend stays under Miller's-law-ish limits instead of listing all 16
// FHIR types the bundle actually contains.

export const RESOURCE_COLORS: Record<string, string> = {
  Observation: "oklch(0.6 0.08 200)",
  Procedure: "oklch(0.6 0.09 150)",
  Immunization: "oklch(0.63 0.09 100)",
  DiagnosticReport: "oklch(0.6 0.1 260)",
  Encounter: "oklch(0.58 0.08 280)",
  DocumentReference: "oklch(0.62 0.08 325)",
  Condition: "oklch(0.58 0.14 45)", // same clay as F1's "flag" — this is what gets isolated
  MedicationRequest: "oklch(0.62 0.1 65)",
};

export const RESOURCE_TYPE_ORDER = Object.keys(RESOURCE_COLORS);

export const OTHER_RESOURCE_COLOR = "oklch(0.68 0.012 235)";

export function colorForResourceType(resourceType: string): string {
  return RESOURCE_COLORS[resourceType] ?? OTHER_RESOURCE_COLOR;
}
