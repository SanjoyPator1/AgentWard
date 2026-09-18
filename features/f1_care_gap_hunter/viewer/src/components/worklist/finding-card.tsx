import { AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GapBadge } from "@/components/gap-badge";
import type { PatientRunOutcome } from "@/lib/types";

export function FindingCard({ outcome }: { outcome: PatientRunOutcome }) {
  const hasGaps = outcome.findings.length > 0;
  const abstained = outcome.terminated_by !== "submit";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <StatusIcon hasGaps={hasGaps} abstained={abstained} />
          <span className="text-sm font-medium text-foreground">
            {outcome.patient_name ?? outcome.patient_synthea_id}
          </span>
        </div>
        {abstained && (
          <Badge tone="warning">
            {outcome.terminated_by === "budget" ? "ran out of steps" : "no answer submitted"}
          </Badge>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {hasGaps ? (
          outcome.findings.map((finding, index) => (
            <div key={index} className="flex flex-col gap-1.5 border-t border-border pt-3 first:border-0 first:pt-0">
              <div className="flex items-center gap-2">
                <GapBadge gapType={finding.gap_type} />
              </div>
              <p className="text-sm text-foreground-muted">{finding.rationale}</p>
              {finding.evidence.length > 0 && (
                <ul className="flex flex-wrap gap-1.5">
                  {finding.evidence.map((evidence, evidenceIndex) => (
                    <li key={evidenceIndex}>
                      <Badge tone="neutral" title={evidence.description}>
                        {evidence.reference}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        ) : (
          <p className="text-sm text-foreground-faint">No care gaps found.</p>
        )}
      </CardContent>
    </Card>
  );
}

function StatusIcon({ hasGaps, abstained }: { hasGaps: boolean; abstained: boolean }) {
  if (abstained) return <HelpCircle className="size-4 text-warning" />;
  if (hasGaps) return <AlertTriangle className="size-4 text-danger" />;
  return <CheckCircle2 className="size-4 text-success" />;
}
