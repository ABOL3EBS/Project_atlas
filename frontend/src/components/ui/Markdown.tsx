import { Fragment, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import type { Citation } from "../../lib/types";

const baseComponents: Components = {
  p: ({ children }) => <p className="mb-2">{children}</p>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  h1: Heading1,
  h2: Heading2,
  h3: Heading2,
  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
  em: ({ children }) => <em>{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-slate-200 pl-3 italic text-slate-500">
      {children}
    </blockquote>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 underline">
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-slate-100 p-3 font-mono text-[0.85em] text-slate-800">
      {children}
    </pre>
  ),
  hr: () => <hr className="my-4 border-slate-200" />,
};

// Renders `[1]`-style markers the model emits for its sources as clickable
// superscript badges that map 1:1 onto the citations shown in the Sources
// block. Markers with no matching citation are dropped so we never surface a
// dead bracket number (e.g. mid-stream, before citations are known).
function CitationText({
  children,
  citations,
  onCitationOpen,
}: {
  children?: React.ReactNode;
  citations: Citation[];
  onCitationOpen: (citation: Citation) => void;
}) {
  const raw = Array.isArray(children) ? children.join("") : String(children ?? "");
  const parts = raw.split(/(\[\d{1,2}\])/g);

  return (
    <>
      {parts.map((part, index) => {
        const marker = /^\[(\d{1,2})\]$/.exec(part);
        if (!marker) return <Fragment key={index}>{part}</Fragment>;
        const citation = citations[Number(marker[1]) - 1];
        if (!citation) return null;
        return (
          <button
            key={index}
            type="button"
            onClick={() => onCitationOpen(citation)}
            title={`Source ${marker[1]}: ${citation.document_name}`}
            aria-label={`Open source ${marker[1]}: ${citation.document_name}`}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-blue-100 px-1 align-super text-xs font-semibold leading-none text-blue-700 transition-colors hover:bg-blue-700 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-600"
          >
            {marker[1]}
          </button>
        );
      })}
    </>
  );
}

function Heading1({ children }: { children?: React.ReactNode }) {
  return <div className="mb-1 mt-3 text-base font-semibold text-slate-900">{children}</div>;
}

function Heading2({ children }: { children?: React.ReactNode }) {
  return <div className="mb-1 mt-3 text-sm font-semibold text-slate-900">{children}</div>;
}

export function Markdown({
  content,
  citations,
  onCitationOpen,
}: {
  content: string;
  citations?: Citation[];
  onCitationOpen?: (citation: Citation) => void;
}) {
  const components = useMemo<Components>(() => {
    if (!citations || !onCitationOpen) return baseComponents;
    return {
      ...baseComponents,
      text: ({ children }) => (
        <CitationText citations={citations} onCitationOpen={onCitationOpen}>
          {children}
        </CitationText>
      ),
    };
  }, [citations, onCitationOpen]);

  return (
    <div className="text-sm leading-relaxed text-slate-800">
      <ReactMarkdown components={components}>{content}</ReactMarkdown>
    </div>
  );
}