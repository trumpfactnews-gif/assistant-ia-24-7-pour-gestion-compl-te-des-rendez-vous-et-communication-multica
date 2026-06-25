/**
 * Pont vers le module natif Android d'interception des SMS.
 *
 * Le module natif (voir `android-native/`) émet un événement `onSmsReceived`
 * pour chaque SMS entrant, avec l'expéditeur et le corps du message.
 *
 * ⚠️ iOS ne permet pas l'interception silencieuse des SMS : sur iOS, ce module
 * est absent et `startSmsListener` est un no-op. Le flux manuel (coller un
 * message) reste disponible sur toutes les plateformes.
 */

import { NativeEventEmitter, NativeModules, Platform } from 'react-native';

export interface IncomingSms {
  sender: string;
  body: string;
  timestamp: number;
}

type SmsHandler = (sms: IncomingSms) => void;

const { SmsListener } = NativeModules as {
  SmsListener?: {
    startListening: () => void;
    stopListening: () => void;
  };
};

export const isSmsInterceptionSupported = Platform.OS === 'android' && !!SmsListener;

export function startSmsListener(onSms: SmsHandler): () => void {
  if (!isSmsInterceptionSupported || !SmsListener) {
    return () => undefined;
  }
  const emitter = new NativeEventEmitter(NativeModules.SmsListener);
  const subscription = emitter.addListener('onSmsReceived', (event: IncomingSms) => {
    onSms(event);
  });
  SmsListener.startListening();

  return () => {
    subscription.remove();
    SmsListener.stopListening();
  };
}
