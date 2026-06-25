/** Primitives d'interface réutilisables. */

import React from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { colors, font, radius, spacing } from '../theme';

export function ScreenContainer({ children }: { children: React.ReactNode }) {
  return <SafeAreaView style={styles.screen}>{children}</SafeAreaView>;
}

export function AppHeader({
  title,
  onBack,
  onSettings,
}: {
  title: string;
  onBack?: () => void;
  onSettings?: () => void;
}) {
  return (
    <View style={styles.header}>
      {onBack ? (
        <TouchableOpacity onPress={onBack} hitSlop={hit}>
          <Text style={styles.headerIcon}>‹</Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.iconSpacer} />
      )}
      <Text style={styles.headerTitle} numberOfLines={1}>
        {title}
      </Text>
      {onSettings ? (
        <TouchableOpacity onPress={onSettings} hitSlop={hit}>
          <Text style={styles.headerIcon}>⚙︎</Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.iconSpacer} />
      )}
    </View>
  );
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  loading = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  loading?: boolean;
  disabled?: boolean;
}) {
  const bg =
    variant === 'primary' ? colors.primary : variant === 'danger' ? colors.fraud : colors.surfaceAlt;
  return (
    <TouchableOpacity
      style={[styles.button, { backgroundColor: bg }, (disabled || loading) && styles.disabled]}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}>
      {loading ? (
        <ActivityIndicator color={colors.text} />
      ) : (
        <Text style={styles.buttonLabel}>{label}</Text>
      )}
    </TouchableOpacity>
  );
}

const hit = { top: 10, bottom: 10, left: 10, right: 10 };

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  headerTitle: { color: colors.text, fontSize: font.heading, fontWeight: '700', flex: 1, textAlign: 'center' },
  headerIcon: { color: colors.text, fontSize: 26, width: 32, textAlign: 'center' },
  iconSpacer: { width: 32 },
  button: {
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  buttonLabel: { color: colors.text, fontSize: font.body, fontWeight: '700' },
  disabled: { opacity: 0.5 },
});
