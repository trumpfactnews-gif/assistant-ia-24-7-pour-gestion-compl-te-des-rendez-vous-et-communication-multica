package ca.sentinelle.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.provider.Telephony;
import android.telephony.SmsMessage;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;

import com.facebook.react.bridge.Arguments;
import com.facebook.react.bridge.ReactApplicationContext;
import com.facebook.react.bridge.ReactContextBaseJavaModule;
import com.facebook.react.bridge.ReactMethod;
import com.facebook.react.bridge.WritableMap;
import com.facebook.react.modules.core.DeviceEventManagerModule;

/**
 * Module natif d'interception des SMS entrants.
 *
 * Émet un événement JS « onSmsReceived » { sender, body, timestamp } pour chaque
 * SMS reçu pendant que le processus de l'application est vivant (premier plan ou
 * arrière-plan). Pour une interception en état « tué », voir le README
 * (tâche Headless JS + receiver déclaré dans le manifeste).
 */
public class SmsListenerModule extends ReactContextBaseJavaModule {

    private static final String MODULE_NAME = "SmsListener";
    private static final String EVENT_NAME = "onSmsReceived";

    private final ReactApplicationContext reactContext;
    private BroadcastReceiver receiver;

    public SmsListenerModule(ReactApplicationContext context) {
        super(context);
        this.reactContext = context;
    }

    @NonNull
    @Override
    public String getName() {
        return MODULE_NAME;
    }

    @ReactMethod
    public void startListening() {
        if (receiver != null) {
            return;
        }
        receiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context ctx, Intent intent) {
                if (!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) {
                    return;
                }
                SmsMessage[] messages = Telephony.Sms.Intents.getMessagesFromIntent(intent);
                if (messages == null || messages.length == 0) {
                    return;
                }
                String sender = messages[0].getDisplayOriginatingAddress();
                StringBuilder body = new StringBuilder();
                for (SmsMessage message : messages) {
                    // Un long SMS arrive en plusieurs parties à recoller.
                    body.append(message.getMessageBody());
                }
                emitSms(sender, body.toString());
            }
        };
        IntentFilter filter = new IntentFilter(Telephony.Sms.Intents.SMS_RECEIVED_ACTION);
        // ContextCompat gère le drapeau requis depuis Android 13 (API 33).
        ContextCompat.registerReceiver(
                reactContext, receiver, filter, ContextCompat.RECEIVER_EXPORTED);
    }

    @ReactMethod
    public void stopListening() {
        if (receiver != null) {
            try {
                reactContext.unregisterReceiver(receiver);
            } catch (IllegalArgumentException ignored) {
                // Déjà désenregistré : sans gravité.
            }
            receiver = null;
        }
    }

    // Requis par NativeEventEmitter côté JS (évite les avertissements).
    @ReactMethod
    public void addListener(String eventName) {
    }

    @ReactMethod
    public void removeListeners(double count) {
    }

    private void emitSms(String sender, String body) {
        WritableMap params = Arguments.createMap();
        params.putString("sender", sender == null ? "" : sender);
        params.putString("body", body);
        params.putDouble("timestamp", System.currentTimeMillis());
        reactContext
                .getJSModule(DeviceEventManagerModule.RCTDeviceEventEmitter.class)
                .emit(EVENT_NAME, params);
    }
}
