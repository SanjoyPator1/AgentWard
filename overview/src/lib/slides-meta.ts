export type SlideMeta = {
  id: string;
  section: string;
  title: string;
};

// The single source of truth for slide order, ids, and sidebar labels.
// Deck.tsx maps each entry here to a component by index.
export const SLIDES: SlideMeta[] = [
  { id: "title", section: "Start", title: "AgentWard" },
  { id: "metaphor", section: "The Idea", title: "The Ward Metaphor" },
  { id: "synthea", section: "The Data", title: "Why Synthetic Patients" },
  { id: "substrate", section: "Architecture", title: "The Substrate Pipeline" },
  { id: "raw-data", section: "The Data", title: "What Synthea Actually Outputs" },
  { id: "mcp-why", section: "Tool Layer", title: "Why an MCP Server" },
  { id: "level1", section: "Tool Layer", title: "fhir-mcp — Level 1 Tools" },
  { id: "level2", section: "Tool Layer", title: "fhir-mcp — Level 2 Tools" },
  { id: "data-journey", section: "The Data", title: "One Fact, Four Transformations" },
  { id: "oracle", section: "Evaluation", title: "Truth by Construction" },
  { id: "absence", section: "Evaluation", title: "Absence Is the Evidence" },
  { id: "f1", section: "The Agent", title: "F1, The Care Gap Hunter" },
  { id: "agent-parts", section: "The Agent", title: "What An Agent Actually Is" },
  { id: "agent-loop", section: "The Agent", title: "The Loop" },
  { id: "agent-guards", section: "The Agent", title: "What Stops It Running Forever" },
  { id: "agent-ask", section: "The Agent", title: "One Patient, Or All Of Them" },
  { id: "agent-trace", section: "The Agent", title: "A Real Run, Casting A Wide Net" },
  { id: "agent-answer", section: "The Agent", title: "A Real Run, The Answer" },
  { id: "status", section: "Wrap-up", title: "Where We Stand" },
  { id: "explore", section: "Bonus", title: "Explore The Cohort" },
];
