// Application Sentinelle INTERACTIVE dans le navigateur (react-native-web).
// Monte le vrai App.tsx dans un cadre « téléphone ». Sans backend, l'analyse
// bascule automatiquement en mode hors ligne (embarqué).
import React from 'react';
import { createRoot } from 'react-dom/client';

import App from '@app/App';

function Phone() {
  return (
    <div
      style={{
        width: 380,
        height: 800,
        maxHeight: '96vh',
        borderRadius: 34,
        overflow: 'hidden',
        border: '8px solid #28324a',
        boxShadow: '0 18px 60px rgba(0,0,0,.6)',
        display: 'flex',
        background: '#0E1726',
      }}>
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <App />
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <div
    style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 14,
      background: '#070b14',
      fontFamily: '-apple-system,Segoe UI,sans-serif',
    }}>
    <div style={{ color: '#cdd6e6', fontSize: 14 }}>
      🛡️ Sentinelle — démo navigateur (analyse hors ligne si aucun serveur)
    </div>
    <Phone />
  </div>,
);
