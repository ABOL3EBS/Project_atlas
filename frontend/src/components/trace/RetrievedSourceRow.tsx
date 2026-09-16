import type { TraceSource } from "../../lib/trace";
import { FileTypeIcon } from "../ui/FileTypeIcon";
import { ChevronRightIcon } from "../ui/icons";

export function RetrievedSourceRow({
  source,
  onToggle,
  expanded,
}: {
  source: TraceSource;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="flex w-full items-center justify-between rounded-lg p-2 text-left transition-colors hover:bg-slate-50"
    >
      <span className="flex min-w-0 items-center gap-2.5">
        <FileTypeIcon name={source.documentName} className="h-4 w-4" />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-slate-800">
            {source.documentName}
          </span>
          <span className="block text-xs text-slate-400">
            {source.page != null ? `Page ${source.page}` : "Source"}
            {source.section ? ` · ${source.section}` : ""}
          </span>
        </span>
      </span>
      <ChevronRightIcon
        className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${expanded ? "rotate-90" : ""}`}
      />
    </button>
  );
}