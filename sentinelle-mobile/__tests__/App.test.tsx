/**
 * Test de fumée : l'application se monte sans planter.
 *
 * L'app s'initialise de façon asynchrone (chargement config + consentement) ;
 * on enveloppe le rendu dans `act(async …)` pour laisser les effets se résoudre
 * (sinon : avertissements act() / "environnement Jest démonté").
 */

import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';

import App from '../App';

it('se monte sans planter', async () => {
  let renderer: TestRenderer.ReactTestRenderer | undefined;
  await act(async () => {
    renderer = TestRenderer.create(<App />);
  });
  // Laisse les promesses d'initialisation se résoudre.
  await act(async () => {
    await Promise.resolve();
  });
  expect(renderer!.toJSON()).toBeTruthy();
  renderer!.unmount();
});
