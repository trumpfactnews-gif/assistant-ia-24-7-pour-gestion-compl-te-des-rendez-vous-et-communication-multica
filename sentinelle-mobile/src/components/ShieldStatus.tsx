/** Grand bouclier d'état en haut de l'accueil. */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radius, spacing } from '../theme';

interface Props {
  active: boolean;
  threatsBlocked: number;
  lang: 'fr' | 'en';
}

export function ShieldStatus({ active, threatsBlocked, lang }: Props) {
  const t = (fr: string, en: string) => (lang === 'fr' ? fr : en);
  return (
    <View style={[styles.card, { borderColor: active ? colors.safe : colors.caution }]}>
      <Text style={styles.shield}>{active ? '🛡️' : '⚠️'}</Text>
      <Text style={styles.title}>
        {active ? t('Protection active', 'Protection active') : t('Protection en pause', 'Protection paused')}
      </Text>
      <Text style={styles.subtitle}>
        {t(
          `${threatsBlocked} menace(s) détectée(s)`,
          `${threatsBlocked} threat(s) detected`,
        )}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 2,
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
  },
  shield: { fontSize: 64, marginBottom: spacing.sm },
  title: { color: colors.text, fontSize: font.heading, fontWeight: '700' },
  subtitle: { color: colors.textMuted, fontSize: font.body, marginTop: spacing.xs },
});
