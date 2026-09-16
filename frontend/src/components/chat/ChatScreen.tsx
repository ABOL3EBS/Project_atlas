import { useEffect, useRef, useState } from "react";
import { useApp } from "../../context/AppContext";
import { useChat } from "../../context/ChatContext";
import type { Citation } from "../../lib/types";
import { CollectionSelector } from "../knowledge-base/CollectionSelector";
import { Dropdown, DropdownItem } from "../ui/Dropdown";
import { ChatIcon, PlusIcon, RefreshIcon, SpinnerIcon } from "../ui/icons";
import { Header } from "../layout/Header";
import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { MessageList } from "./MessageList";
import { SourceDrawer } from "./SourceDrawer";

export function ChatScreen() {
  const { refreshingKnowledgeBases, refreshKnowledgeBases } = useApp();
  const {
    messages,
    conversations,
    conversationId,
    startNewConversation,
    switchConversation,
    traceOpen,
    setTraceOpen,
    traceMessageKey,
    setTraceMessageKey,
  } = useChat();
  const [prefill, setPrefill] = useState("");
  const [source, setSource] = useState<Citation | null>(null);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (traceOpen && last?.role === "assistant" && last.key !== traceMessageKey) {
      setTraceMessageKey(last.key);
    }
  }, [messages, traceOpen, traceMessageKey, setTraceMessageKey]);

  const inspectTrace = (key: string) => {
    setTraceMessageKey(key);
    setTraceOpen(true);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Header
        title="Chat"
        subtitle="Ask questions about your knowledge base."
        right={
          <>
            <CollectionSelector compact align="right" />
            <button
              type="button"
              onClick={() => void refreshKnowledgeBases()}
              aria-label="Refresh collections"
              title="Refresh collections"
              disabled={refreshingKnowledgeBases}
              className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {refreshingKnowledgeBases ? (
                <SpinnerIcon className="h-4 w-4" />
              ) : (
                <RefreshIcon className="h-4 w-4" />
              )}
            </button>
            <Dropdown
              label="Conversations"
              align="right"
              trigger={
                <span className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 transition-colors hover:bg-slate-50">
                  <ChatIcon className="h-4 w-4" />
                </span>
              }
            >
              <button
                type="button"
                onClick={() => void startNewConversation()}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-blue-600 hover:bg-blue-50"
              >
                <PlusIcon className="h-4 w-4" /> New chat
              </button>
              <div className="my-1 border-t border-slate-100" />
              {conversations.length === 0 && (
                <p className="px-3 py-2 text-sm text-slate-400">No previous conversations.</p>
              )}
              {[...conversations]
                .sort((a, b) => b.created_at.localeCompare(a.created_at))
                .slice(0, 20)
                .map((conversation) => (
                  <DropdownItem
                    key={conversation.id}
                    active={conversation.id === conversationId}
                    onSelect={() => void switchConversation(conversation.id)}
                  >
                    <div className="min-w-0">
                      <p className="truncate">
                        Chat · {new Date(conversation.created_at).toLocaleString()}
                      </p>
                    </div>
                  </DropdownItem>
                ))}
            </Dropdown>
          </>
        }
      />

      {messages.length === 0 && !messages.find((m) => m.streaming) ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <EmptyState
            onPickQuestion={(question) => {
              setPrefill(question);
            }}
          />
          <Composer prefilled={prefill} />
        </div>
      ) : (
        <>
          <MessageList
            messages={messages}
            stickToBottomRef={stickToBottomRef}
            onOpenSource={setSource}
            onInspectTrace={inspectTrace}
            traceSelectedKey={traceMessageKey}
          />
          <Composer />
        </>
      )}

      {source && <SourceDrawer citation={source} onClose={() => setSource(null)} />}
    </div>
  );
}