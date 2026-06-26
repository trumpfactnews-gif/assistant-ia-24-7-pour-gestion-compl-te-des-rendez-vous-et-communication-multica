/**
 * Mocks des modules natifs pour les tests Jest (s'exécutent sous Node, sans
 * pont natif). Référencé par la clé `jest.setupFiles` de package.json.
 */

/* eslint-env jest */

// AsyncStorage : mock officiel fourni par la librairie.
jest.mock(
  '@react-native-async-storage/async-storage',
  () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

// react-native-permissions : pas de pont natif en test.
jest.mock('react-native-permissions', () => ({
  PERMISSIONS: { ANDROID: { RECEIVE_SMS: 'android.permission.RECEIVE_SMS', READ_SMS: 'android.permission.READ_SMS' } },
  RESULTS: { GRANTED: 'granted', DENIED: 'denied', BLOCKED: 'blocked' },
  requestMultiple: jest.fn(() => Promise.resolve({})),
  requestNotifications: jest.fn(() => Promise.resolve({ status: 'granted' })),
  check: jest.fn(() => Promise.resolve('granted')),
  request: jest.fn(() => Promise.resolve('granted')),
}));

// react-native-push-notification : pas de pont natif en test.
jest.mock('react-native-push-notification', () => ({
  __esModule: true,
  default: { createChannel: jest.fn(), localNotification: jest.fn() },
  Importance: { HIGH: 4, DEFAULT: 3 },
}));
