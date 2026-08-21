package com.higs.linkconsole;

import android.app.Activity;
import android.app.NotificationManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.provider.Settings;
import android.service.notification.NotificationListenerService;

final class NotificationAccess {
    private NotificationAccess() {}

    static ComponentName component(Context context) {
        return new ComponentName(context, CodexNotificationListener.class);
    }

    static boolean isGranted(Context context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            NotificationManager manager =
                    (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            return manager != null && manager.isNotificationListenerAccessGranted(component(context));
        }
        String enabled = Settings.Secure.getString(
                context.getContentResolver(), "enabled_notification_listeners");
        return enabled != null && enabled.contains(component(context).flattenToString());
    }

    static void openSettings(Activity activity) {
        Intent intent = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
        activity.startActivity(intent);
    }

    static void requestRebind(Context context) {
        if (isGranted(context)) {
            NotificationListenerService.requestRebind(component(context));
        }
    }
}
