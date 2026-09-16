import type { ReactNode } from "react";

export function Header({ title, subtitle, right }: { title: string; subtitle: string; right?: ReactNode }) {
  return (
    <header className="flex h-[72px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6 lg:px-8">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-semibold text-slate-900">{title}</h1>
        <p className="truncate text-sm text-slate-500">{subtitle}</p>
      </div>
      {right ? <div className="flex shrink-0 items-center gap-3">{right}</div> : null}
    </header>
  );
}