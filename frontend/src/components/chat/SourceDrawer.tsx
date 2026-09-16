import { useEffect, useState } from "react";
import { useApp } from "../../context/AppContext";
import { getDocumentChunks } from "../../lib/client";
import type { Citation, DocumentChunk } from "../../lib/types";
import { FileTypeIcon } from "../ui/FileTypeIcon";
import { CloseIcon, SpinnerIcon } from "../ui/icons";

export function SourceDrawer({
  citation,
  onClose,
}: {
  citation: Citation;
  onClose: () => void;
}) {
  const { knowledgeBase } = useApp();
  const [chunks, setChunks] = useState<DocumentChunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setChunks(null);
    setError(null);
    getDocumentChunks(knowledgeBase, citation.document_id)
      .then((result) => {
        if (!cancelled) setChunks(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Failed to load source text.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [knowledgeBase, citation.document_id]);

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={citation.document_name}>
      <div className="absolute inset-0 bg-slate-900/20" onClick={onClose} aria-hidden />
      <div className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-sm">
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-5">
          <div className="flex min-w-0 items-center gap-3">
            <FileTypeIcon name={citation.document_name} className="h-5 w-5" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800">
                {citation.document_name}
              </p>
              <p className="text-xs text-slate-400">
                {citation.page != null ? `Page ${citation.page}` : "Source"}
                {citation.section ? ` · ${citation.section}` : ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close source preview"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && <p className="text-sm text-red-600">{error}</p>}
          {chunks === null && !error && (
            <p className="flex items-center gap-2 text-sm text-slate-500">
              <SpinnerIcon className="h-4 w-4" /> Loading source text…
            </p>
          )}
          {chunks && chunks.length === 0 && (
            <p className="text-sm text-slate-500">No indexed chunks found for this document.</p>
          )}
          <div className="space-y-4">
            {chunks?.map((chunk) => (
              <div key={chunk.chunk_id} className="rounded-xl border border-slate-200 p-4">
                <p className="mb-1 text-xs text-slate-400">
                  {chunk.document_name} · Page {chunk.page ?? "—"}
                  {chunk.section ? ` · ${chunk.section}` : ""}
                </p>
                <blockquote className="whitespace-pre-wrap border-l-2 border-slate-200 pl-3 font-mono text-[13px] leading-relaxed text-slate-700">
                  {chunk.text}
                </blockquote>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}