package com.higs.linkconsole;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;

import java.util.HashSet;
import java.util.Set;

final class CodexCompletionNotifier {
    private static final String PREFS = "codex_completion_alerts";
    private static final String KEY_ENABLED = "enabled";
    private static final String KEY_INITIALIZED = "initialized";
    private static final String KEY_SEEN_COMPLETIONS = "seen_completions";
    private static final String CHANNEL_ID = "codex_task_completed";
    private static final String CHANNEL_NAME = "Codex 完成提醒";
    private static final int TEST_NOTIFICATION_ID = 0x434F4458;
    private static final long SEEN_RETENTION_MS = 24L * 60L * 60L * 1000L;
    private static final long MAX_COMPLETION_ALERT_AGE_MS = 5L * 60L * 1000L;

    private CodexCompletionNotifier() {}

    static boolean isEnabled(Context context) {
        return preferences(context).getBoolean(KEY_ENABLED, true);
    }

    static void setEnabled(Context context, boolean enabled) {
        preferences(context).edit().putBoolean(KEY_ENABLED, enabled).apply();
    }

    static boolean hasRuntimePermission(Context context) {
        return Build.VERSION.SDK_INT < 33
                || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED;
    }

    static boolean canPost(Context context) {
        if (!hasRuntimePermission(context)) return false;
        NotificationManager manager = manager(context);
        if (manager == null || !manager.areNotificationsEnabled()) return false;
        ensureChannel(context);
        NotificationChannel channel = manager.getNotificationChannel(CHANNEL_ID);
        return channel == null || channel.getImportance() != NotificationManager.IMPORTANCE_NONE;
    }

    static String statusText(Context context) {
        if (!isEnabled(context)) return "完成提醒已关闭";
        if (!hasRuntimePermission(context)) return "需要允许链路助手发送通知";
        if (!canPost(context)) return "系统通知或“Codex 完成提醒”类别已关闭";
        return "完成提醒已开启；在 vivo 健康中勾选链路助手后会同步到手表";
    }

    static void handleSnapshot(Context context, CodexTaskSnapshot snapshot) {
        if (snapshot == null || !snapshot.available) return;

        SharedPreferences prefs = preferences(context);
        Set<String> seen = new HashSet<>(
                prefs.getStringSet(KEY_SEEN_COMPLETIONS, new HashSet<>()));
        pruneOldEntries(seen, System.currentTimeMillis());

        Set<String> completedNow = new HashSet<>();
        for (CodexTaskSnapshot.Task task : snapshot.tasks) {
            if ("completed".equals(task.status)) completedNow.add(completionKey(task));
        }

        if (!prefs.getBoolean(KEY_INITIALIZED, false)) {
            seen.addAll(completedNow);
            prefs.edit()
                    .putBoolean(KEY_INITIALIZED, true)
                    .putStringSet(KEY_SEEN_COMPLETIONS, seen)
                    .apply();
            return;
        }

        boolean enabled = isEnabled(context);
        long now = System.currentTimeMillis();
        for (CodexTaskSnapshot.Task task : snapshot.tasks) {
            if (!"completed".equals(task.status)) continue;
            if (!seen.add(completionKey(task))) continue;
            boolean timely = task.updatedAt > 0L
                    && now >= task.updatedAt
                    && now - task.updatedAt <= MAX_COMPLETION_ALERT_AGE_MS;
            if (enabled && timely) {
                postCompletion(context, task.name, snapshot.host, task.updatedAt);
            }
        }
        prefs.edit().putStringSet(KEY_SEEN_COMPLETIONS, seen).apply();
    }

    static boolean sendTest(Context context) {
        return post(
                context,
                TEST_NOTIFICATION_ID,
                "✓ 手表提醒测试",
                "A426 · Codex 完成提醒已接通",
                System.currentTimeMillis());
    }

    private static void postCompletion(
            Context context,
            String taskName,
            String host,
            long completedAt) {
        String cleanName = compact(taskName, 28, "未命名任务");
        String cleanHost = compact(host, 12, "A426");
        String key = cleanName + '|' + completedAt;
        post(
                context,
                0x43000000 | (key.hashCode() & 0x00FFFFFF),
                "✓ " + cleanName + " 已完成",
                cleanHost + " · 结果已就绪",
                completedAt > 0L ? completedAt : System.currentTimeMillis());
    }

    private static boolean post(
            Context context,
            int notificationId,
            String title,
            String text,
            long when) {
        ensureChannel(context);
        if (!canPost(context)) return false;

        Notification notification = new Notification.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_codex)
                .setColor(Color.rgb(33, 214, 217))
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setContentIntent(CodexWidgetProvider.clickIntent(context))
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_REMINDER)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setWhen(when)
                .setShowWhen(true)
                .build();

        NotificationManager manager = manager(context);
        if (manager == null) return false;
        manager.notify(notificationId, notification);
        return true;
    }

    private static void ensureChannel(Context context) {
        NotificationManager manager = manager(context);
        if (manager == null || manager.getNotificationChannel(CHANNEL_ID) != null) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("当 A426 上的 Codex 任务完成时提醒，并可同步到手表");
        channel.enableVibration(true);
        manager.createNotificationChannel(channel);
    }

    private static NotificationManager manager(Context context) {
        return (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static String completionKey(CodexTaskSnapshot.Task task) {
        return compact(task.name, 80, "未命名任务") + '\u001f' + task.updatedAt;
    }

    private static void pruneOldEntries(Set<String> entries, long now) {
        entries.removeIf(value -> {
            int separator = value.lastIndexOf('\u001f');
            if (separator < 0 || separator == value.length() - 1) return true;
            try {
                long timestamp = Long.parseLong(value.substring(separator + 1));
                return timestamp <= 0L || now - timestamp > SEEN_RETENTION_MS;
            } catch (NumberFormatException ignored) {
                return true;
            }
        });
    }

    private static String compact(String value, int limit, String fallback) {
        if (value == null) return fallback;
        String cleaned = value.replaceAll("\\s+", " ").trim();
        if (cleaned.isEmpty()) return fallback;
        return cleaned.length() <= limit ? cleaned : cleaned.substring(0, limit - 1) + "…";
    }
}
