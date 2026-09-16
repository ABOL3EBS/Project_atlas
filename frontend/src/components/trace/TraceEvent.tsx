import type { TraceRow } from "../../lib/trace";
import { formatTime } from "../../lib/api";
import {
  AlertTriangleIcon,
  BranchIcon,
  CheckIcon,
  FileTextIcon,
  GearIcon,
  HashIcon,
  SearchIcon,
  SpinnerIcon,
  ZapIcon,
} from "../ui/icons";

function StatusIcon({ row }: { row: TraceRow }) {
  if (row.status === "error") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 text-red-600">
        <AlertTriangleIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.status === "active") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <SpinnerIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.kind === "retrieval") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <SearchIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.kind === "generation") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <BranchIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.kind === "stream") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <ZapIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.kind === "rerank") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <HashIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.kind === "citation") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <FileTextIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (row.kind === "decision" || row.kind === "tool") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <GearIcon className="h-3.5 w-3.5" />
      </span>
    );
  }
  return (
    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
      <CheckIcon className="h-3.5 w-3.5" />
    </span>
  );
}

export function TraceEvent({ row, isLast }: { row: TraceRow; isLast: boolean }) {
  return (
    <div className="relative">
      {!isLast && (
        <span
          className="absolute left-[11px] top-7 bottom-[-8px] w-px bg-slate-200"
          aria-hidden
        />
      )}
      <div className="flex gap-3 py-2">
        <StatusIcon row={row} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <p className="truncate text-sm font-medium text-slate-800">{row.title}</p>
            <span className="shrink-0 text-xs text-slate-400">{formatTime(new Date(row.timestamp).toISOString())}</span>
          </div>
          <p className="mt-0.5 truncate text-xs text-slate-500">{row.description}</p>
        </div>
      </div>
    </div>
  );
}