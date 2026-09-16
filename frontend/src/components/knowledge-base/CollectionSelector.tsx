import { useState } from "react";
import { useApp } from "../../context/AppContext";
import { Dropdown, DropdownItem } from "../ui/Dropdown";
import { ChevronDownIcon, DocumentMultiIcon, PlusIcon } from "../ui/icons";

export function CollectionSelector({
  compact = false,
  align = "left",
}: {
  compact?: boolean;
  align?: "left" | "right";
}) {
  const { knowledgeBases, knowledgeBase, setKnowledgeBase, refreshKnowledgeBases } = useApp();
  const [newName, setNewName] = useState("");
  const selected = knowledgeBases.find((kb) => kb.id === knowledgeBase);

  const createNew = () => {
    const name = newName.trim();
    if (!name) return;
    setKnowledgeBase(name);
    setNewName("");
    void refreshKnowledgeBases();
  };

  const trigger = compact ? (
    <span className="flex max-w-56 items-center gap-2">
      <DocumentMultiIcon className="h-4 w-4 shrink-0 text-slate-500" />
      <span className="truncate text-sm font-medium text-slate-800">
        {selected?.id ?? knowledgeBase}
      </span>
      <ChevronDownIcon className="h-4 w-4 shrink-0 text-slate-400" />
    </span>
  ) : (
    <span className="flex flex-col">
      <span className="text-sm font-medium text-slate-800">
        {selected?.id ?? knowledgeBase}
      </span>
      <span className="text-xs text-slate-400">
        {selected
          ? `${selected.document_count} docs · ${selected.chunk_count} chunks`
          : "No collections found"}
      </span>
    </span>
  );

  return (
    <Dropdown
      label="Select knowledge base"
      align={align}
      menuClassName="w-[280px]"
      trigger={
        <div
          className={`flex cursor-pointer items-center gap-2.5 rounded-lg border border-slate-200 bg-white transition-colors hover:bg-slate-50 ${
            compact ? "px-3 py-2 text-sm" : "p-3"
          }`}
        >
          {trigger}
        </div>
      }
    >
      <p className="px-3 pb-1 pt-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Collections
      </p>
      {knowledgeBases.map((kb) => (
        <DropdownItem
          key={kb.id}
          active={kb.id === knowledgeBase}
          onSelect={() => setKnowledgeBase(kb.id)}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="min-w-0 truncate">{kb.id}</span>
            <span className="shrink-0 whitespace-nowrap text-xs text-slate-400">
              {kb.document_count} docs · {kb.chunk_count}
            </span>
          </div>
        </DropdownItem>
      ))}
      <div className="my-1 border-t border-slate-100" />
      <div className="flex items-center gap-2 px-2 py-1">
        <PlusIcon className="h-4 w-4 shrink-0 text-blue-600" />
        <input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") createNew();
          }}
          placeholder="New collection name"
          aria-label="New collection name"
          className="w-full bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
        />
        <button
          type="button"
          onClick={createNew}
          className="shrink-0 rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
        >
          Create
        </button>
      </div>
    </Dropdown>
  );
}