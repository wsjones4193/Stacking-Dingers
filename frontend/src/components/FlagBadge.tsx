/**
 * Renders a small colored badge for a roster flag type.
 */
import { cn, flagColor, flagLabel } from "@/lib/utils";
import type { RosterFlag } from "@/types/api";

interface FlagBadgeProps {
  flag: RosterFlag;
  className?: string;
}

export default function FlagBadge({ flag, className }: FlagBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium",
        flagColor(flag.flag_type),
        className
      )}
      title={flag.flag_reason}
    >
      {flagLabel(flag.flag_type)}
    </span>
  );
}
