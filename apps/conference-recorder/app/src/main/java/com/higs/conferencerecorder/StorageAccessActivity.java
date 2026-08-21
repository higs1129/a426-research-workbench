package com.higs.conferencerecorder;

import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.higs.conferencerecorder.data.PackageExporter;
import com.higs.conferencerecorder.data.StorageTargetStore;

public final class StorageAccessActivity extends BaseActivity {
    private static final int REQUEST_TREE = 2001;

    private TextView statePill;
    private TextView pathView;
    private TextView lastExportView;
    private TextView testButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout content = createScreen("存储与同步", "手机写入 · Synology Drive 上传", true);

        LinearLayout topology = UiKit.card(this);
        topology.setBackground(UiKit.roundRect(UiKit.INK, 20, this));
        topology.addView(UiKit.eyebrow(this, "LOCAL OUTBOX"));
        TextView title = UiKit.text(this, "选择 vivo-synology 根目录", 22,
                Color.WHITE, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 8);
        topology.addView(title, titleParams);
        TextView description = UiKit.text(
                this,
                "App 会在所选目录内创建 ConferenceRecorder；Synology Drive 再把它单向上传到群晖。",
                14,
                Color.rgb(203, 220, 223),
                false);
        LinearLayout.LayoutParams descriptionParams = UiKit.matchWrap();
        descriptionParams.topMargin = UiKit.dp(this, 8);
        topology.addView(description, descriptionParams);
        content.addView(topology);

        content.addView(UiKit.sectionTitle(this, "当前授权"));
        LinearLayout status = UiKit.card(this);
        statePill = UiKit.pill(this, "检查中", UiKit.TEXT_SECONDARY,
                Color.rgb(238, 241, 239));
        status.addView(statePill);
        pathView = UiKit.text(this, "尚未选择", 16, UiKit.TEXT_PRIMARY, true);
        status.addView(pathView);
        TextView choose = UiKit.button(this, "选择或更换同步根目录", true);
        choose.setOnClickListener(view -> chooseTree());
        status.addView(choose);
        content.addView(status);

        content.addView(UiKit.sectionTitle(this, "写入测试"));
        LinearLayout test = UiKit.card(this);
        test.addView(UiKit.text(
                this,
                "生成一个唯一测试包，不覆盖任何旧文件。随后可在 Synology Drive 和群晖中确认是否出现。",
                14,
                UiKit.TEXT_SECONDARY,
                false));
        testButton = UiKit.button(this, "写入连接测试包", false);
        testButton.setOnClickListener(view -> writeTestPackage());
        test.addView(testButton);
        lastExportView = UiKit.text(this, "", 12, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams lastParams = UiKit.matchWrap();
        lastParams.topMargin = UiKit.dp(this, 10);
        test.addView(lastExportView, lastParams);
        content.addView(test);

        content.addView(UiKit.sectionTitle(this, "状态含义"));
        LinearLayout meanings = UiKit.card(this);
        addMeaning(meanings, "写入成功", "只说明报告包已进入手机同步目录");
        meanings.addView(UiKit.divider(this));
        addMeaning(meanings, "等待 Drive", "Synology Drive 尚未确认上传完成");
        meanings.addView(UiKit.divider(this));
        addMeaning(meanings, "群晖已收到", "需由 Drive 或未来的群晖检查流程确认");
        meanings.addView(UiKit.divider(this));
        addMeaning(meanings, "A426 已处理", "电脑从 W: 只读并生成易读结果");
        content.addView(meanings);

        LinearLayout boundary = UiKit.card(this);
        boundary.setBackground(UiKit.roundRect(UiKit.WARNING_SOFT, 18, this));
        boundary.addView(UiKit.text(this, "不会直接写入 W 盘", 16, UiKit.WARNING, true));
        boundary.addView(UiKit.text(
                this,
                "手机只写自己的同步目录；群晖是原始资料源，A426 后续仅从 W: 读取。",
                13,
                UiKit.TEXT_PRIMARY,
                false));
        content.addView(boundary);
        renderState();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (statePill != null) renderState();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_TREE || resultCode != RESULT_OK || data == null) return;
        Uri treeUri = data.getData();
        if (treeUri == null) return;
        int grantedFlags = data.getFlags();
        boolean canRead = (grantedFlags & Intent.FLAG_GRANT_READ_URI_PERMISSION) != 0;
        boolean canWrite = (grantedFlags & Intent.FLAG_GRANT_WRITE_URI_PERMISSION) != 0;
        if (!canRead || !canWrite) {
            Toast.makeText(this, "所选目录没有提供完整读写授权", Toast.LENGTH_LONG).show();
            return;
        }
        try {
            getContentResolver().takePersistableUriPermission(
                    treeUri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            StorageTargetStore.saveTarget(this, treeUri);
            renderState();
            Toast.makeText(this, "同步根目录授权已保存", Toast.LENGTH_SHORT).show();
        } catch (SecurityException error) {
            Toast.makeText(this, "无法保留目录写入授权，请重新选择", Toast.LENGTH_LONG).show();
        }
    }

    private void chooseTree() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_TREE);
    }

    private void writeTestPackage() {
        if (!StorageTargetStore.isConfigured(this)) {
            chooseTree();
            return;
        }
        setTestRunning(true);
        new Thread(() -> {
            try {
                PackageExporter.ExportResult result = PackageExporter.writeConnectionTest(this);
                runOnUiThread(() -> {
                    setTestRunning(false);
                    renderState();
                    Toast.makeText(
                            this,
                            "已写入手机目录，等待 Synology Drive 上传",
                            Toast.LENGTH_LONG).show();
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    setTestRunning(false);
                    Toast.makeText(this, "写入失败：" + error.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }, "conference-storage-test").start();
    }

    private void renderState() {
        boolean configured = StorageTargetStore.isConfigured(this);
        statePill.setText(configured ? "可写目录已授权" : "尚未配置");
        statePill.setTextColor(configured ? UiKit.ACCENT : UiKit.WARNING);
        statePill.setBackground(UiKit.roundRect(
                configured ? UiKit.ACCENT_SOFT : UiKit.WARNING_SOFT, 999, this));
        pathView.setText(StorageTargetStore.displayPath(this));
        lastExportView.setText(getString(
                R.string.storage_last_export,
                StorageTargetStore.lastExport(this)));
        testButton.setAlpha(configured ? 1f : 0.6f);
    }

    private void setTestRunning(boolean running) {
        testButton.setEnabled(!running);
        testButton.setText(running ? "正在写入……" : "写入连接测试包");
    }

    private void addMeaning(LinearLayout parent, String label, String detail) {
        LinearLayout row = UiKit.horizontal(this);
        row.addView(UiKit.text(this, label, 14, UiKit.TEXT_PRIMARY, true), UiKit.weight(0.34f));
        row.addView(UiKit.text(this, detail, 13, UiKit.TEXT_SECONDARY, false), UiKit.weight(0.66f));
        parent.addView(row);
    }
}
