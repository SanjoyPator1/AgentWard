import { Badge } from "@/components/ui/badge";
import { GAP_LABELS, type GapType } from "@/lib/types";

export function GapBadge({ gapType }: { gapType: GapType | string }) {
  const label = GAP_LABELS[gapType as GapType] ?? gapType;
  return <Badge tone="danger">{label}</Badge>;
}
