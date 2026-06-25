/** Écran d'analyse manuelle : coller un message suspect. */

import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { AppHeader, Button, ScreenContainer } from '../components/ui';
import { SentinelleApiError } from '../api/client';
import { useApp } from '../state/AppContext';
import { useNav } from '../navigation';
import { colors, font, radius, spacing } from '../theme';

export function AnalyzeScreen() {
  const { config, analyzeMessage } = useApp();
  const { navigate, goBack } = useNav();
  const [message, setMessage] = useState('');
  const [sender, setSender] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = (fr: string, en: string) => (config.lang === 'fr' ? fr : en);

  const run = async () => {
    if (!message.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const item = await analyzeMessage(message.trim(), sender.trim() || undefined);
      navigate('detail', { id: item.id });
    } catch (e) {
      const msg =
        e instanceof SentinelleApiError
          ? e.message
          : t('Une erreur est survenue.', 'Something went wrong.');
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenContainer>
      <AppHeader title={t('Analyser', 'Analyze')} onBack={goBack} />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.label}>{t('Message reçu', 'Received message')}</Text>
          <TextInput
            style={[styles.input, styles.textarea]}
            value={message}
            onChangeText={setMessage}
            placeholder={t('Collez ici le SMS suspect…', 'Paste the suspicious text here…')}
            placeholderTextColor={colors.textMuted}
            multiline
            textAlignVertical="top"
          />

          <Text style={styles.label}>{t('Expéditeur (optionnel)', 'Sender (optional)')}</Text>
          <TextInput
            style={styles.input}
            value={sender}
            onChangeText={setSender}
            placeholder={t('Ex. +1 514 555-0199', 'E.g. +1 514 555-0199')}
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button
            label={t('Analyser le message', 'Analyze message')}
            onPress={run}
            loading={busy}
            disabled={!message.trim()}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { padding: spacing.md },
  label: { color: colors.textMuted, fontSize: font.small, marginBottom: spacing.xs, marginTop: spacing.md },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    fontSize: font.body,
    padding: spacing.md,
  },
  textarea: { minHeight: 140 },
  error: { color: colors.fraud, fontSize: font.small, marginTop: spacing.md },
});
