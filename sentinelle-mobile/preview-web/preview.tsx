import React from 'react';
import { createRoot } from 'react-dom/client';

import { AppProvider } from '@app/src/state/AppContext';
import { NavProvider, useNav, type Route } from '@app/src/navigation';
import { HomeScreen } from '@app/src/screens/HomeScreen';
import { AnalyzeScreen } from '@app/src/screens/AnalyzeScreen';
import { DetailScreen } from '@app/src/screens/DetailScreen';
import { SettingsScreen } from '@app/src/screens/SettingsScreen';
import { OnboardingScreen } from '@app/src/screens/OnboardingScreen';

function Router() {
  const { route } = useNav();
  switch (route.name) {
    case 'analyze':
      return <AnalyzeScreen />;
    case 'detail':
      return <DetailScreen />;
    case 'settings':
      return <SettingsScreen />;
    default:
      return <HomeScreen />;
  }
}

function Screen({ initialRoute }: { initialRoute: Route }) {
  return (
    <AppProvider>
      <NavProvider initialRoute={initialRoute}>
        <Router />
      </NavProvider>
    </AppProvider>
  );
}

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: 14 }}>
      <div style={{ color: '#cdd6e6', font: '600 14px -apple-system,Segoe UI,sans-serif', marginBottom: 10 }}>
        {title}
      </div>
      <div
        className="frame"
        style={{
          width: 320,
          height: 690,
          borderRadius: 30,
          overflow: 'hidden',
          border: '7px solid #28324a',
          boxShadow: '0 14px 50px rgba(0,0,0,.55)',
          display: 'flex',
          background: '#0E1726',
        }}>
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>{children}</div>
      </div>
    </div>
  );
}

function Board() {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        background: '#070b14',
        padding: 28,
      }}>
      <Frame title="1 · Onboarding & consentement">
        <OnboardingScreen lang="fr" onDone={() => {}} />
      </Frame>
      <Frame title="2 · Accueil (bouclier + historique)">
        <Screen initialRoute={{ name: 'home' }} />
      </Frame>
      <Frame title="3 · Analyser un message">
        <Screen initialRoute={{ name: 'analyze' }} />
      </Frame>
      <Frame title="4 · Verdict (détail)">
        <Screen initialRoute={{ name: 'detail', params: { id: 'demo' } }} />
      </Frame>
      <Frame title="5 · Paramètres">
        <Screen initialRoute={{ name: 'settings' }} />
      </Frame>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<Board />);
