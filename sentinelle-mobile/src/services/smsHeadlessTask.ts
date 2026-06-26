/**
 * Tâche Headless JS : analyse un SMS même lorsque l'application est « tuée ».
 *
 * Sur Android, un BroadcastReceiver déclaré dans le manifeste
 * (`SmsHeadlessReceiver`) démarre un `HeadlessJsTaskService` qui exécute CETTE
 * fonction, hors de toute interface. On y lit la configuration persistée,
 * on analyse le message via le backend, on journalise et on notifie.
 *
 * Enregistrée dans `index.js` :
 *   AppRegistry.registerHeadlessTask('SentinelleSmsTask', () => sentinelleSmsHeadlessTask);
 */

import { SentinelleClient } from '../api/client';
import { configureNotifications, showFraudAlert } from './notifications';
import { shouldAlert } from '../utils/verdict';
import { HistoryItem, loadConfig, loadHistory, saveHistory } from '../utils/storage';

export interface HeadlessSms {
  sender: string;
  body: string;
  timestamp?: number;
}

export async function sentinelleSmsHeadlessTask(data: HeadlessSms): Promise<void> {
  if (!data || !data.body) {
    return;
  }
  const config = await loadConfig();
  if (!config.autoProtect) {
    return;
  }

  const client = new SentinelleClient({ baseUrl: config.apiBaseUrl, apiKey: config.apiKey });
  try {
    const verdict = await client.analyze(data.body, data.sender, config.lang);

    const at = data.timestamp ?? Date.now();
    const item: HistoryItem = {
      id: `${at}-${Math.round(Math.random() * 1e9)}`,
      at,
      message: data.body,
      sender: data.sender,
      verdict,
    };
    const history = await loadHistory();
    await saveHistory([item, ...history]);

    if (shouldAlert(verdict.level)) {
      configureNotifications();
      showFraudAlert(verdict, config.lang);
    }
  } catch {
    // Hors ligne ou backend indisponible : on n'interrompt rien, on réessaiera
    // au prochain message (une file d'attente hors-ligne est prévue à la roadmap).
  }
}
