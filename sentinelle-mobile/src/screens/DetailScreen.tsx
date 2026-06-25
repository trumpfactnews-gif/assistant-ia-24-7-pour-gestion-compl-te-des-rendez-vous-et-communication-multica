/** Écran de détail d'un verdict + signalement communautaire. */

import React, { useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AppHeader, Button, ScreenContainer } from '../components/ui';
import { SignalList } from '../components/SignalList';
import { VerdictCard } from '../components/VerdictCard';
import { useApp } from '../state/AppContext';
import { useNav } from '../navigation';
import { colors, font, spacing } from '../theme';
import { looksLikePhone } from '../utils/phone';
import type { ReportInput } from '../api/types';

export function DetailScreen() {
  const { config, history, reportTarget, markReported } = useApp();
  const { route, goBack } = useNav();
  const [busy, setBusy] = useState(false);
  const t = (fr: string, en: string) => (config.lang === 'fr' ? fr : en);

  const id = route.params?.id as string | undefined;
  const item = useMemo(() => history.find((h) => h.id === id), [history, id]);

  if (!item) {
    return (
      <ScreenContainer>
        <AppHeader title={t('Détail', 'Detail')} onBack={goBack} />
        <Text style={styles.missing}>{t('Message introuvable.', 'Message not found.')}</Text>
      </ScreenContainer>
    );
  }

  const badDomains = item.verdict.analyzed_urls
    .filter((u) => !u.is_official)
    .map((u) => u.registrable_domain);
  const canReportNumber = !!item.sender && looksLikePhone(item.sender);
  const canReport = canReportNumber || badDomains.length > 0;

  const submitReport = async () => {
    setBusy(true);
    try {
      const targets: ReportInput[] = [];
      if (canReportNumber && item.sender) {
        targets.push({
          type: 'number',
          value: item.sender,
          category: item.verdict.category,
          message: item.message,
        });
      }
      for (const domain of badDomains) {
        targets.push({ type: 'domain', value: domain, category: item.verdict.category });
      }
      await Promise.all(targets.map((tg) => reportTarget(tg)));
      markReported(item.id);
      Alert.alert(
        t('Merci !', 'Thank you!'),
        t(
          'Votre signalement protège toute la communauté.',
          'Your report protects the whole community.',
        ),
      );
    } catch {
      Alert.alert(t('Erreur', 'Error'), t('Le signalement a échoué.', 'The report failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenContainer>
      <AppHeader title={t('Verdict', 'Verdict')} onBack={goBack} />
      <ScrollView contentContainerStyle={styles.content}>
        <VerdictCard verdict={item.verdict} lang={config.lang} />

        <Text style={styles.sectionTitle}>{t('Message', 'Message')}</Text>
        <View style={styles.messageBox}>
          {item.sender ? <Text style={styles.sender}>{item.sender}</Text> : null}
          <Text style={styles.messageText}>{item.message}</Text>
        </View>

        <Text style={styles.sectionTitle}>{t('Indices détectés', 'Detected indicators')}</Text>
        <SignalList signals={item.verdict.signals} lang={config.lang} />

        {canReport ? (
          item.reported ? (
            <Text style={styles.reported}>
              ✓ {t('Déjà signalé à la communauté.', 'Already reported to the community.')}
            </Text>
          ) : (
            <Button
              label={t('Signaler comme fraude', 'Report as fraud')}
              variant="danger"
              onPress={submitReport}
              loading={busy}
            />
          )
        ) : null}
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md },
  missing: { color: colors.textMuted, fontSize: font.body, textAlign: 'center', marginTop: spacing.xl },
  sectionTitle: {
    color: colors.text,
    fontSize: font.heading,
    fontWeight: '700',
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  messageBox: { backgroundColor: colors.surface, borderRadius: 12, padding: spacing.md },
  sender: { color: colors.textMuted, fontSize: font.small, marginBottom: spacing.xs },
  messageText: { color: colors.text, fontSize: font.body, lineHeight: 21 },
  reported: { color: colors.safe, fontSize: font.body, textAlign: 'center', marginTop: spacing.lg },
});
