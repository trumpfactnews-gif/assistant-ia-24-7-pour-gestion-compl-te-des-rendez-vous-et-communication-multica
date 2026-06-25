/** Carte de verdict : jauge de score, niveau, catégorie, explication, action. */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { Verdict } from '../api/types';
import { colors, font, radius, spacing } from '../theme';
import { levelStyle, pickLang } from '../utils/verdict';

interface Props {
  verdict: Verdict;
  lang: 'fr' | 'en';
}

export function VerdictCard({ verdict, lang }: Props) {
  const style = levelStyle(verdict.level);
  const score = Math.max(0, Math.min(100, verdict.risk_score));

  return (
    <View style={[styles.card, { borderColor: style.color }]}>
      <View style={styles.header}>
        <Text style={styles.emoji}>{style.emoji}</Text>
        <View style={styles.headerText}>
          <Text style={[styles.level, { color: style.color }]}>
            {pickLang(verdict.level_label, lang)}
          </Text>
          <Text style={styles.category}>{pickLang(verdict.category_label, lang)}</Text>
        </View>
        <Text style={[styles.score, { color: style.color }]}>{score}</Text>
      </View>

      <View style={styles.gaugeTrack}>
        <View style={[styles.gaugeFill, { width: `${score}%`, backgroundColor: style.color }]} />
      </View>

      <Text style={styles.explanation}>{pickLang(verdict.explanation, lang)}</Text>

      <View style={[styles.actionBox, { borderLeftColor: style.color }]}>
        <Text style={styles.actionLabel}>
          {lang === 'fr' ? 'Que faire ?' : 'What to do?'}
        </Text>
        <Text style={styles.actionText}>{pickLang(verdict.recommended_action, lang)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1.5,
    padding: spacing.md,
  },
  header: { flexDirection: 'row', alignItems: 'center' },
  emoji: { fontSize: 36, marginRight: spacing.sm },
  headerText: { flex: 1 },
  level: { fontSize: font.heading, fontWeight: '800' },
  category: { color: colors.textMuted, fontSize: font.small, marginTop: 2 },
  score: { fontSize: 34, fontWeight: '900' },
  gaugeTrack: {
    height: 8,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    marginVertical: spacing.md,
    overflow: 'hidden',
  },
  gaugeFill: { height: 8, borderRadius: radius.pill },
  explanation: { color: colors.text, fontSize: font.body, lineHeight: 21 },
  actionBox: {
    marginTop: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderLeftWidth: 4,
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  actionLabel: { color: colors.textMuted, fontSize: font.small, fontWeight: '700', marginBottom: 2 },
  actionText: { color: colors.text, fontSize: font.body, lineHeight: 20 },
});
