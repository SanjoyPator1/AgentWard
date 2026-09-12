import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, Tag, Callout } from "@/components/deck/parts";
import { X, ArrowRight } from "lucide-react";

function ChipRow({ items }: { items: string[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-md border border-line bg-paper-soft px-2.5 py-1.5 text-center font-mono text-[11px] text-ink-soft"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export default function Slide06McpWhy(_props: SlideProps) {
  return (
    <SlideLayout>
      <TwoCol
        left={
          <div className="space-y-3">
            <SlideTitle eyebrow="Tool Layer" accent="N × M Becomes N + M">
              Why An MCP Server
            </SlideTitle>
            <Lede>
              Before MCP, connecting a model to a tool was a bespoke job every time — every
              application speaking to every system in its own way. MCP wraps each system once, and
              each application learns the protocol once.
            </Lede>
          </div>
        }
        right={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">
              The three roles, and who decides what runs
            </p>
            <div className="space-y-2.5">
              <div className="rounded-lg border border-line bg-paper-deep/50 p-2.5">
                <Tag tone="neutral">Host</Tag>
                <p className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">
                  The application the human uses. Owns the model, the conversation, the permission
                  gates.
                </p>
              </div>
              <div className="rounded-lg border border-line bg-paper-deep/50 p-2.5">
                <Tag tone="neutral">Client</Tag>
                <p className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">
                  A connector inside the host, one per server. Speaks MCP. Does not think.
                </p>
              </div>
              <div className="rounded-lg border border-brand/30 bg-brand-soft/50 p-2.5">
                <Tag tone="brand">Server — fhir-mcp</Tag>
                <p className="mt-1.5 text-[12.5px] leading-snug text-ink-soft">
                  Wraps one system, exposes it as tools. This is what we built. No model inside it.
                </p>
              </div>
            </div>
          </Panel>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Panel className="border-flag/25 bg-flag-soft/25">
          <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-flag-dark uppercase">Before — bespoke</p>
          <div className="flex items-center justify-between gap-3">
            <ChipRow items={["Claude Desktop", "Cursor", "Your agent"]} />
            <X className="size-4 shrink-0 text-ink-faint" />
            <ChipRow items={["FHIR server", "Postgres", "GitHub"]} />
          </div>
          <p className="mt-4 text-center font-serif text-3xl font-bold text-flag-dark">9</p>
          <p className="text-center text-[12px] text-ink-faint">separate integrations, each written again</p>
        </Panel>
        <Panel className="border-brand/25 bg-brand-soft/25">
          <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-brand-dark uppercase">After — one protocol</p>
          <div className="flex items-center justify-between gap-2">
            <ChipRow items={["Claude Desktop", "Cursor", "Your agent"]} />
            <ArrowRight className="size-4 shrink-0 text-ink-faint" />
            <span className="shrink-0 rounded-md border border-brand/40 bg-brand px-2.5 py-1.5 font-mono text-[11px] font-semibold text-paper-soft">
              MCP
            </span>
            <ArrowRight className="size-4 shrink-0 text-ink-faint" />
            <ChipRow items={["fhir-mcp", "postgres-mcp", "github-mcp"]} />
          </div>
          <p className="mt-4 text-center font-serif text-3xl font-bold text-brand-dark">6</p>
          <p className="text-center text-[12px] text-ink-faint">pieces total — every new app gets all three systems free</p>
        </Panel>
      </div>

      <Callout>
        An MCP server contains no AI. It is an ordinary program that answers structured requests —
        all the intelligence sits in the host, which decides which tool to call. Our server&apos;s job
        is to make that decision easy to get right and hard to get wrong.
      </Callout>
    </SlideLayout>
  );
}
