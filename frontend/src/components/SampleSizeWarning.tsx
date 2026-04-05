/**
 * Displays a caution banner when a DataResponse has low_confidence = true.
 */
import { AlertTriangle } from "lucide-react";

interface Props {
  sampleSize: number;
  show: boolean;
}

export default function SampleSizeWarning({ sampleSize, show }: Props) {
  if (!show) return null;
  return (
    <div className="mb-4 flex items-center gap-2 rounded-md border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs text-yellow-400">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span>Low confidence — only {sampleSize} sample{sampleSize !== 1 ? "s" : ""}. Interpret with caution.</span>
    </div>
  );
}
