package ca.sentinelle.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.provider.Telephony;
import android.telephony.SmsMessage;

import com.facebook.react.HeadlessJsTaskService;

/**
 * Receiver déclaré dans le manifeste : reçoit les SMS même quand l'application
 * est « tuée », puis démarre le {@link SmsHeadlessTaskService} qui exécute la
 * tâche JS « SentinelleSmsTask ».
 *
 * Complète {@link SmsListenerModule} (qui ne fonctionne que processus vivant).
 */
public class SmsHeadlessReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
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
            body.append(message.getMessageBody());
        }

        Bundle extras = new Bundle();
        extras.putString("sender", sender == null ? "" : sender);
        extras.putString("body", body.toString());
        extras.putDouble("timestamp", System.currentTimeMillis());

        Intent service = new Intent(context, SmsHeadlessTaskService.class);
        service.putExtras(extras);

        // Maintient le CPU éveillé le temps de lancer la tâche JS.
        HeadlessJsTaskService.acquireWakeLockNow(context);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(service);
        } else {
            context.startService(service);
        }
    }
}
