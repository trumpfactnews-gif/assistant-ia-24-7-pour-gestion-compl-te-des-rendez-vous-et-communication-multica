package ca.sentinelle.sms;

import android.content.Intent;
import android.os.Bundle;

import androidx.annotation.Nullable;

import com.facebook.react.HeadlessJsTaskService;
import com.facebook.react.bridge.Arguments;
import com.facebook.react.jstasks.HeadlessJsTaskConfig;

/**
 * Service qui exécute la tâche JS « SentinelleSmsTask » (voir
 * src/services/smsHeadlessTask.ts), déclenchée par {@link SmsHeadlessReceiver}.
 *
 * ⚠️ Android 8+ : le démarrage d'un service depuis un broadcast en arrière-plan
 * est restreint. En production, ce service doit appeler startForeground() avec
 * une notification (type « dataSync »/« shortService ») ; voir le README mobile.
 */
public class SmsHeadlessTaskService extends HeadlessJsTaskService {

    @Nullable
    @Override
    protected HeadlessJsTaskConfig getTaskConfig(Intent intent) {
        Bundle extras = intent.getExtras();
        if (extras == null) {
            return null;
        }
        return new HeadlessJsTaskConfig(
                "SentinelleSmsTask",
                Arguments.fromBundle(extras),
                30000,   // délai max (ms)
                false    // non autorisé en premier plan (évite les doublons avec le module live)
        );
    }
}
