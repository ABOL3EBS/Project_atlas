import { formatMs } from "../../lib/api";
import { ClockIcon, HashIcon, StopwatchIcon } from "../ui/icons";

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="flex items-center gap-2 text-sm text-slate-600">
        {icon}
        {label}
      </span>
      <span className="text-sm font-medium text-slate-800">{value}</span>
    </div>
  );
}

export function PerformanceMetrics({
  totalMs,
  retrievalMs,
  generationMs,
}: {
  totalMs: number | null;
  retrievalMs: number | null;
  generationMs: number | null;
}) {
  return (
    <div className="border-t border-slate-200 pt-4">
      <p className="mb-2 text-sm font-semibold text-slate-800">Performance</p>
      <Metric
        icon={<ClockIcon className="h-4 w-4 text-slate-400" />}
        label="Total latency"
        value={totalMs != null ? formatMs(totalMs) : "—"}
      />
      <Metric
        icon={<StopwatchIcon className="h-4 w-4 text-slate-400" />}
        label="Retrieval time"
        value={retrievalMs != null ? formatMs(retrievalMs) : "—"}
      />
      <Metric
        icon={<HashIcon className="h-4 w-4 text-slate-400" />}
        label="Generation time"
        value={generationMs != null ? formatMs(generationMs) : "—"}
      />
    </div>
  );
}