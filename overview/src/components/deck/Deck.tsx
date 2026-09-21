"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SLIDES } from "@/lib/slides-meta";
import type { SlideComponent } from "@/lib/slide-types";
import { TopBar, ProgressRail, NavArrows } from "@/components/deck/Chrome";
import { Sidebar } from "@/components/deck/Sidebar";

import Slide01Title from "@/components/slides/Slide01Title";
import Slide02Metaphor from "@/components/slides/Slide02Metaphor";
import Slide03Synthea from "@/components/slides/Slide03Synthea";
import Slide04Substrate from "@/components/slides/Slide04Substrate";
import Slide05RawData from "@/components/slides/Slide05RawData";
import Slide06McpWhy from "@/components/slides/Slide06McpWhy";
import Slide07Level1 from "@/components/slides/Slide07Level1";
import Slide08Level2 from "@/components/slides/Slide08Level2";
import Slide09DataJourney from "@/components/slides/Slide09DataJourney";
import Slide10Oracle from "@/components/slides/Slide10Oracle";
import Slide11Absence from "@/components/slides/Slide11Absence";
import Slide12F1 from "@/components/slides/Slide12F1";
import Slide13AgentParts from "@/components/slides/Slide13AgentParts";
import Slide14AgentLoop from "@/components/slides/Slide14AgentLoop";
import Slide15AgentGuards from "@/components/slides/Slide15AgentGuards";
import Slide16AgentAsk from "@/components/slides/Slide16AgentAsk";
import Slide17AgentTrace from "@/components/slides/Slide17AgentTrace";
import Slide18AgentAnswer from "@/components/slides/Slide18AgentAnswer";
import Slide19Status from "@/components/slides/Slide19Status";
import Slide20Explore from "@/components/slides/Slide20Explore";

const SLIDE_COMPONENTS: SlideComponent[] = [
  Slide01Title,
  Slide02Metaphor,
  Slide03Synthea,
  Slide04Substrate,
  Slide05RawData,
  Slide06McpWhy,
  Slide07Level1,
  Slide08Level2,
  Slide09DataJourney,
  Slide10Oracle,
  Slide11Absence,
  Slide12F1,
  Slide13AgentParts,
  Slide14AgentLoop,
  Slide15AgentGuards,
  Slide16AgentAsk,
  Slide17AgentTrace,
  Slide18AgentAnswer,
  Slide19Status,
  Slide20Explore,
];

function readHash(): number {
  if (typeof window === "undefined") return 0;
  const n = Number.parseInt(window.location.hash.replace("#", ""), 10);
  if (Number.isFinite(n) && n >= 1 && n <= SLIDES.length) return n - 1;
  return 0;
}

export function Deck() {
  const [current, setCurrent] = useState(0);
  const [step, setStep] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef<number | null>(null);

  useEffect(() => {
    // Reads the browser-only URL hash on mount to sync initial deep-link state;
    // a lazy useState initializer would hydration-mismatch against the SSR pass.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrent(readHash());
    const onHash = () => setCurrent(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const goTo = useCallback((index: number) => {
    const clamped = Math.max(0, Math.min(SLIDES.length - 1, index));
    setCurrent(clamped);
    setStep(0);
    window.location.hash = String(clamped + 1);
    scrollRef.current?.scrollTo({ top: 0 });
  }, []);

  const totalSteps = SLIDE_COMPONENTS[current].steps ?? 1;

  const next = useCallback(() => {
    if (step < totalSteps - 1) {
      setStep((s) => s + 1);
      return;
    }
    goTo(current + 1);
  }, [current, step, totalSteps, goTo]);

  const prev = useCallback(() => {
    if (step > 0) {
      setStep((s) => s - 1);
      return;
    }
    if (current === 0) return;
    const prevIndex = current - 1;
    const prevSteps = SLIDE_COMPONENTS[prevIndex].steps ?? 1;
    setCurrent(prevIndex);
    setStep(prevSteps - 1);
    window.location.hash = String(prevIndex + 1);
    scrollRef.current?.scrollTo({ top: 0 });
  }, [current, step]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (sidebarOpen) return;
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;

      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        prev();
      } else if (e.key === "Home") {
        goTo(0);
      } else if (e.key === "End") {
        goTo(SLIDES.length - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, goTo, sidebarOpen]);

  const onTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 60) {
      if (dx < 0) next();
      else prev();
    }
    touchStartX.current = null;
  };

  const CurrentSlide = SLIDE_COMPONENTS[current];

  return (
    <div className="paper-grain flex h-dvh w-full flex-col overflow-hidden bg-paper">
      <TopBar current={current} onMenu={() => setSidebarOpen(true)} />
      <ProgressRail current={current} step={step} totalSteps={totalSteps} />

      <div
        ref={scrollRef}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        className="scrollbar-none min-h-0 flex-1 overflow-y-auto"
      >
        <CurrentSlide step={step} onStepChange={setStep} />
      </div>

      <NavArrows
        onPrev={prev}
        onNext={next}
        disablePrev={current === 0 && step === 0}
        disableNext={current === SLIDES.length - 1 && step === totalSteps - 1}
      />

      <Sidebar open={sidebarOpen} onOpenChange={setSidebarOpen} current={current} onSelect={goTo} />
    </div>
  );
}
