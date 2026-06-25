/**
 * Navigation minimaliste à pile (sans dépendance native supplémentaire).
 *
 * Choix volontaire : pour une application focalisée (4–5 écrans) et un transfert
 * sans friction, on évite la chaîne de dépendances natives de react-navigation
 * (react-native-screens, gesture-handler…). Remplaçable par react-navigation
 * si l'app grandit.
 */

import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type ScreenName = 'home' | 'analyze' | 'detail' | 'settings';

export interface Route {
  name: ScreenName;
  params?: Record<string, unknown>;
}

interface NavValue {
  route: Route;
  canGoBack: boolean;
  navigate: (name: ScreenName, params?: Record<string, unknown>) => void;
  goBack: () => void;
}

const NavContext = createContext<NavValue | null>(null);

export function NavProvider({ children }: { children: React.ReactNode }) {
  const [stack, setStack] = useState<Route[]>([{ name: 'home' }]);

  const navigate = useCallback((name: ScreenName, params?: Record<string, unknown>) => {
    setStack((s) => [...s, { name, params }]);
  }, []);

  const goBack = useCallback(() => {
    setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));
  }, []);

  const value = useMemo<NavValue>(
    () => ({
      route: stack[stack.length - 1] ?? { name: 'home' },
      canGoBack: stack.length > 1,
      navigate,
      goBack,
    }),
    [stack, navigate, goBack],
  );

  return <NavContext.Provider value={value}>{children}</NavContext.Provider>;
}

export function useNav(): NavValue {
  const ctx = useContext(NavContext);
  if (!ctx) {
    throw new Error('useNav doit être utilisé dans un NavProvider');
  }
  return ctx;
}
