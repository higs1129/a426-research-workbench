package com.higs.linkconsole;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.widget.RemoteViews;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class NetworkWidgetProvider extends AppWidgetProvider {
    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager, int[] appWidgetIds) {
        NetworkSnapshot snapshot = WidgetState.load(context);
        for (int appWidgetId : appWidgetIds) {
            appWidgetManager.updateAppWidget(appWidgetId, buildViews(context, snapshot));
        }
    }

    static void updateAll(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        ComponentName provider = new ComponentName(context, NetworkWidgetProvider.class);
        int[] ids = manager.getAppWidgetIds(provider);
        NetworkSnapshot snapshot = WidgetState.load(context);
        for (int id : ids) {
            manager.updateAppWidget(id, buildViews(context, snapshot));
        }
    }

    private static RemoteViews buildViews(Context context, NetworkSnapshot snapshot) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_network);
        views.setTextViewText(R.id.widgetMode, snapshot.modeLabel());
        views.setTextViewText(R.id.widgetRoute, snapshot.widgetRouteLabel());
        views.setTextViewText(R.id.widgetLatency, snapshot.latencyLabel());
        views.setTextViewText(R.id.widgetUpdated, formatTime(snapshot.updatedAt));

        int accent;
        switch (snapshot.mode) {
            case TAILSCALE:
                accent = Color.rgb(33, 214, 217);
                break;
            case CLASH:
                accent = Color.rgb(155, 120, 255);
                break;
            case NONE:
                accent = Color.rgb(255, 184, 90);
                break;
            default:
                accent = Color.rgb(146, 171, 183);
                break;
        }
        views.setTextColor(R.id.widgetMode, accent);

        Intent open = new Intent(context, MainActivity.class)
                .putExtra("refresh_now", true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pending = PendingIntent.getActivity(
                context,
                41,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        views.setOnClickPendingIntent(R.id.widgetRoot, pending);
        return views;
    }

    private static String formatTime(long time) {
        if (time <= 0) return "点击检测";
        return new SimpleDateFormat("HH:mm", Locale.CHINA).format(new Date(time));
    }
}
