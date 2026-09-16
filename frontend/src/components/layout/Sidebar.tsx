import { NavLink, useNavigate } from "react-router-dom";
import { useApp } from "../../context/AppContext";
import { useChat } from "../../context/ChatContext";
import {
  Avatar,
  initialsFor,
} from "../ui/Avatar";
import { Dropdown, DropdownItem } from "../ui/Dropdown";
import {
  BranchIcon,
  ChatIcon,
  ChevronDownIcon,
  DocumentMultiIcon,
  DocumentStackIcon,
  GearIcon,
  PlusIcon,
} from "../ui/icons";

const NAV = [
  { to: "/chat", label: "Chat", icon: ChatIcon },
  { to: "/knowledge-base", label: "Knowledge Base", icon: DocumentStackIcon },
  { to: "/settings", label: "Settings", icon: GearIcon },
];

export function Sidebar() {
  const { knowledgeBases, knowledgeBase, setKnowledgeBase } = useApp();
  const { traceOpen, setTraceOpen } = useChat();
  const navigate = useNavigate();

  const selected = knowledgeBases.find((kb) => kb.id === knowledgeBase);

  const switchTo = (id: string) => {
    setKnowledgeBase(id);
  };

  return (
    <aside className="flex h-full w-16 shrink-0 flex-col border-r border-slate-200 bg-white md:w-60">
      <div className="flex h-16 items-center justify-center gap-2 border-b border-slate-200 px-5 md:justify-start">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-blue-600">
          <img src="/logo.png" alt="Atlas logo" className="h-9 w-9 object-cover" />
        </span>
        <span className="hidden text-lg font-semibold text-slate-900 md:block">Atlas</span>
      </div>

      <nav className="flex flex-col gap-1 px-3 py-4" aria-label="Primary">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            <Icon className="h-4.5 w-4.5 shrink-0" />
            <span className="hidden md:block">{label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => {
            navigate("/chat");
            setTraceOpen(!traceOpen);
          }}
          className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            traceOpen ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          <BranchIcon className="h-4.5 w-4.5 shrink-0" />
          <span className="hidden md:block">Trace</span>
        </button>
      </nav>

      <div className="mx-3 border-t border-slate-200 pt-4">
        <p className="mb-2 hidden px-2 text-xs font-semibold uppercase tracking-wide text-slate-400 md:block">
          Knowledge Base
        </p>
        <Dropdown
          label="Switch knowledge base"
          trigger={
            <div className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 p-2 transition-colors hover:bg-slate-50 md:p-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                <DocumentMultiIcon className="h-4 w-4" />
              </span>
              <div className="hidden min-w-0 flex-1 md:block">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-slate-800">
                    {selected?.id ?? knowledgeBase}
                  </p>
                  <ChevronDownIcon className="h-4 w-4 shrink-0 text-slate-400" />
                </div>
                <p className="truncate text-xs text-slate-400">
                  {selected
                    ? `${selected.document_count} docs · ${selected.chunk_count} chunks`
                    : "Unknown collection"}
                </p>
              </div>
            </div>
          }
        >
          {knowledgeBases.map((kb) => (
            <DropdownItem
              key={kb.id}
              active={kb.id === knowledgeBase}
              onSelect={() => switchTo(kb.id)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{kb.id}</span>
                <span className="shrink-0 text-xs text-slate-400">
                  {kb.document_count} docs
                </span>
              </div>
            </DropdownItem>
          ))}
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-blue-600 hover:bg-blue-50"
            onClick={() => navigate("/knowledge-base")}
          >
            <PlusIcon className="h-4 w-4" />
            Manage collections
          </button>
        </Dropdown>
      </div>

      <div className="mt-auto hidden border-t border-slate-200 p-3 md:block">
        <div className="flex items-center gap-3 rounded-lg px-1 py-1">
          <Avatar initials={initialsFor("Local User")} tone="violet" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-800">Local User</p>
            <p className="truncate text-xs text-slate-400">local</p>
          </div>
          <span className="text-slate-400">›</span>
        </div>
      </div>
    </aside>
  );
}