import { useEffect, useRef, type MutableRefObject } from "react";
import type { Citation } from "../../lib/types";
import type { ChatMessage } from "../../context/ChatContext";
import { AssistantMessage } from "./AssistantMessage";
import { UserMessage } from "./UserMessage";

export function MessageList({
  messages,
  stickToBottomRef,
  onOpenSource,
  onInspectTrace,
  traceSelectedKey,
}: {
  messages: ChatMessage[];
  stickToBottomRef: MutableRefObject<boolean>;
  onOpenSource: (citation: Citation) => void;
  onInspectTrace: (key: string) => void;
  traceSelectedKey: string | null;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const previousFirstKey = useRef<string | null>(null);

  // Observe whether the user is pinned to the bottom of the thread.
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        stickToBottomRef.current = entry.isIntersecting;
      },
      { root: listRef.current },
    );
    const sentinel = sentinelRef.current;
    if (sentinel) observer.observe(sentinel);
    return () => observer.disconnect();
  }, [stickToBottomRef]);

  // Scroll to bottom on new messages; follow streaming only when pinned.
  useEffect(() => {
    const firstKey = messages[0]?.key ?? null;
    const last = messages[messages.length - 1];
    const shouldScroll =
      firstKey !== previousFirstKey.current ||
      (stickToBottomRef.current && (last?.streaming ?? false));
    previousFirstKey.current = firstKey;
    if (shouldScroll) {
      sentinelRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages, stickToBottomRef]);

  return (
    <div ref={listRef} className="flex-1 overflow-y-auto px-6 py-6 lg:px-8">
      <div className="mx-auto max-w-3xl space-y-6">
        {messages.map((message) =>
          message.role === "user" ? (
            <UserMessage key={message.key} content={message.content} created_at={message.created_at} />
          ) : (
            <AssistantMessage
              key={message.key}
              message={message}
              onOpenSource={onOpenSource}
              onInspectTrace={() => onInspectTrace(message.key)}
              traceSelected={traceSelectedKey === message.key}
            />
          ),
        )}
        <div ref={sentinelRef} className="h-1" aria-hidden />
      </div>
    </div>
  );
}