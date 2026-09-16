import { formatTime } from "../../lib/api";
import { UserIcon } from "../ui/icons";

export function UserMessage({ content, created_at }: { content: string; created_at: string }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
        <UserIcon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <div className="rounded-2xl rounded-tl-sm bg-blue-50 px-4 py-3 text-sm text-slate-800">
          {content}
        </div>
        <p className="mt-1 text-xs text-slate-400">{formatTime(created_at)}</p>
      </div>
    </div>
  );
}