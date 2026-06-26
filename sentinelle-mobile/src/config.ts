/**
 * Configuration de l'application. Les valeurs sont surchargées à l'exécution
 * par les réglages utilisateur (écran Paramètres, persistés via AsyncStorage).
 */

export interface AppConfig {
  apiBaseUrl: string;
  apiKey?: string;
  /** Protection automatique des SMS entrants (Android uniquement). */
  autoProtect: boolean;
  lang: 'fr' | 'en';
}

import { Platform } from 'react-native';

export const DEFAULT_CONFIG: AppConfig = {
  // Web (démo) : pas de serveur par défaut → analyse hors ligne instantanée.
  // Android (émulateur) : 10.0.2.2 pointe vers le localhost de l'hôte.
  apiBaseUrl: Platform.OS === 'web' ? '' : 'http://10.0.2.2:8000',
  apiKey: undefined,
  autoProtect: true,
  lang: 'fr',
};

export const STORAGE_KEYS = {
  config: 'sentinelle.config',
  consent: 'sentinelle.consent',
  history: 'sentinelle.history',
} as const;
