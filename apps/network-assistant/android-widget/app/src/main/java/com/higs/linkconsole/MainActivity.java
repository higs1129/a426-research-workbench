package com.higs.linkconsole;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.view.Window;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final long CODEX_MAX_FRESH_AGE_MS = 2L * 60L * 1000L;
    private TextView currentMode;
    private TextView currentRoute;
    private TextView currentLatency;
    private TextView updatedAt;
    private TextView tailscaleStatus;
    private TextView tailscaleDetail;
    private TextView udpProbeStatus;
    private TextView udpProbeDetail;
    private TextView remoteStatus;
    private TextView remoteDetail;
    private TextView clashStatus;
    private TextView clashDetail;
    private TextView actionStatus;
    private TextView diagnosticNote;
    private TextView codexAccessStatus;
    private TextView codexLatestStatus;
    private TextView codexWatchStatus;
    private EditText clashSecret;
    private Switch clashAutoSelectionSwitch;
    private Switch codexWatchAlertSwitch;
    private Button refreshButton;
    private Button switchTailscaleButton;
    private Button switchClashButton;
    private Button udpProbeButton;
    private Button enableNotificationAccessButton;
    private Button codexRefreshButton;
    private Button codexWatchTestButton;
    private boolean refreshRunning;
    private boolean udpProbeRunning;
    private static final int REQUEST_POST_NOTIFICATIONS = 910;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        window.setStatusBarColor(Color.rgb(7, 19, 27));
        window.setNavigationBarColor(Color.rgb(7, 19, 27));
        setContentView(R.layout.activity_main);
        bindViews();
        clashAutoSelectionSwitch.setChecked(WidgetState.isClashAutoSelectionEnabled(this));
        codexWatchAlertSwitch.setChecked(CodexCompletionNotifier.isEnabled(this));
        wireActions();

        String savedSecret = WidgetState.getClashSecret(this);
        if (!savedSecret.isEmpty()) clashSecret.setText(savedSecret);
        render(WidgetState.load(this));
        updateNotificationAccessUi();
        refresh();

        if (getIntent().getBooleanExtra("open_notification_access", false)
                && !NotificationAccess.isGranted(this)) {
            enableNotificationAccessButton.post(() -> NotificationAccess.openSettings(this));
        }
    }

    private void bindViews() {
        currentMode = findViewById(R.id.currentMode);
        currentRoute = findViewById(R.id.currentRoute);
        currentLatency = findViewById(R.id.currentLatency);
        updatedAt = findViewById(R.id.updatedAt);
        tailscaleStatus = findViewById(R.id.tailscaleStatus);
        tailscaleDetail = findViewById(R.id.tailscaleDetail);
        udpProbeStatus = findViewById(R.id.udpProbeStatus);
        udpProbeDetail = findViewById(R.id.udpProbeDetail);
        remoteStatus = findViewById(R.id.remoteStatus);
        remoteDetail = findViewById(R.id.remoteDetail);
        clashStatus = findViewById(R.id.clashStatus);
        clashDetail = findViewById(R.id.clashDetail);
        actionStatus = findViewById(R.id.actionStatus);
        diagnosticNote = findViewById(R.id.diagnosticNote);
        codexAccessStatus = findViewById(R.id.codexAccessStatus);
        codexLatestStatus = findViewById(R.id.codexLatestStatus);
        codexWatchStatus = findViewById(R.id.codexWatchStatus);
        clashSecret = findViewById(R.id.clashSecret);
        clashAutoSelectionSwitch = findViewById(R.id.clashAutoSelectionSwitch);
        codexWatchAlertSwitch = findViewById(R.id.codexWatchAlertSwitch);
        refreshButton = findViewById(R.id.refreshButton);
        switchTailscaleButton = findViewById(R.id.switchTailscaleButton);
        switchClashButton = findViewById(R.id.switchClashButton);
        udpProbeButton = findViewById(R.id.udpProbeButton);
        enableNotificationAccessButton = findViewById(R.id.enableNotificationAccessButton);
        codexRefreshButton = findViewById(R.id.codexRefreshButton);
        codexWatchTestButton = findViewById(R.id.codexWatchTestButton);
    }

    private void wireActions() {
        refreshButton.setOnClickListener(view -> refresh());
        findViewById(R.id.saveSecretButton).setOnClickListener(view -> {
            String secret = clashSecret.getText().toString().trim();
            WidgetState.setClashSecret(this, secret);
            actionStatus.setText(secret.isEmpty() ? "Secret 已清除" : "Secret 已仅保存到这台手机");
            refresh();
        });
        switchTailscaleButton.setOnClickListener(view -> switchToTailscale());
        switchClashButton.setOnClickListener(view -> switchToClash());
        udpProbeButton.setOnClickListener(view -> runUdpProbe());
        clashAutoSelectionSwitch.setOnCheckedChangeListener((button, checked) -> {
            WidgetState.setClashAutoSelectionEnabled(this, checked);
            actionStatus.setText(checked
                    ? "下次切换 Clash 时将启用自动选择"
                    : "下次切换 Clash 时将保留上次节点");
        });
        enableNotificationAccessButton.setOnClickListener(
                view -> NotificationAccess.openSettings(this));
        codexRefreshButton.setOnClickListener(view -> refreshCodexTasks());
        codexWatchAlertSwitch.setOnCheckedChangeListener((button, checked) -> {
            CodexCompletionNotifier.setEnabled(this, checked);
            updateWatchAlertUi();
        });
        codexWatchTestButton.setOnClickListener(view -> sendWatchTestNotification());
    }

    @Override
    protected void onResume() {
        super.onResume();
        NetworkWidgetProvider.updateAll(this);
        if (codexAccessStatus != null) {
            updateNotificationAccessUi();
            updateWatchAlertUi();
            refreshCodexTasks();
        }
    }

    private void updateNotificationAccessUi() {
        boolean granted = NotificationAccess.isGranted(this);
        if (granted) {
            enableNotificationAccessButton.setText("管理通知使用权");
            NotificationAccess.requestRebind(this);
        } else {
            enableNotificationAccessButton.setText("授予通知使用权");
        }
        renderCodexTasks(CodexTaskRepository.load(this));
        CodexWidgetProvider.updateAll(this);
    }

    private void updateWatchAlertUi() {
        codexWatchStatus.setText(CodexCompletionNotifier.statusText(this));
    }

    private void sendWatchTestNotification() {
        if (Build.VERSION.SDK_INT >= 33
                && !CodexCompletionNotifier.hasRuntimePermission(this)) {
            codexWatchStatus.setText("请先允许链路助手发送通知，授权后会自动发送测试提醒");
            requestPermissions(
                    new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    REQUEST_POST_NOTIFICATIONS);
            return;
        }
        boolean sent = CodexCompletionNotifier.sendTest(this);
        codexWatchStatus.setText(sent
                ? "测试通知已发送；若手机已收到但手表未震动，请在 vivo 健康中勾选链路助手"
                : CodexCompletionNotifier.statusText(this));
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_POST_NOTIFICATIONS) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            sendWatchTestNotification();
        } else {
            updateWatchAlertUi();
        }
    }

    private void refreshCodexTasks() {
        codexRefreshButton.setEnabled(false);
        codexRefreshButton.setText("正在同步…");
        CodexTaskRepository.refresh(this, snapshot -> runOnUiThread(() -> {
            codexRefreshButton.setEnabled(true);
            codexRefreshButton.setText("刷新 A426 任务状态");
            renderCodexTasks(snapshot);
        }));
    }

    private void renderCodexTasks(CodexTaskSnapshot snapshot) {
        if (!snapshot.available) {
            boolean granted = NotificationAccess.isGranted(this);
            CodexState notification = CodexState.load(this);
            codexAccessStatus.setText(granted ? "等待 A426 任务状态" : "尚未授予通知使用权");
            codexLatestStatus.setText(granted
                    ? notification.title + " · " + notification.text
                    : "先连接 Tailscale 同步任务；通知权限用于辅助识别状态和触发刷新。");
            return;
        }

        if (!snapshot.isFresh(CODEX_MAX_FRESH_AGE_MS)) {
            codexAccessStatus.setText("A426 状态待同步");
            codexLatestStatus.setText(snapshot.error.isEmpty()
                    ? "任务状态已超过 2 分钟，旧的运行状态已隐藏。"
                    : snapshot.error + "\n旧的运行状态已隐藏。" );
            return;
        }

        codexAccessStatus.setText(snapshot.summary());
        StringBuilder details = new StringBuilder();
        int shown = Math.min(snapshot.tasks.size(), 5);
        for (int index = 0; index < shown; index++) {
            CodexTaskSnapshot.Task task = snapshot.tasks.get(index);
            if (details.length() > 0) details.append('\n');
            details.append(statusSymbol(task.status)).append(' ')
                    .append(task.name).append(" · ").append(statusText(task.status));
        }
        if (details.length() == 0) details.append("A426 已同步，当前没有任务变化。");
        if (!snapshot.error.isEmpty()) details.append("\n").append(snapshot.error);
        if (!NotificationAccess.isGranted(this)) {
            details.append("\n通知权限未开启：组件仍能显示任务并尝试打开 ChatGPT Remote。");
        }
        codexLatestStatus.setText(details.toString());
    }

    private String statusText(String status) {
        if ("running".equals(status)) return "运行中";
        if ("completed".equals(status)) return "已完成";
        return "已停止";
    }

    private String statusSymbol(String status) {
        if ("running".equals(status)) return "●";
        if ("completed".equals(status)) return "✓";
        return "!";
    }

    private void refresh() {
        if (refreshRunning) return;
        refreshRunning = true;
        refreshButton.setEnabled(false);
        refreshButton.setText("正在检测…");
        actionStatus.setText("正在识别当前 VPN 与真实网络路径");
        NetworkRepository.refresh(this, snapshot -> runOnUiThread(() -> {
            refreshRunning = false;
            refreshButton.setEnabled(true);
            refreshButton.setText("重新检测");
            render(snapshot);
            actionStatus.setText("检测完成");
        }));
    }

    private void switchToTailscale() {
        setSwitchButtonsEnabled(false);
        VpnSwitcher.switchToTailscale(this, new VpnSwitcher.Callback() {
            @Override
            public void onProgress(String message) {
                runOnUiThread(() -> actionStatus.setText(message));
            }

            @Override
            public void onComplete(boolean success, String message) {
                runOnUiThread(() -> {
                    actionStatus.setText(message);
                    setSwitchButtonsEnabled(true);
                    if (success) refresh();
                });
            }
        });
    }

    private void switchToClash() {
        setSwitchButtonsEnabled(false);
        VpnSwitcher.switchToClash(this, new VpnSwitcher.Callback() {
            @Override
            public void onProgress(String message) {
                runOnUiThread(() -> actionStatus.setText(message));
            }

            @Override
            public void onComplete(boolean success, String message) {
                runOnUiThread(() -> {
                    actionStatus.setText(message);
                    setSwitchButtonsEnabled(true);
                    if (success) refresh();
                });
            }
        });
    }

    private void runUdpProbe() {
        if (udpProbeRunning) return;
        udpProbeRunning = true;
        udpProbeButton.setEnabled(false);
        udpProbeButton.setText("正在发送…");
        udpProbeStatus.setText("正在绑定手机物理网络");
        udpProbeDetail.setText("测试包将绕过当前 Tailscale 或 Clash VPN，直接发往群晖 UDP 40000。");

        UdpProbe.send(this, result -> runOnUiThread(() -> {
            udpProbeRunning = false;
            udpProbeButton.setEnabled(true);
            udpProbeButton.setText("发送 UDP 测试包");
            udpProbeStatus.setText(result.status);
            udpProbeDetail.setText(result.detail);
            udpProbeStatus.setTextColor(getColor(result.success
                    ? R.color.cyan
                    : R.color.amber));
        }));
    }

    private void setSwitchButtonsEnabled(boolean enabled) {
        switchTailscaleButton.setEnabled(enabled);
        switchClashButton.setEnabled(enabled);
    }

    private void render(NetworkSnapshot snapshot) {
        currentMode.setText(snapshot.modeLabel());
        currentRoute.setText(snapshot.currentRoute);
        currentLatency.setText(snapshot.latencyLabel());
        updatedAt.setText(formatTime(snapshot.updatedAt));
        tailscaleStatus.setText(snapshot.tailscaleStatus);
        tailscaleDetail.setText(snapshot.tailscaleDetail);
        remoteStatus.setText(snapshot.remoteStatus);
        remoteDetail.setText(snapshot.remoteDetail);
        clashStatus.setText(snapshot.clashStatus);
        clashDetail.setText(snapshot.clashDetail);
        diagnosticNote.setText(TextUtils.isEmpty(snapshot.note)
                ? "桌面组件显示最近一次检测结果；点击组件即可进入这里刷新或切换。"
                : snapshot.note);

        int accent;
        switch (snapshot.mode) {
            case TAILSCALE:
                accent = getColor(R.color.cyan);
                break;
            case CLASH:
                accent = getColor(R.color.violet);
                break;
            case NONE:
                accent = getColor(R.color.amber);
                break;
            default:
                accent = getColor(R.color.text_secondary);
                break;
        }
        currentMode.setTextColor(accent);
    }

    private String formatTime(long timestamp) {
        if (timestamp <= 0) return "尚未检测";
        return new SimpleDateFormat("MM-dd HH:mm:ss", Locale.CHINA).format(new Date(timestamp));
    }
}
