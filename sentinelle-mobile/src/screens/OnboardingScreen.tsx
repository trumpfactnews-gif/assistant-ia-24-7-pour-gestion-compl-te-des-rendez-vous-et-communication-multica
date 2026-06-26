/** Écran d'accueil initial : explication, consentement et permissions. */

import React, { useState } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { PERMISSIONS, requestMultiple, requestNotifications } from 'react-native-permissions';

import { Button, ScreenContainer } from '../components/ui';
import { colors, font, spacing } from '../theme';
import { setConsent } from '../utils/storage';
import { isSmsInterceptionSupported } from '../services/smsListener';

interface Props {
  lang: 'fr' | 'en';
  onDone: () => void;
}

async function requestAndroidPermissions(): Promise<void> {
  if (Platform.OS !== 'android') return;
  try {
    await requestMultiple([PERMISSIONS.ANDROID.RECEIVE_SMS, PERMISSIONS.ANDROID.READ_SMS]);
    // POST_NOTIFICATIONS (Android 13+) se demande via l'API dédiée.
    await requestNotifications(['alert', 'sound']);
  } catch {
    // Permissions refusées ou lib absente : l'app reste utilisable en mode manuel.
  }
}

export function OnboardingScreen({ lang, onDone }: Props) {
  const [busy, setBusy] = useState(false);
  const t = (fr: string, en: string) => (lang === 'fr' ? fr : en);

  const accept = async () => {
    setBusy(true);
    await requestAndroidPermissions();
    await setConsent(true);
    setBusy(false);
    onDone();
  };

  return (
    <ScreenContainer>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.shield}>🛡️</Text>
        <Text style={styles.title}>Sentinelle</Text>
        <Text style={styles.tagline}>
          {t(
            'Votre bouclier contre les fraudes par message texte.',
            'Your shield against text-message fraud.',
          )}
        </Text>

        <View style={styles.bullets}>
          <Bullet text={t('Analyse les SMS suspects en temps réel.', 'Analyzes suspicious texts in real time.')} />
          <Bullet text={t('Vous alerte avant que la fraude ne réussisse.', 'Warns you before fraud succeeds.')} />
          <Bullet text={t('Protégé par une communauté de signalements.', 'Powered by a community of reports.')} />
        </View>

        <View style={styles.consentBox}>
          <Text style={styles.consentTitle}>{t('Votre vie privée', 'Your privacy')}</Text>
          <Text style={styles.consentText}>
            {t(
              "Pour vous protéger, Sentinelle a besoin de votre consentement pour analyser le contenu des SMS. Les numéros ne sont jamais stockés en clair et le contenu n'est pas conservé.",
              'To protect you, Sentinelle needs your consent to analyze SMS content. Phone numbers are never stored in clear text and message content is not retained.',
            )}
          </Text>
          {!isSmsInterceptionSupported && (
            <Text style={styles.iosNote}>
              {t(
                "ℹ️ Sur cet appareil, l'analyse automatique des SMS n'est pas possible. Vous pourrez analyser un message manuellement en le collant dans l'app.",
                'ℹ️ On this device, automatic SMS analysis is not available. You can analyze a message manually by pasting it into the app.',
              )}
            </Text>
          )}
        </View>

        <Button
          label={t('Activer la protection', 'Enable protection')}
          onPress={accept}
          loading={busy}
        />
      </ScrollView>
    </ScreenContainer>
  );
}

function Bullet({ text }: { text: string }) {
  return (
    <View style={styles.bulletRow}>
      <Text style={styles.bulletDot}>✓</Text>
      <Text style={styles.bulletText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, alignItems: 'center' },
  shield: { fontSize: 72, marginTop: spacing.xl },
  title: { color: colors.text, fontSize: font.title, fontWeight: '900', marginTop: spacing.sm },
  tagline: {
    color: colors.textMuted,
    fontSize: font.body,
    textAlign: 'center',
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  bullets: { alignSelf: 'stretch', marginBottom: spacing.lg },
  bulletRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: spacing.sm },
  bulletDot: { color: colors.safe, fontSize: font.body, marginRight: spacing.sm, fontWeight: '800' },
  bulletText: { color: colors.text, fontSize: font.body, flex: 1, lineHeight: 21 },
  consentBox: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  consentTitle: { color: colors.text, fontSize: font.body, fontWeight: '700', marginBottom: spacing.xs },
  consentText: { color: colors.textMuted, fontSize: font.small, lineHeight: 19 },
  iosNote: { color: colors.caution, fontSize: font.small, lineHeight: 19, marginTop: spacing.sm },
});
