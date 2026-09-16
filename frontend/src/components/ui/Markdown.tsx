import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";

const components: Components = {
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

function Heading1({ children }: { children?: React.ReactNode }) {
  return <div className="mb-1 mt-3 text-base font-semibold text-slate-900">{children}</div>;
}

function Heading2({ children }: { children?: React.ReactNode }) {
  return <div className="mb-1 mt-3 text-sm font-semibold text-slate-900">{children}</div>;
}

export function Markdown({ content }: { content: string }) {
  return (
    <div className="text-sm leading-relaxed text-slate-800">
      <ReactMarkdown components={components}>{content}</ReactMarkdown>
    </div>
  );
}