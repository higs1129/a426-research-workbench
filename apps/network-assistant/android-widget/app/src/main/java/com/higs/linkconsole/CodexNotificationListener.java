package com.higs.linkconsole;

import android.app.Notification;
import android.app.PendingIntent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import java.util.Locale;

public class CodexNotificationListener extends NotificationListenerService {
    private static final String CHATGPT_PACKAGE = "com.openai.chatgpt";
    private static volatile CodexNotificationListener connectedInstance;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable removalSync = this::syncAfterRemoval;
    private final Runnable taskRefresh = () -> CodexTaskRepository.refresh(this, null);

    @Override
    public void onListenerConnected() {
        super.onListenerConnected();
        connectedInstance = this;
        syncActiveNotifications(true);
        scheduleTaskRefreshBurst(500L);
    }

    @Override
    public void onListenerDisconnected() {
        if (connectedInstance == this) connectedInstance = null;
        super.onListenerDisconnected();
    }

    @Override
    public void onDestroy() {
        if (connectedInstance == this) connectedInstance = null;
        super.onDestroy();
    }

    static String getDiagnosticSnapshot() {
        CodexNotificationListener service = connectedInstance;
        return service == null ? null : service.buildDiagnosticSnapshot();
    }

    @Override
    public void onNotificationPosted(StatusBarNotification notification) {
        super.onNotificationPosted(notification);
        if (isChatGpt(notification)) {
            capture(notification);
            scheduleTaskRefreshBurst(1_200L);
        }
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification notification) {
        super.onNotificationRemoved(notification);
        if (!isChatGpt(notification)) return;
        handler.removeCallbacks(removalSync);
        handler.postDelayed(removalSync, 500L);
    }

    private void syncActiveNotifications(boolean clearWhenEmpty) {
        StatusBarNotification newest = newestChatGptNotification();
        if (newest != null) {
            capture(newest);
        } else if (clearWhenEmpty) {
            markCurrentNotificationFinished();
        }
    }

    private void syncAfterRemoval() {
        StatusBarNotification newest = newestChatGptNotification();
        if (newest != null) {
            capture(newest);
            scheduleTaskRefreshBurst(1_200L);
            return;
        }
        markCurrentNotificationFinished();
        scheduleTaskRefreshBurst(1_200L);
    }

    private void markCurrentNotificationFinished() {
        CodexState state = CodexState.load(this);
        if (state.notificationKey.isEmpty()) return;

        String lowerTitle = state.title.toLowerCase(Locale.ROOT);
        String lowerText = state.text.toLowerCase(Locale.ROOT);
        boolean isRemote = lowerTitle.contains("remote") || state.text.contains("连接");
        boolean wasRunning = state.text.contains("正在运行") || lowerText.contains("running");

        state.text = isRemote
                ? "Remote 已断开"
                : wasRunning ? "任务已结束" : "通知已结束";
        state.notificationKey = "";
        state.updatedAt = System.currentTimeMillis();
        CodexState.save(this, state, null);
        CodexWidgetProvider.updateAll(this);
    }

    private StatusBarNotification newestChatGptNotification() {
        StatusBarNotification[] active;
        try {
            active = getActiveNotifications();
        } catch (SecurityException error) {
            return null;
        }
        if (active == null) return null;
        StatusBarNotification newest = null;
        for (StatusBarNotification item : active) {
            if (!isChatGpt(item)) continue;
            if (newest == null || item.getPostTime() > newest.getPostTime()) newest = item;
        }
        return newest;
    }

    private String buildDiagnosticSnapshot() {
        StatusBarNotification[] active;
        try {
            active = getActiveNotifications();
        } catch (SecurityException error) {
            return "读取失败：系统拒绝了活动通知访问。";
        }

        if (active == null) active = new StatusBarNotification[0];
        int total = 0;
        int summaries = 0;
        int children = 0;
        int clickableChildren = 0;
        int independent = 0;
        int clickableIndependent = 0;
        int maxTextLines = 0;
        StringBuilder details = new StringBuilder();

        for (StatusBarNotification item : active) {
            if (!isChatGpt(item)) continue;
            total++;

            Notification notification = item.getNotification();
            boolean summary = (notification.flags & Notification.FLAG_GROUP_SUMMARY) != 0;
            boolean grouped = item.isGroup();
            boolean clickable = notification.contentIntent != null
                    || notification.fullScreenIntent != null;
            CharSequence[] textLines = notification.extras == null
                    ? null
                    : notification.extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES);
            int lineCount = textLines == null ? 0 : textLines.length;
            maxTextLines = Math.max(maxTextLines, lineCount);

            String kind;
            if (summary) {
                summaries++;
                kind = "汇总";
            } else if (grouped) {
                children++;
                if (clickable) clickableChildren++;
                kind = "子项";
            } else {
                independent++;
                if (clickable) clickableIndependent++;
                kind = "独立";
            }

            Bundle extras = notification.extras;
            String title = extras == null ? "ChatGPT" : firstText(
                    extras.getCharSequence(Notification.EXTRA_TITLE),
                    extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE),
                    "ChatGPT");
            String text = extras == null ? "" : firstText(
                    extras.getCharSequence(Notification.EXTRA_BIG_TEXT),
                    extras.getCharSequence(Notification.EXTRA_TEXT),
                    extras.getCharSequence(Notification.EXTRA_SUB_TEXT),
                    "");

