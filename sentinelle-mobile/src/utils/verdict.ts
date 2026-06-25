/**
 * Helpers de présentation d'un verdict (logique pure, sans React Native).
 */

import type { Bilingual, Lang, RiskLevel } from '../api/types';

export interface LevelStyle {
  color: string;
  emoji: string;
}

const LEVEL_STYLES: Record<RiskLevel, LevelStyle> = {
  safe: { color: '#1FA463', emoji: '✅' },
  caution: { color: '#E6A700', emoji: '🟡' },
  suspicious: { color: '#E8730C', emoji: '⚠️' },
  fraud: { color: '#D7263D', emoji: '🛑' },
};

export function levelStyle(level: RiskLevel): LevelStyle {
  return LEVEL_STYLES[level] ?? LEVEL_STYLES.safe;
}

/** Déduit le niveau à partir d'un score (mêmes seuils que le backend). */
export function levelFromScore(score: number): RiskLevel {
  if (score >= 75) return 'fraud';
  if (score >= 50) return 'suspicious';
  if (score >= 25) return 'caution';
  return 'safe';
}

/** Choisit la chaîne dans la langue voulue, avec repli sur l'autre. */
export function pickLang(text: Bilingual, lang: Lang): string {
  return text[lang] || text[lang === 'fr' ? 'en' : 'fr'] || '';
}

/** true si le message mérite une notification / un blocage proactif. */
export function shouldAlert(level: RiskLevel): boolean {
  return level === 'suspicious' || level === 'fraud';
}
