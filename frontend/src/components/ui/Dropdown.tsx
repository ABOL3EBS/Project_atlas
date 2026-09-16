import { useEffect, useRef, useState, type ReactNode } from "react";

interface DropdownProps {
  trigger: ReactNode;
  label: string;
  children: ReactNode;
  align?: "left" | "right";
  menuClassName?: string;
}

export function Dropdown({
  trigger,
  label,
  children,
  align = "left",
  menuClassName = "",
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <div
        role="button"
        tabIndex={0}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen((value) => !value);
          }
        }}
        onClick={() => setOpen((value) => !value)}
      >
        {trigger}
      </div>
      {open && (
        <div
          role="menu"
          className={`absolute z-40 mt-1 min-w-[220px] max-w-[min(28rem,calc(100vw-2rem))] rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm ${
            align === "right" ? "right-0" : "left-0"
          } ${menuClassName}`}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function DropdownItem({
  onSelect,
  children,
  active = false,
  disabled = false,
}: {
  onSelect: () => void;
  children: ReactNode;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onSelect}
      className={`block w-full rounded-lg px-3 py-2 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-blue-600 ${
        active ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-100"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      {children}
    </button>
  );
}