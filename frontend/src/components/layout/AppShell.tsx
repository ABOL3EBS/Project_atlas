import { Outlet } from "react-router-dom";
import { useApp } from "../../context/AppContext";
import { useChat } from "../../context/ChatContext";
import { AlertTriangleIcon } from "../ui/icons";
import { Sidebar } from "./Sidebar";
import { TracePanel } from "../trace/TracePanel";

export function AppShell() {
  const { traceOpen, setTraceOpen } = useChat();
  const { health, healthError } = useApp();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      <Sidebar />

      <div className="relative flex min-w-0 flex-1 flex-col">
        {health && !health.llm_available && (
          <div className="flex shrink-0 items-center gap-2 border-b border-amber-200 bg-amber-50 px-6 py-2 text-xs text-amber-800">
            <AlertTriangleIcon className="h-4 w-4" />
            <span>
              LLM provider unavailable — chat responses will not stream. Start Ollama and ensure the
              model is pulled, then refresh.
            </span>
          </div>
        )}
        {healthError && (
          <div className="flex shrink-0 items-center gap-2 border-b border-red-200 bg-red-50 px-6 py-2 text-xs text-red-800">
            <AlertTriangleIcon className="h-4 w-4" />
            <span>Backend unreachable. Start the Atlas backend, then refresh.</span>
          </div>
        )}
        <Outlet />
      </div>

      {traceOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-slate-900/20 lg:hidden"
            onClick={() => setTraceOpen(false)}
            aria-hidden
          />
          <TracePanel className="fixed inset-y-0 right-0 z-40 w-[340px] max-w-full shadow-sm lg:static lg:z-auto lg:shadow-none" />
        </>
      )}
    </div>
  );
}