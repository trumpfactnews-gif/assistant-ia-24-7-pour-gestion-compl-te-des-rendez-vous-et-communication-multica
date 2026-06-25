/** Liste des indices (signaux) détectés dans un message. */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { Signal } from '../api/types';
import { colors, font, radius, spacing } from '../theme';
import { pickLang } from '../utils/verdict';

interface Props {
  signals: Signal[];
  lang: 'fr' | 'en';
}

export function SignalList({ signals, lang }: Props) {
  if (signals.length === 0) {
    return (
      <Text style={styles.empty}>
        {lang === 'fr' ? 'Aucun indice marquant.' : 'No notable indicator.'}
      </Text>
    );
  }
  return (
    <View>
      {signals.map((s, i) => (
        <View key={`${s.code}-${i}`} style={styles.row}>
          <Text style={styles.bullet}>•</Text>
          <View style={styles.body}>
            <Text style={styles.label}>{pickLang(s.label, lang)}</Text>
            {s.evidence ? <Text style={styles.evidence}>« {s.evidence} »</Text> : null}
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { color: colors.textMuted, fontSize: font.body },
  row: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    padding: spacing.sm,
    marginBottom: spacing.xs,
  },
  bullet: { color: colors.primary, fontSize: font.body, marginRight: spacing.sm },
  body: { flex: 1 },
  label: { color: colors.text, fontSize: font.body },
  evidence: { color: colors.textMuted, fontSize: font.small, marginTop: 2, fontStyle: 'italic' },
});
