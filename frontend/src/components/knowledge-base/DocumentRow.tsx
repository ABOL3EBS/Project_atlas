import type { Document } from "../../lib/types";
import { formatBytes, formatRelative } from "../../lib/api";
import { FileTypeIcon } from "../ui/FileTypeIcon";
import { StatusBadge } from "../ui/Badge";
import { EyeIcon, SpinnerIcon, TrashIcon } from "../ui/icons";

export function DocumentRow({
  document,
  onPreview,
  onDelete,
}: {
  document: Document;
  onPreview: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group flex items-center gap-4 border-b border-slate-200 px-4 py-3 last:border-b-0">
      <FileTypeIcon name={document.name} className="h-5 w-5" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">{document.name}</p>
        <p className="truncate text-xs text-slate-400">
          {formatBytes(document.size)} · {document.chunk_count} chunks · uploaded{" "}
          {formatRelative(document.created_at)}
        </p>
      </div>

      {document.status === "indexed" && <StatusBadge tone="emerald">Indexed</StatusBadge>}
      {document.status === "ingesting" && (
        <StatusBadge tone="amber">
          <SpinnerIcon className="h-3 w-3" />
          Processing
        </StatusBadge>
      )}
      {document.status === "failed" && (
        <StatusBadge tone="red">Failed</StatusBadge>
      )}

      <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          onClick={onPreview}
          aria-label={`Preview ${document.name}`}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        >
          <EyeIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label={`Delete ${document.name}`}
          className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}