            details.append('\n')
                    .append(total).append(". [").append(kind).append("] ")
                    .append(cleanDiagnosticText(title))
                    .append("\n   点击=").append(clickable ? "有" : "无")
                    .append(" · 文本行=").append(lineCount);
            if (!text.isEmpty()) {
                details.append("\n   ").append(cleanDiagnosticText(text));
            }
            if (textLines != null && textLines.length > 0) {
                for (int index = 0; index < Math.min(textLines.length, 4); index++) {
                    details.append("\n   ↳ ").append(cleanDiagnosticText(textLines[index]));
                }
            }
        }

        if (total == 0) {
            return "活动 ChatGPT 通知：0\n当前没有可供判断的运行任务。";
        }

        String verdict;
        if (children >= 2 && clickableChildren == children) {
            verdict = "结论：具备逐任务分列和精确跳转条件。";
        } else if (children > 0 && clickableChildren > 0) {
            verdict = "结论：只检测到部分子通知带独立入口，需要按可点击项降级展示。";
        } else if (maxTextLines >= 2) {
            verdict = "结论：可从汇总文本分列任务，但未发现独立子通知，不能保证逐线程跳转。";
        } else if (independent >= 2 && clickableIndependent >= 2) {
            verdict = "结论：检测到多条独立可点击通知，可以逐项展示和跳转。";
        } else {
            verdict = "结论：当前只暴露了汇总或单条通知，暂不能确认逐线程跳转。";
        }

        return "活动 ChatGPT 通知：" + total
                + "\n汇总=" + summaries
                + " · 子项=" + children + "（可点击 " + clickableChildren + "）"
                + "\n独立=" + independent + "（可点击 " + clickableIndependent + "）"
                + "\n" + verdict
                + details;
    }

    private String cleanDiagnosticText(CharSequence value) {
        if (value == null) return "";
        String cleaned = value.toString().replaceAll("\\s+", " ").trim();
        return cleaned.length() <= 72 ? cleaned : cleaned.substring(0, 69) + "…";
    }

    private void capture(StatusBarNotification statusBarNotification) {
        Notification notification = statusBarNotification.getNotification();
        Bundle extras = notification.extras;
        String title = firstText(
                extras.getCharSequence(Notification.EXTRA_TITLE),
                extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE),
                "ChatGPT");
        String text = firstText(
                extras.getCharSequence(Notification.EXTRA_BIG_TEXT),
                extras.getCharSequence(Notification.EXTRA_TEXT),
                extras.getCharSequence(Notification.EXTRA_SUB_TEXT),
                "收到一条新通知");

        CodexState state = new CodexState();
        state.title = title;
        state.text = text;
        state.notificationKey = statusBarNotification.getKey();
        state.updatedAt = statusBarNotification.getPostTime();
        PendingIntent contentIntent = notification.contentIntent != null
                ? notification.contentIntent
                : notification.fullScreenIntent;
        CodexState.save(this, state, contentIntent);
        CodexWidgetProvider.updateAll(this);
    }

    private void scheduleTaskRefreshBurst(long firstDelayMs) {
        handler.removeCallbacks(taskRefresh);
        handler.postDelayed(taskRefresh, firstDelayMs);
        handler.postDelayed(taskRefresh, Math.max(firstDelayMs + 3_800L, 5_000L));
        handler.postDelayed(taskRefresh, Math.max(firstDelayMs + 13_800L, 15_000L));
    }

    private boolean isChatGpt(StatusBarNotification notification) {
        return notification != null && CHATGPT_PACKAGE.equals(notification.getPackageName());
    }

    private String firstText(CharSequence first, CharSequence second, String fallback) {
        return firstText(first, second, null, fallback);
    }

    private String firstText(
            CharSequence first,
            CharSequence second,
            CharSequence third,
            String fallback) {
        CharSequence[] candidates = {first, second, third};
        for (CharSequence candidate : candidates) {
            if (candidate != null && !candidate.toString().trim().isEmpty()) {
                return candidate.toString().trim();
            }
        }
        return fallback;
    }
}
