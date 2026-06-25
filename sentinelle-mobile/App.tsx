/**
 * Racine de l'application Sentinelle.
 *
 * - Affiche l'onboarding tant que le consentement n'est pas donné.
 * - Une fois actif : configure les notifications, branche l'écoute des SMS
 *   entrants (Android) et route entre les écrans.
 */

import React, { useEffect, useState } from 'react';
import { ActivityIndicator, StatusBar, StyleSheet, View } from 'react-native';

import { AppProvider, useApp } from './src/state/AppContext';
import { NavProvider, useNav } from './src/navigation';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { AnalyzeScreen } from './src/screens/AnalyzeScreen';
import { DetailScreen } from './src/screens/DetailScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { configureNotifications } from './src/services/notifications';
import { startSmsListener } from './src/services/smsListener';
import { hasConsented } from './src/utils/storage';
import { colors } from './src/theme';

function Splash() {
  return (
    <View style={styles.splash}>
      <ActivityIndicator color={colors.primary} size="large" />
    </View>
  );
}

function CurrentScreen() {
  const { route } = useNav();
  switch (route.name) {
    case 'analyze':
      return <AnalyzeScreen />;
    case 'detail':
      return <DetailScreen />;
    case 'settings':
      return <SettingsScreen />;
    case 'home':
    default:
      return <HomeScreen />;
  }
}

function Main() {
  const { config, analyzeMessage } = useApp();

  useEffect(() => {
    configureNotifications();
  }, []);

  // Écoute des SMS entrants (Android) tant que la protection auto est active.
  useEffect(() => {
    if (!config.autoProtect) return undefined;
    const stop = startSmsListener((sms) => {
      void analyzeMessage(sms.body, sms.sender, { auto: true });
    });
    return stop;
  }, [config.autoProtect, analyzeMessage]);

  return (
    <NavProvider>
      <CurrentScreen />
    </NavProvider>
  );
}

function Root() {
  const { ready, config } = useApp();
  const [consent, setConsentState] = useState<boolean | null>(null);

  useEffect(() => {
    hasConsented().then(setConsentState);
  }, []);

  if (!ready || consent === null) {
    return <Splash />;
  }
  if (!consent) {
    return <OnboardingScreen lang={config.lang} onDone={() => setConsentState(true)} />;
  }
  return <Main />;
}

export default function App() {
  return (
    <AppProvider>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
      <Root />
    </AppProvider>
  );
}

const styles = StyleSheet.create({
  splash: { flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' },
});
