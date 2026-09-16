import type { Citation } from "../../lib/types";
import { FileTypeIcon } from "../ui/FileTypeIcon";

export function SourceChip({
  citation,
  onOpen,
}: {
  citation: Citation;
  onOpen: (citation: Citation) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-3 py-2 transition-colors hover:border-blue-300 hover:bg-blue-50/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
    >
      <FileTypeIcon name={citation.document_name} className="h-5 w-5" />
      <span className="flex flex-col items-start text-left">
        <span className="text-sm font-medium text-slate-800">{citation.document_name}</span>
        <span className="text-xs text-slate-400">
          {citation.page != null ? `Page ${citation.page}` : "Source"}
          {citation.section ? ` · ${citation.section}` : ""}
        </span>
      </span>
    </button>
  );
}