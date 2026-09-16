import { useEffect, useMemo, useState } from "react";
import { useApp } from "../../context/AppContext";
import { useChat } from "../../context/ChatContext";
import { getDocumentChunks } from "../../lib/client";
import { buildTraceView, type TraceSource } from "../../lib/trace";
import type { DocumentChunk } from "../../lib/types";
import { CloseIcon, SpinnerIcon } from "../ui/icons";
import { PerformanceMetrics } from "./PerformanceMetrics";
import { RetrievedSourceRow } from "./RetrievedSourceRow";
import { TraceEvent } from "./TraceEvent";

export function TracePanel({ className = "" }: { className?: string }) {
  const { messages, traceMessageKey, setTraceOpen } = useChat();
  const { knowledgeBase } = useApp();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const target = useMemo(() => {
    if (!traceMessageKey) return null;
    return messages.find((message) => message.key === traceMessageKey) ?? null;
  }, [messages, traceMessageKey]);

  const question = useMemo(() => {
    if (!target) return null;
    const index = messages.indexOf(target);
    let i = index - 1;
    while (i >= 0) {
      if (messages[i].role === "user") return messages[i].content;
      i -= 1;
    }
    return null;
  }, [messages, target]);

  const view = useMemo(
    () => (target ? buildTraceView(target, target.trace ?? { events: [] }) : null),
    [target],
  );

  useEffect(() => {
    setExpandedKey(null);
  }, [traceMessageKey]);

  return (
    <section className={`flex h-full flex-col border-l border-slate-200 bg-white ${className}`} aria-label="Execution trace">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-5">
        <h2 className="text-base font-semibold text-slate-900">Execution Trace</h2>
        <button
          type="button"
          onClick={() => setTraceOpen(false)}
          aria-label="Close trace panel"
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        >
          <CloseIcon className="h-5 w-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {!target && (
          <p className="text-sm text-slate-500">
            Select an assistant turn or send a message to inspect its execution trace.
          </p>
        )}
        {target && view && (
          <>
            {question && (
              <div className="mb-3 rounded-lg bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Turn</p>
                <p className="mt-1 line-clamp-2 text-sm text-slate-700">{question}</p>
              </div>
            )}

            {view.rows.length === 0 ? (
              <p className="text-sm text-slate-500">No trace recorded for this turn.</p>
            ) : (
              <div>
                {view.rows.map((row, index) => (
                  <TraceEvent key={row.id} row={row} isLast={index === view.rows.length - 1} />
                ))}
              </div>
            )}

            {view.sources.length > 0 && (
              <div className="mt-4 border-t border-slate-200 pt-4">
                <p className="mb-2 text-sm font-semibold text-slate-800">
                  Retrieved Sources ({view.sources.length})
                </p>
                {view.sources.map((source, index) => {
                  const key = `${source.documentId}-${source.page}-${index}`;
                  const expanded = expandedKey === key;
                  return (
                    <div key={key} className={expanded ? "rounded-xl border border-slate-200" : ""}>
                      <RetrievedSourceRow
                        source={source}
                        expanded={expanded}
                        onToggle={() => setExpandedKey(expanded ? null : key)}
                      />
                      {expanded && (
                        <div className="px-2 pb-2">
                          <ChunkPreview source={source} knowledgeBase={knowledgeBase} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            <PerformanceMetrics
              totalMs={view.performance.totalMs}
              retrievalMs={view.performance.retrievalMs}
              generationMs={view.performance.generationMs}
            />
          </>
        )}
      </div>
    </section>
  );
}

function ChunkPreview({
  source,
  knowledgeBase,
}: {
  source: TraceSource;
  knowledgeBase: string;
}) {
  const [chunks, setChunks] = useState<DocumentChunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!source.documentId) {
      setError("Chunk text is not exposed in the trace; open the source document in chat.");
      return;
    }
    setChunks(null);
    setError(null);
    getDocumentChunks(knowledgeBase, source.documentId)
      .then((result) => {
        if (!cancelled) setChunks(result);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load chunk text.");
      });
    return () => {
      cancelled = true;
    };
  }, [knowledgeBase, source.documentId]);

  if (error) return <p className="px-2 pb-2 text-xs text-slate-500">{error}</p>;
  if (chunks === null) {
    return (
      <p className="flex items-center gap-2 px-2 pb-2 text-xs text-slate-500">
        <SpinnerIcon className="h-3.5 w-3.5" /> Loading…
      </p>
    );
  }
  if (chunks.length === 0) {
    return <p className="px-2 pb-2 text-xs text-slate-500">No indexed chunks for this document.</p>;
  }
  return (
    <div className="space-y-2 px-2 pb-2">
      {chunks.map((chunk) => (
        <blockquote
          key={chunk.chunk_id}
          className="whitespace-pre-wrap border-l-2 border-slate-200 pl-2 font-mono text-xs leading-relaxed text-slate-600"
        >
          {chunk.text.length > 400 ? `${chunk.text.slice(0, 400)}…` : chunk.text}
        </blockquote>
      ))}
    </div>
  );
}