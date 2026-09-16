import { BrandMark } from "../ui/icons";

const EXAMPLES = [
  "What does the onboarding checklist require?",
  "List the deployment steps for a new instance.",
  "What are the access control rules?",
];

export function EmptyState({ onPickQuestion }: { onPickQuestion: (question: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6">
      <span className="mb-4 text-slate-200">
        <BrandMark className="h-14 w-14" />
      </span>
      <h2 className="text-lg font-semibold text-slate-900">Ask anything about your documents</h2>
      <p className="mt-1 max-w-sm text-center text-sm text-slate-500">
        Questions are answered from the indexed knowledge base, with sources and a live execution
        trace.
      </p>
      <div className="mt-6 flex flex-col items-center gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onPickQuestion(example)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 transition-colors hover:border-blue-300 hover:bg-blue-50/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}