import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useChat } from "../../context/ChatContext";
import { PaperclipIcon, SendIcon, StopIcon } from "../ui/icons";
import { Toggle } from "../ui/Toggle";

export function Composer({ prefilled }: { prefilled?: string }) {
  const [value, setValue] = useState(prefilled ?? "");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const navigatingRef = useRef(false);
  const navigate = useNavigate();
  const { sendMessage, isStreaming, stopStreaming, traceOpen, setTraceOpen } = useChat();

  useEffect(() => {
    if (prefilled && !navigatingRef.current) {
      setValue(prefilled);
      textareaRef.current?.focus();
    }
  }, [prefilled]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || isStreaming) return;
    navigatingRef.current = false;
    setValue("");
    void sendMessage(text);
  };

  const attach = () => {
    if (!navigatingRef.current) {
      navigate("/knowledge-base", { state: { openUpload: true } });
      navigatingRef.current = true;
    }
  };

  return (
    <div className="shrink-0 border-t border-slate-200 bg-white px-6 py-4 lg:px-8 lg:py-5">
      <div className="mx-auto max-w-3xl">
        <div
          className={`rounded-2xl border bg-white shadow-sm transition-colors ${
            focused ? "border-blue-400" : "border-slate-200"
          }`}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              navigatingRef.current = false;
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask a question about your knowledge base..."
            aria-label="Message"
            className="max-h-[140px] w-full resize-none rounded-2xl bg-transparent px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
          />
          <div className="flex items-center justify-between px-3 pb-2.5">
            {isStreaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              >
                <StopIcon className="h-4 w-4" /> Stop
              </button>
            ) : (
              <span className="px-2" />
            )}
            <button
              type="button"
              onClick={submit}
              disabled={!value.trim() || isStreaming}
              aria-label="Send message"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              <SendIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-4 px-1">
          <button
            type="button"
            onClick={attach}
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
          >
            <PaperclipIcon className="h-4 w-4" />
            Attach file
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700"
            onClick={() => setTraceOpen(!traceOpen)}
          >
            <Toggle checked={traceOpen} onChange={setTraceOpen} label="Show trace" />
            Show trace
          </button>
        </div>
      </div>
    </div>
  );
}