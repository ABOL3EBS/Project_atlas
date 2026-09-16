import { useApp } from "../../context/AppContext";
import { Header } from "../layout/Header";
import { Button } from "../ui/Button";
import { AlertTriangleIcon, CheckIcon, RefreshIcon } from "../ui/icons";
import { SettingsSection } from "./SettingsSection";

const CONFIG_DEFAULTS: Array<{ label: string; value: string; key: string }> = [
  { label: "Generation model", value: "gemma2 (Ollama)", key: "LLM_PROVIDER=ollama · LLM_MODEL=gemma2" },
  { label: "Embedding model", value: "nomic-embed-text (Ollama)", key: "EMBEDDING_PROVIDER=ollama · EMBEDDING_MODEL=nomic-embed-text" },
  { label: "Grounding threshold", value: "0.60", key: "calibrated on the M6 answer-evaluation dataset" },
];

function Row({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <div>
        <p className="text-sm font-medium text-slate-800">{label}</p>
        {hint && <p className="text-xs text-slate-400">{hint}</p>}
      </div>
      <span className="shrink-0 text-sm text-slate-500">{value}</span>
    </div>
  );
}

export function SettingsScreen() {
  const { health, healthError, refreshHealth } = useApp();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Header
        title="Settings"
        subtitle="System and agent configuration."
        right={
          <Button variant="secondary" icon={<RefreshIcon className="h-4 w-4" />} onClick={() => void refreshHealth()}>
            Refresh
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto px-6 py-6 lg:px-8">
        <div className="mx-auto max-w-2xl space-y-6">
          <SettingsSection title="System status">
            {healthError ? (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertTriangleIcon className="h-4 w-4 shrink-0" />
                Backend unreachable at /api/health.
              </div>
            ) : health ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-800">API</p>
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                      health.status === "ok"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    {health.status === "ok" ? (
                      <CheckIcon className="h-3.5 w-3.5" />
                    ) : (
                      <AlertTriangleIcon className="h-3.5 w-3.5" />
                    )}
                    {health.status}
                  </span>
                </div>
                <Row label="LLM provider" value={health.llm_available ? "available" : "unavailable"} />
                <Row
                  label="Embedding provider"
                  value={health.embedding_available ? "available" : "unavailable"}
                />
              </div>
            ) : (
              <p className="text-sm text-slate-500">Checking…</p>
            )}
          </SettingsSection>

          <SettingsSection title="Configuration">
            <p className="text-xs text-slate-400">
              Runtime settings are managed by the backend — set these in the backend{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em]">.env</code>{" "}
              file (see README). Values shown are the documented defaults in use.
            </p>
            <div className="mt-2 divide-y divide-slate-100">
              {CONFIG_DEFAULTS.map((item) => (
                <Row key={item.label} label={item.label} value={item.value} hint={item.key} />
              ))}
            </div>
          </SettingsSection>

          <SettingsSection title="Danger zone">
            <div className="rounded-lg border border-red-100 bg-red-50/30 p-4">
              <p className="text-sm text-slate-600">
                Clearing all indexed data is intentionally not exposed in this UI.
              </p>
              <button
                type="button"
                disabled
                className="pointer-events-none mt-2 inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-400"
              >
                Clear all indexed data (unavailable from the API)
              </button>
            </div>
          </SettingsSection>
        </div>
      </div>
    </div>
  );
}