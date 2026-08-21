package com.higs.linkconsole;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Handler;
import android.os.Looper;

final class VpnSwitcher {
    interface Callback {
        void onProgress(String message);
        void onComplete(boolean success, String message);
    }

    private static final String TAILSCALE_PACKAGE = "com.tailscale.ipn";
    private static final String TAILSCALE_RECEIVER = "com.tailscale.ipn.IPNReceiver";
    private static final String TAILSCALE_CONNECT = "com.tailscale.ipn.CONNECT_VPN";
    private static final String TAILSCALE_DISCONNECT = "com.tailscale.ipn.DISCONNECT_VPN";
    private static final String TAILSCALE_EXIT_NODE = "com.tailscale.ipn.USE_EXIT_NODE";

    private static final String CLASH_PACKAGE = "com.github.metacubex.clash.meta";
    private static final String CLASH_ACTIVITY = "com.github.kr328.clash.ExternalControlActivity";
    private static final String CLASH_START = "com.github.metacubex.clash.meta.action.START_CLASH";
    private static final String CLASH_STOP = "com.github.metacubex.clash.meta.action.STOP_CLASH";

    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private VpnSwitcher() {}

    static void switchToTailscale(Activity activity, Callback callback) {
        if (!isInstalled(activity, TAILSCALE_PACKAGE)) {
            callback.onComplete(false, "未安装 Tailscale");
            return;
        }
        callback.onProgress("正在停止 Clash Meta…");
        try {
            if (isInstalled(activity, CLASH_PACKAGE)) {
                launchClashControl(activity, CLASH_STOP);
            }
        } catch (Exception ignored) {
            // Tailscale may still take ownership of the VPN interface below.
        }

        MAIN.postDelayed(() -> {
            callback.onProgress("正在连接 Tailscale…");
            try {
                sendTailscaleBroadcast(activity, TAILSCALE_CONNECT, null);
            } catch (Exception error) {
                callback.onComplete(false, "Tailscale 启动请求失败：" + safeMessage(error));
                return;
            }

            MAIN.postDelayed(() -> {
                callback.onProgress("正在选择 A426 出口节点…");
                try {
                    Intent exitNode = new Intent(TAILSCALE_EXIT_NODE)
                            .setClassName(TAILSCALE_PACKAGE, TAILSCALE_RECEIVER)
                            .putExtra("exitNode", "a426")
                            .putExtra("allowLanAccess", true);
                    activity.sendBroadcast(exitNode);
                    WidgetState.setLastSelected(activity, NetworkSnapshot.Mode.TAILSCALE);
                    MAIN.postDelayed(() -> callback.onComplete(
                            true,
                            "已请求切换到 Tailscale；正在验证真实路径"), 2_000);
                } catch (Exception error) {
                    callback.onComplete(false, "出口节点设置失败：" + safeMessage(error));
                }
            }, 2_200);
        }, 800);
    }

    static void switchToClash(Activity activity, Callback callback) {
        if (!isInstalled(activity, CLASH_PACKAGE)) {
            callback.onComplete(false, "未安装 Clash Meta for Android");
            return;
        }
        callback.onProgress("正在断开 Tailscale…");
        try {
            if (isInstalled(activity, TAILSCALE_PACKAGE)) {
                sendTailscaleBroadcast(activity, TAILSCALE_DISCONNECT, null);
            }
        } catch (Exception ignored) {
            // Starting Clash will request ownership of the single Android VPN slot.
        }

        MAIN.postDelayed(() -> {
            callback.onProgress("正在启动 Clash Meta…");
            try {
                launchClashControl(activity, CLASH_START);
                WidgetState.setLastSelected(activity, NetworkSnapshot.Mode.CLASH);
                MAIN.postDelayed(() -> {
                    if (!WidgetState.isClashAutoSelectionEnabled(activity)) {
                        callback.onComplete(true, "已切换到 Clash Meta；保留上次节点选择");
                        return;
                    }
                    callback.onProgress("正在让自动选择接管节点…");
                    NetworkRepository.selectClashAutomatic(activity, (success, message) -> {
                        if (success) {
                            callback.onComplete(true, message);
                        } else {
                            callback.onComplete(
                                    true,
                                    "Clash 已启动，但自动选择未接管：" + message);
                        }
                    });
                }, 2_000);
            } catch (ActivityNotFoundException error) {
                callback.onComplete(false, "当前 Clash 版本不支持外部启动入口");
            } catch (Exception error) {
                callback.onComplete(false, "Clash 启动请求失败：" + safeMessage(error));
            }
        }, 900);
    }

    private static void sendTailscaleBroadcast(Context context, String action, Intent extras) {
        Intent intent = extras == null ? new Intent(action) : extras;
        intent.setClassName(TAILSCALE_PACKAGE, TAILSCALE_RECEIVER);
        context.sendBroadcast(intent);
    }

    private static void launchClashControl(Activity activity, String action) {
        Intent intent = new Intent(action)
                .setClassName(CLASH_PACKAGE, CLASH_ACTIVITY)
                .addFlags(Intent.FLAG_ACTIVITY_NO_ANIMATION);
        activity.startActivity(intent);
    }

    private static boolean isInstalled(Context context, String packageName) {
        try {
            // The legacy overload remains available on every supported Android version.
            context.getPackageManager().getPackageInfo(packageName, 0);
            return true;
        } catch (PackageManager.NameNotFoundException error) {
            return false;
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.isEmpty() ? error.getClass().getSimpleName() : message;
    }
}
