export function Avatar({
  initials,
  tone = "slate",
  className = "",
}: {
  initials: string;
  tone?: "slate" | "violet" | "blue";
  className?: string;
}) {
  const tones = {
    slate: "bg-slate-200 text-slate-600",
    violet: "bg-violet-100 text-violet-700",
    blue: "bg-blue-600 text-white",
  };
  return (
    <span
      className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${tones[tone]} ${className}`}
      aria-hidden
    >
      {initials}
    </span>
  );
}

export function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] ?? "" : "";
  return `${first}${last}`.toUpperCase();
}