package com.higs.linkconsole;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class CodexTaskRepository {
    interface Callback {
        void onComplete(CodexTaskSnapshot snapshot);
    }

    private static final String PREFS = "codex_task_state";
    private static final String KEY_PAYLOAD = "payload";
    private static final String KEY_LAST_ERROR = "last_error";
    private static final String KEY_LAST_ATTEMPT = "last_attempt_at";
    private static final String TASKS_URL =
            "https://a426.tailabd98b.ts.net/netcheck/api/codex/tasks";
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();
    private static final Object REFRESH_LOCK = new Object();
    private static boolean refreshRunning;
    private static boolean refreshPending;

    private CodexTaskRepository() {}

    static CodexTaskSnapshot load(Context context) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String raw = preferences.getString(KEY_PAYLOAD, "");
        if (raw == null || raw.isEmpty()) return new CodexTaskSnapshot();
        try {
            CodexTaskSnapshot snapshot = CodexTaskSnapshot.fromJson(new JSONObject(raw));
            snapshot.error = preferences.getString(KEY_LAST_ERROR, "");
            snapshot.attemptedAt = preferences.getLong(KEY_LAST_ATTEMPT, snapshot.fetchedAt);
            return snapshot;
        } catch (Exception ignored) {
            return new CodexTaskSnapshot();
        }
    }

    static void refreshIfStale(Context context, long maxAgeMs) {
        CodexTaskSnapshot cached = load(context);
        if (!cached.available || System.currentTimeMillis() - cached.fetchedAt >= maxAgeMs) {
            refresh(context, null);
        }
    }

    static void refresh(Context context, Callback callback) {
        Context appContext = context.getApplicationContext();
        synchronized (REFRESH_LOCK) {
            if (refreshRunning) {
                refreshPending = true;
                if (callback != null) callback.onComplete(load(appContext));
                return;
            }
            refreshRunning = true;
        }

        EXECUTOR.execute(() -> {
            CodexTaskSnapshot result;
            boolean rerun;
            long attemptedAt = System.currentTimeMillis();
            try {
                JSONObject root = new JSONObject(requestTasks());
                if (!root.optBoolean("ok", false)) throw new IOException("A426 returned no task state");
                root.put("client_fetched_at_ms", attemptedAt);
                appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                        .edit()
                        .putString(KEY_PAYLOAD, root.toString())
                        .putString(KEY_LAST_ERROR, "")
                        .putLong(KEY_LAST_ATTEMPT, attemptedAt)
                        .apply();
                result = CodexTaskSnapshot.fromJson(root);
                result.attemptedAt = attemptedAt;
                CodexCompletionNotifier.handleSnapshot(appContext, result);
            } catch (Exception error) {
                String message = friendlyError(error);
                appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                        .edit()
                        .putString(KEY_LAST_ERROR, message)
                        .putLong(KEY_LAST_ATTEMPT, attemptedAt)
                        .apply();
                result = load(appContext);
                result.error = message;
                result.attemptedAt = attemptedAt;
            } finally {
                synchronized (REFRESH_LOCK) {
                    refreshRunning = false;
                    rerun = refreshPending;
                    refreshPending = false;
                }
            }
            CodexWidgetProvider.updateAll(appContext);
            if (callback != null) callback.onComplete(result);
            if (rerun) refresh(appContext, null);
        });
    }

    private static String requestTasks() throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(TASKS_URL).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(5_000);
        connection.setReadTimeout(7_000);
        connection.setUseCaches(false);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("X-Codex-Widget", "1");
        int status = connection.getResponseCode();
        InputStream stream = status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String body = readAll(stream);
        connection.disconnect();
        if (status < 200 || status >= 300) throw new IOException("HTTP " + status);
        return body;
    }

    private static String readAll(InputStream stream) throws IOException {
        if (stream == null) return "";
        StringBuilder value = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) value.append(line);
        }
        return value.toString();
    }

    private static String friendlyError(Exception error) {
        String name = error.getClass().getSimpleName();
        if (name.contains("UnknownHost")) return "Tailscale DNS 暂不可用，保留上次结果";
        if (name.contains("Timeout")) return "连接 A426 超时，保留上次结果";
        return "暂时无法同步 A426，保留上次结果";
    }
}
