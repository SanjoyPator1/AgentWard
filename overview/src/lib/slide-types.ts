import type { ComponentType } from "react";

// Every slide receives these two props uniformly from Deck.tsx, whether it
// uses them or not. A slide that wants internal steps (a viz that advances
// through stages before the deck moves to the next slide) reads `step` and
// sets a static `steps` count on its component; next()/prev() in Deck.tsx
// walk steps before changing slides. A slide with only one step ignores both.

export type SlideProps = {
  step: number;
  onStepChange: (step: number) => void;
};

export type SlideComponent = ComponentType<SlideProps> & { steps?: number };
