package com.higs.linkconsole;

import android.app.PendingIntent;
import android.content.Context;
import android.content.SharedPreferences;

final class CodexState {
    private static final String PREFS = "codex_widget_state";
    private static volatile PendingIntent latestContentIntent;

    String title = "Codex Remote";
    String text = "等待 ChatGPT 通知";
    String notificationKey = "";
    long updatedAt = 0L;

    static CodexState load(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        CodexState state = new CodexState();
        state.title = prefs.getString("title", state.title);
        state.text = prefs.getString("text", state.text);
        state.notificationKey = prefs.getString("notification_key", "");
        state.updatedAt = prefs.getLong("updated_at", 0L);
        return state;
    }

    static void save(Context context, CodexState state, PendingIntent contentIntent) {
        latestContentIntent = contentIntent;
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString("title", state.title)
                .putString("text", state.text)
                .putString("notification_key", state.notificationKey)
                .putLong("updated_at", state.updatedAt)
                .apply();
    }

    static PendingIntent getLatestContentIntent() {
        return latestContentIntent;
    }

    static void clearContentIntent() {
        latestContentIntent = null;
    }
}
