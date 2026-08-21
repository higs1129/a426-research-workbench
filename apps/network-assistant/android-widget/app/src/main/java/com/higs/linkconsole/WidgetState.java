package com.higs.linkconsole;

import android.content.Context;
import android.content.SharedPreferences;

final class WidgetState {
    private static final String STATE_PREFS = "link_console_state";
    private static final String CONFIG_PREFS = "link_console_config";

    private WidgetState() {}

    static void save(Context context, NetworkSnapshot snapshot) {
        context.getSharedPreferences(STATE_PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString("mode", snapshot.mode.name())
                .putString("route", snapshot.currentRoute)
                .putInt("latency", snapshot.latencyMs)
                .putInt("tailscale_p95", snapshot.tailscaleP95Ms)
                .putInt("tailscale_jitter", snapshot.tailscaleJitterMs)
                .putFloat("tailscale_loss", (float) snapshot.tailscaleLossPct)
                .putString("tailscale_status", snapshot.tailscaleStatus)
                .putString("tailscale_detail", snapshot.tailscaleDetail)
                .putString("remote_status", snapshot.remoteStatus)
                .putString("remote_detail", snapshot.remoteDetail)
                .putInt("remote_latency", snapshot.remoteLatencyMs)
                .putInt("remote_successes", snapshot.remoteSuccesses)
                .putInt("remote_attempts", snapshot.remoteAttempts)
                .putString("clash_status", snapshot.clashStatus)
                .putString("clash_detail", snapshot.clashDetail)
                .putString("note", snapshot.note)
                .putLong("updated_at", snapshot.updatedAt)
                .apply();
    }

    static NetworkSnapshot load(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(STATE_PREFS, Context.MODE_PRIVATE);
        NetworkSnapshot snapshot = new NetworkSnapshot();
        try {
            snapshot.mode = NetworkSnapshot.Mode.valueOf(
                    prefs.getString("mode", NetworkSnapshot.Mode.UNKNOWN.name()));
        } catch (IllegalArgumentException ignored) {
            snapshot.mode = NetworkSnapshot.Mode.UNKNOWN;
        }
        snapshot.currentRoute = prefs.getString("route", "点按打开并检测");
        snapshot.latencyMs = prefs.getInt("latency", -1);
        snapshot.tailscaleP95Ms = prefs.getInt("tailscale_p95", -1);
        snapshot.tailscaleJitterMs = prefs.getInt("tailscale_jitter", -1);
        snapshot.tailscaleLossPct = prefs.getFloat("tailscale_loss", -1);
        snapshot.tailscaleStatus = prefs.getString("tailscale_status", "未检测");
        snapshot.tailscaleDetail = prefs.getString("tailscale_detail", "启用 Tailscale 后可检测链路");
        snapshot.remoteStatus = prefs.getString("remote_status", "未检测");
        snapshot.remoteDetail = prefs.getString(
                "remote_detail", "启用 Tailscale 或 Clash 后检测 Remote 网络入口");
        snapshot.remoteLatencyMs = prefs.getInt("remote_latency", -1);
        snapshot.remoteSuccesses = prefs.getInt("remote_successes", 0);
        snapshot.remoteAttempts = prefs.getInt("remote_attempts", 0);
        snapshot.clashStatus = prefs.getString("clash_status", "未检测");
        snapshot.clashDetail = prefs.getString("clash_detail", "填写 Secret 后可读取节点");
        snapshot.note = prefs.getString("note", "");
        snapshot.updatedAt = prefs.getLong("updated_at", 0L);
        return snapshot;
    }

    static void setLastSelected(Context context, NetworkSnapshot.Mode mode) {
        context.getSharedPreferences(CONFIG_PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString("last_selected", mode.name())
                .apply();
    }

    static NetworkSnapshot.Mode getLastSelected(Context context) {
        String value = context.getSharedPreferences(CONFIG_PREFS, Context.MODE_PRIVATE)
                .getString("last_selected", NetworkSnapshot.Mode.UNKNOWN.name());
        try {
            return NetworkSnapshot.Mode.valueOf(value);
        } catch (IllegalArgumentException ignored) {
            return NetworkSnapshot.Mode.UNKNOWN;
        }
    }

    static void setClashSecret(Context context, String secret) {
        context.getSharedPreferences(CONFIG_PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString("clash_secret", secret)
                .apply();
    }

    static String getClashSecret(Context context) {
        return context.getSharedPreferences(CONFIG_PREFS, Context.MODE_PRIVATE)
                .getString("clash_secret", "");
    }

    static void setClashAutoSelectionEnabled(Context context, boolean enabled) {
        context.getSharedPreferences(CONFIG_PREFS, Context.MODE_PRIVATE)
                .edit()
                .putBoolean("clash_auto_selection", enabled)
                .apply();
    }

    static boolean isClashAutoSelectionEnabled(Context context) {
        return context.getSharedPreferences(CONFIG_PREFS, Context.MODE_PRIVATE)
                .getBoolean("clash_auto_selection", true);
    }
}
