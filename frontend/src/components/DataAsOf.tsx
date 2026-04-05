/**
 * Renders a small "Data through [date]" footer label.
 */
import { formatDate } from "@/lib/utils";

interface Props {
  dataAsOf: string | null | undefined;
}

export default function DataAsOf({ dataAsOf }: Props) {
  if (!dataAsOf) return null;
  return (
    <p className="mt-1 text-xs text-muted-foreground">
      Data through {formatDate(dataAsOf)}
    </p>
  );
}
