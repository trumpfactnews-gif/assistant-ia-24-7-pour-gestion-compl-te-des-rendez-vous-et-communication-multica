/**
 * Contexte applicatif : configuration, client API, historique et actions.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { SentinelleApiError, SentinelleClient } from '../api/client';
import type { ReportInput, Verdict } from '../api/types';
import { offlineAnalyze } from '../detection/offline';
import { AppConfig, DEFAULT_CONFIG } from '../config';
import { shouldAlert } from '../utils/verdict';
import { looksLikePhone } from '../utils/phone';
import {
  HistoryItem,
  clearHistory as clearHistoryStore,
  loadConfig,
  loadHistory,
  saveConfig,
  saveHistory,
} from '../utils/storage';
import { showFraudAlert } from '../services/notifications';

interface AppContextValue {
  ready: boolean;
  config: AppConfig;
  client: SentinelleClient;
  history: HistoryItem[];
  threatsBlocked: number;
  updateConfig: (patch: Partial<AppConfig>) => Promise<void>;
  analyzeMessage: (
    message: string,
    sender?: string,
    options?: { auto?: boolean },
  ) => Promise<HistoryItem>;
  reportTarget: (input: ReportInput) => Promise<void>;
  markReported: (id: string) => void;
  clearHistory: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

function newId(): string {
  return `${Date.now()}-${Math.round(Math.random() * 1e9)}`;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  useEffect(() => {
    (async () => {
      const [cfg, hist] = await Promise.all([loadConfig(), loadHistory()]);
      setConfig(cfg);
      setHistory(hist);
      setReady(true);
    })();
  }, []);

  const client = useMemo(
    () => new SentinelleClient({ baseUrl: config.apiBaseUrl, apiKey: config.apiKey }),
    [config.apiBaseUrl, config.apiKey],
  );

  const persistHistory = useCallback(async (items: HistoryItem[]) => {
    setHistory(items);
    await saveHistory(items);
  }, []);

  const updateConfig = useCallback(
    async (patch: Partial<AppConfig>) => {
      const next = { ...config, ...patch };
      setConfig(next);
      await saveConfig(next);
    },
    [config],
  );

  const analyzeMessage = useCallback(
    async (message: string, sender?: string, options?: { auto?: boolean }) => {
      let verdict: Verdict;
      if (!config.apiBaseUrl.trim()) {
        // Aucun serveur configuré → analyse hors ligne immédiate (mode démo).
        verdict = offlineAnalyze(message, config.lang);
      } else {
        try {
          verdict = await client.analyze(message, sender, config.lang);
        } catch (err) {
          // Backend injoignable (réseau/timeout) → repli sur l'analyse hors ligne.
          if (err instanceof SentinelleApiError && err.status === 0) {
            verdict = offlineAnalyze(message, config.lang);
          } else {
            throw err;
          }
        }
      }
      const item: HistoryItem = { id: newId(), at: Date.now(), message, sender, verdict };
      await persistHistory([item, ...history]);
      if (options?.auto && shouldAlert(verdict.level)) {
        showFraudAlert(verdict, config.lang);
      }
      return item;
    },
    [client, config.lang, history, persistHistory],
  );

  const reportTarget = useCallback(
    async (input: ReportInput) => {
      await client.report(input);
    },
    [client],
  );

  const markReported = useCallback(
    (id: string) => {
      const next = history.map((h) => (h.id === id ? { ...h, reported: true } : h));
      void persistHistory(next);
    },
    [history, persistHistory],
  );

  const clearHistory = useCallback(async () => {
    setHistory([]);
    await clearHistoryStore();
  }, []);

  const threatsBlocked = useMemo(
    () => history.filter((h) => shouldAlert(h.verdict.level)).length,
    [history],
  );

  const value: AppContextValue = {
    ready,
    config,
    client,
    history,
    threatsBlocked,
    updateConfig,
    analyzeMessage,
    reportTarget,
    markReported,
    clearHistory,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error('useApp doit être utilisé dans un AppProvider');
  }
  return ctx;
}

export { looksLikePhone };
