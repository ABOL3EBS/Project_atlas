import type { Citation } from "../../lib/types";
import type { ChatMessage } from "../../context/ChatContext";
import { formatTime } from "../../lib/api";
import {
  AlertTriangleIcon,
  BranchIcon,
  DocumentStackIcon,
} from "../ui/icons";
import { Markdown } from "../ui/Markdown";
import { SourceChip } from "./SourceChip";

export function AssistantMessage({
  message,
  onOpenSource,
  onInspectTrace,
  traceSelected,
}: {
  message: ChatMessage;
  onOpenSource: (citation: Citation) => void;
  onInspectTrace: () => void;
  traceSelected: boolean;
}) {
  const { content, citations, rejected, streaming, events } = message;

  return (
    <div
      className={`group flex gap-3 ${traceSelected ? "rounded-xl bg-blue-50/50 p-3" : ""}`}
    >
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600">
        <span className="flex h-5 w-5 items-center justify-center rounded-md bg-blue-600 text-white">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden>
            <path d="M12 2.5 20 7v10l-8 4.5L4 17V7l8-4.5Z" />
            <path d="M9 8.5h6M9 11h6M9 13.5h4" stroke="white" strokeWidth={1.6} strokeLinecap="round" opacity={0.9} />
          </svg>
        </span>
      </span>

      <div className="min-w-0 flex-1">
        {rejected && (
          <div className="mb-2 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertTriangleIcon className="h-4 w-4 shrink-0" />
            <span>Couldn't find a confident answer in the knowledge base.</span>
          </div>
        )}

        <div className="text-sm leading-relaxed text-slate-800">
          {content ? (
            <Markdown
              content={content}
              citations={citations}
              onCitationOpen={onOpenSource}
            />
          ) : (
            !streaming && (
              <p className="italic text-slate-400">No response was produced.</p>
            )
          )}
          {streaming && (
            <span
              className="caret ml-0.5 inline-block h-4 w-[2px] animate-pulse rounded-full bg-blue-600 align-text-bottom"
              aria-label="Typing"
            />
          )}
        </div>

        {citations.length > 0 && (
          <div className="mt-3">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <DocumentStackIcon className="h-3.5 w-3.5" /> Sources
            </p>
            <div className="flex flex-wrap gap-2">
              {citations.map((citation) => (
                <SourceChip key={citation.chunk_id ?? citation.document_id} citation={citation} onOpen={onOpenSource} />
              ))}
            </div>
          </div>
        )}

        <div className="mt-1.5 flex items-center gap-3">
          <p className="text-xs text-slate-400">{formatTime(message.created_at)}</p>
          {events.length > 0 && (
            <button
              type="button"
              onClick={onInspectTrace}
              aria-label={streaming ? "View trace" : traceSelected ? "Trace open" : "Inspect trace"}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-xs font-medium underline-offset-4 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
                traceSelected
                  ? "bg-blue-50 text-blue-700 underline decoration-blue-300"
                  : "text-slate-500 opacity-0 group-hover:opacity-100 hover:bg-blue-50 hover:text-blue-700 hover:underline hover:decoration-blue-300"
              }`}
            >
              <BranchIcon className="h-3.5 w-3.5" />
              {streaming ? "View trace" : traceSelected ? "Trace open" : "Inspect trace"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}