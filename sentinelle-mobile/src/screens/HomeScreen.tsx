/** Écran d'accueil : bouclier + actions + historique récent. */

import React from 'react';
import { FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { AppHeader, Button, ScreenContainer } from '../components/ui';
import { ShieldStatus } from '../components/ShieldStatus';
import { useApp } from '../state/AppContext';
import { useNav } from '../navigation';
import { colors, font, radius, spacing } from '../theme';
import { levelStyle, pickLang } from '../utils/verdict';
import type { HistoryItem } from '../utils/storage';

export function HomeScreen() {
  const { config, history, threatsBlocked } = useApp();
  const { navigate } = useNav();
  const t = (fr: string, en: string) => (config.lang === 'fr' ? fr : en);

  return (
    <ScreenContainer>
      <AppHeader title="Sentinelle" onSettings={() => navigate('settings')} />
      <FlatList
        contentContainerStyle={styles.content}
        data={history}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          <View>
            <ShieldStatus active={config.autoProtect} threatsBlocked={threatsBlocked} lang={config.lang} />
            <Button
              label={t('Analyser un message', 'Analyze a message')}
              onPress={() => navigate('analyze')}
            />
            <Text style={styles.sectionTitle}>{t('Activité récente', 'Recent activity')}</Text>
          </View>
        }
        renderItem={({ item }) => (
          <HistoryRow item={item} lang={config.lang} onPress={() => navigate('detail', { id: item.id })} />
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {t('Aucun message analysé pour le moment.', 'No message analyzed yet.')}
          </Text>
        }
      />
    </ScreenContainer>
  );
}

function HistoryRow({
  item,
  lang,
  onPress,
}: {
  item: HistoryItem;
  lang: 'fr' | 'en';
  onPress: () => void;
}) {
  const style = levelStyle(item.verdict.level);
  return (
    <TouchableOpacity style={styles.row} onPress={onPress} activeOpacity={0.7}>
      <View style={[styles.dot, { backgroundColor: style.color }]} />
      <View style={styles.rowBody}>
        <Text style={styles.rowMsg} numberOfLines={1}>
          {item.message}
        </Text>
        <Text style={styles.rowMeta}>
          {pickLang(item.verdict.level_label, lang)} · {item.verdict.risk_score}/100
          {item.sender ? ` · ${item.sender}` : ''}
        </Text>
      </View>
      <Text style={styles.chevron}>›</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md },
  sectionTitle: {
    color: colors.text,
    fontSize: font.heading,
    fontWeight: '700',
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  empty: { color: colors.textMuted, fontSize: font.body, textAlign: 'center', marginTop: spacing.lg },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  dot: { width: 12, height: 12, borderRadius: 6, marginRight: spacing.md },
  rowBody: { flex: 1 },
  rowMsg: { color: colors.text, fontSize: font.body },
  rowMeta: { color: colors.textMuted, fontSize: font.small, marginTop: 2 },
  chevron: { color: colors.textMuted, fontSize: 24, marginLeft: spacing.sm },
});
