/**
 * Notifications locales (alerte « bouclier »).
 * Enveloppe fine autour de react-native-push-notification.
 */

import PushNotification, { Importance } from 'react-native-push-notification';

import type { Verdict } from '../api/types';
import { pickLang } from '../utils/verdict';
import type { Lang } from '../api/types';

const CHANNEL_ID = 'sentinelle-alerts';

export function configureNotifications(): void {
  PushNotification.createChannel(
    {
      channelId: CHANNEL_ID,
      channelName: 'Alertes Sentinelle',
      channelDescription: 'Avertissements lorsqu’une fraude est détectée',
      importance: Importance.HIGH,
      vibrate: true,
    },
    () => undefined,
  );
}

export function showFraudAlert(verdict: Verdict, lang: Lang = 'fr'): void {
  const title =
    verdict.level === 'fraud'
      ? lang === 'fr'
        ? '🛑 Fraude bloquée'
        : '🛑 Fraud blocked'
      : lang === 'fr'
        ? '⚠️ Message suspect'
        : '⚠️ Suspicious message';

  PushNotification.localNotification({
    channelId: CHANNEL_ID,
    title,
    message: pickLang(verdict.explanation, lang),
    bigText: pickLang(verdict.recommended_action, lang),
    priority: 'high',
    importance: 'high',
    playSound: true,
  });
}
