/** Persistance locale (AsyncStorage) : config, consentement, historique. */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { AppConfig, DEFAULT_CONFIG, STORAGE_KEYS } from '../config';
import type { Verdict } from '../api/types';

export interface HistoryItem {
  id: string;
  at: number;
  message: string;
  sender?: string;
  verdict: Verdict;
  reported?: boolean;
}

const HISTORY_LIMIT = 200;

export async function loadConfig(): Promise<AppConfig> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.config);
    if (!raw) return DEFAULT_CONFIG;
    return { ...DEFAULT_CONFIG, ...(JSON.parse(raw) as Partial<AppConfig>) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export async function saveConfig(config: AppConfig): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEYS.config, JSON.stringify(config));
}

export async function hasConsented(): Promise<boolean> {
  return (await AsyncStorage.getItem(STORAGE_KEYS.consent)) === 'true';
}

export async function setConsent(value: boolean): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEYS.consent, value ? 'true' : 'false');
}

export async function loadHistory(): Promise<HistoryItem[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.history);
    return raw ? (JSON.parse(raw) as HistoryItem[]) : [];
  } catch {
    return [];
  }
}

export async function saveHistory(items: HistoryItem[]): Promise<void> {
  await AsyncStorage.setItem(
    STORAGE_KEYS.history,
    JSON.stringify(items.slice(0, HISTORY_LIMIT)),
  );
}

export async function clearHistory(): Promise<void> {
  await AsyncStorage.removeItem(STORAGE_KEYS.history);
}
