import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getHealth, listKnowledgeBases } from "../lib/client";
import type { Health, KnowledgeBase } from "../lib/types";

interface AppContextValue {
  knowledgeBases: KnowledgeBase[];
  knowledgeBase: string;
  setKnowledgeBase: (id: string) => void;
  health: Health | null;
  healthError: boolean;
  refreshKnowledgeBases: () => Promise<void>;
  refreshHealth: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

const STORAGE_KEY = "atlas.knowledgeBase";

export function AppProvider({ children }: { children: ReactNode }) {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBase, setKnowledgeBaseState] = useState<string>(() => {
    return localStorage.getItem(STORAGE_KEY) ?? "default";
  });
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  const refreshKnowledgeBases = useCallback(async () => {
    try {
      const bases = await listKnowledgeBases();
      setKnowledgeBases(bases);
    } catch {
      // keep the previous list; the caller can surface the error
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const result = await getHealth();
      setHealth(result);
      setHealthError(false);
    } catch {
      setHealth(null);
      setHealthError(true);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    void refreshKnowledgeBases();
    const healthTimer = window.setInterval(() => void refreshHealth(), 20000);
    return () => window.clearInterval(healthTimer);
  }, [refreshHealth, refreshKnowledgeBases]);

  const setKnowledgeBase = useCallback(
    (id: string) => {
      localStorage.setItem(STORAGE_KEY, id);
      setKnowledgeBaseState(id);
    },
    [],
  );

  const value = useMemo(
    () => ({
      knowledgeBases,
      knowledgeBase,
      setKnowledgeBase,
      health,
      healthError,
      refreshKnowledgeBases,
      refreshHealth,
    }),
    [knowledgeBases, knowledgeBase, setKnowledgeBase, health, healthError, refreshKnowledgeBases, refreshHealth],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used within AppProvider");
  return value;
}