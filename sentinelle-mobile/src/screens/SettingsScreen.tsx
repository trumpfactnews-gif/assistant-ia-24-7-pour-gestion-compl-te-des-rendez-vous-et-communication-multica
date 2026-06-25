/** Écran de paramètres : connexion à l'API, protection auto, langue, historique. */

import React, { useState } from 'react';
import { Alert, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { AppHeader, Button, ScreenContainer } from '../components/ui';
import { SentinelleClient } from '../api/client';
import { useApp } from '../state/AppContext';
import { useNav } from '../navigation';
import { colors, font, radius, spacing } from '../theme';

export function SettingsScreen() {
  const { config, updateConfig, clearHistory } = useApp();
  const { goBack } = useNav();
  const [baseUrl, setBaseUrl] = useState(config.apiBaseUrl);
  const [apiKey, setApiKey] = useState(config.apiKey ?? '');
  const [testing, setTesting] = useState(false);
  const t = (fr: string, en: string) => (config.lang === 'fr' ? fr : en);

  const saveConnection = async () => {
    await updateConfig({ apiBaseUrl: baseUrl.trim(), apiKey: apiKey.trim() || undefined });
    Alert.alert(t('Enregistré', 'Saved'), t('Connexion mise à jour.', 'Connection updated.'));
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const client = new SentinelleClient({
        baseUrl: baseUrl.trim(),
        apiKey: apiKey.trim() || undefined,
      });
      const h = await client.health();
      Alert.alert(
        t('Connexion réussie', 'Connection OK'),
        `${h.service} · ${t('IA', 'AI')}: ${h.ml_available ? '✓' : '✗'}`,
      );
    } catch {
      Alert.alert(t('Échec', 'Failed'), t('Impossible de joindre le serveur.', 'Could not reach the server.'));
    } finally {
      setTesting(false);
    }
  };

  const confirmClear = () => {
    Alert.alert(
      t('Effacer l’historique ?', 'Clear history?'),
      t('Cette action est irréversible.', 'This cannot be undone.'),
      [
        { text: t('Annuler', 'Cancel'), style: 'cancel' },
        { text: t('Effacer', 'Clear'), style: 'destructive', onPress: () => void clearHistory() },
      ],
    );
  };

  return (
    <ScreenContainer>
      <AppHeader title={t('Paramètres', 'Settings')} onBack={goBack} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.section}>{t('Connexion à l’API', 'API connection')}</Text>
        <Text style={styles.label}>{t('Adresse du serveur', 'Server URL')}</Text>
        <TextInput
          style={styles.input}
          value={baseUrl}
          onChangeText={setBaseUrl}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="http://10.0.2.2:8000"
          placeholderTextColor={colors.textMuted}
        />
        <Text style={styles.label}>{t('Clé d’API (optionnelle)', 'API key (optional)')}</Text>
        <TextInput
          style={styles.input}
          value={apiKey}
          onChangeText={setApiKey}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          placeholder="X-API-Key"
          placeholderTextColor={colors.textMuted}
        />
        <Button label={t('Tester la connexion', 'Test connection')} variant="secondary" onPress={testConnection} loading={testing} />
        <Button label={t('Enregistrer', 'Save')} onPress={saveConnection} />

        <Text style={styles.section}>{t('Protection', 'Protection')}</Text>
        <ToggleRow
          label={t('Protection automatique des SMS', 'Automatic SMS protection')}
          value={config.autoProtect}
          onChange={(v) => void updateConfig({ autoProtect: v })}
        />
        <ToggleRow
          label={t('Langue : Français', 'Language: English')}
          value={config.lang === 'fr'}
          onChange={(v) => void updateConfig({ lang: v ? 'fr' : 'en' })}
        />

        <Text style={styles.section}>{t('Données', 'Data')}</Text>
        <Button label={t('Effacer l’historique', 'Clear history')} variant="danger" onPress={confirmClear} />
      </ScrollView>
    </ScreenContainer>
  );
}

function ToggleRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <View style={styles.toggleRow}>
      <Text style={styles.toggleLabel}>{label}</Text>
      <Switch value={value} onValueChange={onChange} />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md },
  section: {
    color: colors.text,
    fontSize: font.heading,
    fontWeight: '700',
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  label: { color: colors.textMuted, fontSize: font.small, marginBottom: spacing.xs, marginTop: spacing.sm },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    fontSize: font.body,
    padding: spacing.md,
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  toggleLabel: { color: colors.text, fontSize: font.body, flex: 1, marginRight: spacing.md },
});
