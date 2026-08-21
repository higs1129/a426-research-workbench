package com.higs.linkconsole;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.view.View;
import android.widget.RemoteViews;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class CodexWidgetProvider extends AppWidgetProvider {
    private static final long MAX_FRESH_AGE_MS = 2L * 60L * 1000L;
    private static final String CHATGPT_PACKAGE = "com.openai.chatgpt";
    private static final String CHATGPT_REMOTE_URL = "https://chatgpt.com/remote/";
    private static final int[] ROW_IDS = {
            R.id.codexTaskRow1, R.id.codexTaskRow2, R.id.codexTaskRow3, R.id.codexTaskRow4};
    private static final int[] TITLE_IDS = {
            R.id.codexTaskTitle1, R.id.codexTaskTitle2, R.id.codexTaskTitle3, R.id.codexTaskTitle4};
    private static final int[] STATUS_IDS = {
            R.id.codexTaskStatus1, R.id.codexTaskStatus2, R.id.codexTaskStatus3, R.id.codexTaskStatus4};

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] appWidgetIds) {
        CodexTaskSnapshot snapshot = CodexTaskRepository.load(context);
        for (int id : appWidgetIds) manager.updateAppWidget(id, buildViews(context, snapshot));
        CodexTaskRepository.refreshIfStale(context, 60_000L);
    }

    static void updateAll(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        ComponentName provider = new ComponentName(context, CodexWidgetProvider.class);
        CodexTaskSnapshot snapshot = CodexTaskRepository.load(context);
        for (int id : manager.getAppWidgetIds(provider)) {
            manager.updateAppWidget(id, buildViews(context, snapshot));
        }
    }

    private static RemoteViews buildViews(Context context, CodexTaskSnapshot snapshot) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_codex);
        PendingIntent click = clickIntent(context);
        views.setOnClickPendingIntent(R.id.codexWidgetRoot, click);
        for (int rowId : ROW_IDS) views.setOnClickPendingIntent(rowId, click);

        if (!snapshot.available) {
            renderNotificationFallback(context, views);
            return views;
        }
        if (!snapshot.isFresh(MAX_FRESH_AGE_MS)) {
            renderStaleSnapshot(views, snapshot);
            return views;
        }

        String header;
        if (snapshot.activeCount > 0) {
            header = snapshot.activeCount + " 个任务运行中 · " + snapshot.host;
        } else if (!snapshot.tasks.isEmpty()) {
            header = "Codex 最近任务 · " + snapshot.host;
        } else {
            header = "Codex 空闲 · " + snapshot.host;
        }
        views.setTextViewText(R.id.codexWidgetTitle, header);
        views.setTextViewText(R.id.codexWidgetTime, formatTime(snapshot.fetchedAt));

        List<CodexTaskSnapshot.Task> tasks = snapshot.tasks;
        if (tasks.isEmpty()) {
            showRow(views, 0, "最近 90 分钟没有任务变化", "空闲", "completed");
            hideRowsFrom(views, 1);
            return views;
        }

        int visibleTasks = tasks.size() > 4 ? 3 : Math.min(tasks.size(), 4);
        for (int index = 0; index < visibleTasks; index++) {
            CodexTaskSnapshot.Task task = tasks.get(index);
            showRow(views, index, task.name, statusLabel(task.status), task.status);
        }
        if (tasks.size() > 4) {
            showRow(views, 3, "另有 " + (tasks.size() - 3) + " 项", "进入 Remote 查看", "more");
            hideRowsFrom(views, 4);
        } else {
            hideRowsFrom(views, visibleTasks);
        }
        return views;
    }

    private static void renderStaleSnapshot(RemoteViews views, CodexTaskSnapshot snapshot) {
        views.setTextViewText(R.id.codexWidgetTitle, "Codex 状态待同步 · " + snapshot.host);
        long displayTime = snapshot.attemptedAt > 0L ? snapshot.attemptedAt : snapshot.fetchedAt;
        views.setTextViewText(R.id.codexWidgetTime, formatTime(displayTime));
        String message = snapshot.error.isEmpty()
                ? "状态已超过 2 分钟，已隐藏过期任务"
                : snapshot.error;
        showRow(views, 0, message, "待同步", "stopped");
        hideRowsFrom(views, 1);
    }

    private static void renderNotificationFallback(Context context, RemoteViews views) {
        boolean granted = NotificationAccess.isGranted(context);
        CodexState state = CodexState.load(context);
        views.setTextViewText(R.id.codexWidgetTitle, granted ? "Codex · 等待 A426" : "Codex 状态");
        views.setTextViewText(R.id.codexWidgetTime, granted ? formatTime(state.updatedAt) : "未授权");
        showRow(
                views,
                0,
                granted ? state.title : "点击授予 ChatGPT 通知读取权限",
                granted ? compact(state.text, 16) : "",
                "more");
        hideRowsFrom(views, 1);
    }

    private static void showRow(
            RemoteViews views,
            int index,
            String title,
            String statusLabel,
            String status) {
        views.setViewVisibility(ROW_IDS[index], View.VISIBLE);
        views.setTextViewText(TITLE_IDS[index], symbol(status) + " " + compact(title, 24));
        views.setTextViewText(STATUS_IDS[index], statusLabel);
        views.setTextColor(STATUS_IDS[index], statusColor(status));
    }

    private static void hideRowsFrom(RemoteViews views, int startIndex) {
        for (int index = startIndex; index < ROW_IDS.length; index++) {
            views.setViewVisibility(ROW_IDS[index], View.GONE);
        }
    }

    private static String statusLabel(String status) {
        switch (status) {
            case "running":
                return "运行中";
            case "completed":
                return "已完成";
            case "stopped":
                return "已停止";
            default:
                return "查看";
        }
    }

    private static String symbol(String status) {
        switch (status) {
            case "completed":
                return "✓";
            case "stopped":
                return "!";
            case "more":
                return "+";
            default:
                return "●";
        }
    }

    private static int statusColor(String status) {
        switch (status) {
            case "running":
                return Color.rgb(33, 214, 217);
            case "completed":
                return Color.rgb(71, 213, 151);
            case "stopped":
                return Color.rgb(255, 184, 90);
            default:
                return Color.rgb(146, 171, 183);
        }
    }

    static PendingIntent clickIntent(Context context) {
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(CHATGPT_REMOTE_URL));
        intent.setPackage(CHATGPT_PACKAGE);
        if (context.getPackageManager().resolveActivity(intent, 0) == null) {
            intent = context.getPackageManager().getLaunchIntentForPackage(CHATGPT_PACKAGE);
        }
        if (intent == null) intent = new Intent(context, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(
                context,
                57,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static String compact(String value, int limit) {
        if (value == null) return "";
        String cleaned = value.replaceAll("\\s+", " ").trim();
        return cleaned.length() <= limit ? cleaned : cleaned.substring(0, limit - 1) + "…";
    }

    private static String formatTime(long time) {
        if (time <= 0) return "等待同步";
        return new SimpleDateFormat("HH:mm", Locale.CHINA).format(new Date(time));
    }
}
