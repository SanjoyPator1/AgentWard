import { SlideLayout, TwoCol } from "@/components/deck/SlideLayout";
import type { SlideProps } from "@/lib/slide-types";
import { SlideTitle, Lede, Panel, BrowserWindow, CodeBlock, Callout, Tag } from "@/components/deck/parts";

const TOOLS: [string, string][] = [
  ["get_resource_by_id", "Read one resource when you already have its type and id"],
  ["search_resources", "Search one resource type, any FHIR params, one page at a time"],
  ["get_next_page", "Fetch the next page of a search already started, via its token"],
];

const EXAMPLE = `search_resources(
  resource_type="Condition",
  search_params={"patient": "2685", "clinical-status": "active"},
  count=2,
)

-> total_matching: 21        # true count, every page
   returned: 2                # just this page
   resources:
     - id: "2687"
       code: {text: "Risk activity involvement (finding)"}
     - id: "2693"
       code: {text: "Received higher education (finding)"}
   next_page_token: "...offset=2"`;

export default function Slide07Level1(_props: SlideProps) {
  return (
    <SlideLayout>
      <div className="flex items-center gap-3">
        <SlideTitle eyebrow="Tool Layer" accent="Thin Passthrough">
          fhir-mcp — Level 1
        </SlideTitle>
        <Tag tone="brand" >shipped</Tag>
      </div>
      <Lede>
        Generic tools that mirror the FHIR REST API almost directly. The agent has to already know
        FHIR well to use them — which is the point: this is the baseline every task-shaped and
        code-mode tool gets measured against.
      </Lede>

      <TwoCol
        left={
          <Panel className="h-full">
            <p className="mb-3 font-mono text-[11px] tracking-[0.15em] text-ink-faint uppercase">The three tools</p>
            <div className="space-y-3">
              {TOOLS.map(([name, desc]) => (
                <div key={name} className="rounded-lg border border-line bg-paper-deep/40 p-3">
                  <p className="font-mono text-[12.5px] font-semibold text-brand-dark">{name}()</p>
                  <p className="mt-1 text-[13px] leading-snug text-ink-soft">{desc}</p>
                </div>
              ))}
            </div>
          </Panel>
        }
        right={
          <BrowserWindow title="fhir-mcp · tools/call" tone="dark">
            <CodeBlock code={EXAMPLE} />
          </BrowserWindow>
        }
      />

      <Callout tone="flag" label="The cost of maximum flexibility:">
        the agent paginates by hand, joins by hand, and burns tool calls doing it — Experiment 1
        measures exactly that against Level 2 and Level 3.
      </Callout>
    </SlideLayout>
  );
}
