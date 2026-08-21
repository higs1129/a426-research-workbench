package com.higs.conferencerecorder;

import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.higs.conferencerecorder.data.ActiveConferenceStore;
import com.higs.conferencerecorder.data.ConferenceImportStore;
import com.higs.conferencerecorder.data.ConferenceRepository;
import com.higs.conferencerecorder.data.ConferenceStore;
import com.higs.conferencerecorder.data.StorageTargetStore;
import com.higs.conferencerecorder.model.Conference;

import org.json.JSONException;

import java.io.IOException;
import java.util.HashSet;
import java.util.Set;

public final class MeetingManagementActivity extends BaseActivity {
    private static final int REQUEST_CONFERENCE_JSON = 4102;

    private TextView storageState;
    private TextView storagePath;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ConferenceRepository repository = ConferenceStore.get(this);
        Conference active = ActiveConferenceStore.active(this, repository);
        LinearLayout content = createScreen("会议管理", "低频配置与数据入口", true);

        content.addView(UiKit.sectionTitle(this, "切换当前会议"));
        for (Conference conference : repository.conferences()) {
            content.addView(conferenceChoiceCard(conference,
                    active != null && active.id.equals(conference.id)));
        }

        content.addView(UiKit.sectionTitle(this, "导入或更新会议"));
        content.addView(importCard(repository));

        content.addView(UiKit.sectionTitle(this, "同步与导出目录"));
        content.addView(storageCard());

        content.addView(UiKit.sectionTitle(this, "帮助"));
        LinearLayout help = UiKit.card(this);
        TextView architecture = UiKit.button(this, "查看数据结构与边界", false);
        architecture.setOnClickListener(view -> open(ArchitectureActivity.class, null));
        help.addView(architecture);
        content.addView(help);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (storageState != null) renderStorageState();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_CONFERENCE_JSON || resultCode != RESULT_OK || data == null) {
            return;
        }
        Uri uri = data.getData();
        if (uri == null) return;

        ConferenceRepository current = ConferenceStore.get(this);
        Set<String> existingIds = new HashSet<>();
        for (Conference conference : current.conferences()) existingIds.add(conference.id);
        try {
            ConferenceImportStore.ImportResult result =
                    ConferenceImportStore.importFromUri(this, uri, existingIds);
            ConferenceStore.reload(this);
            Toast.makeText(this, result.summary(), Toast.LENGTH_LONG).show();
            recreate();
        } catch (IOException | JSONException error) {
            new AlertDialog.Builder(this)
                    .setTitle("无法导入会议 JSON")
                    .setMessage(error.getMessage() == null
                            ? "文件读取或格式校验失败" : error.getMessage())
                    .setPositiveButton("知道了", null)
                    .show();
        }
    }

    private LinearLayout conferenceChoiceCard(Conference conference, boolean active) {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card);
        card.setOnClickListener(view -> {
            ActiveConferenceStore.setActive(this, conference.id);
            Toast.makeText(this, "已切换到“" + conference.title + "”", Toast.LENGTH_SHORT).show();
            recreate();
        });
        LinearLayout top = UiKit.horizontal(this);
        top.addView(UiKit.text(this, conference.title, 17,
                UiKit.TEXT_PRIMARY, true), UiKit.weight(1f));
        top.addView(UiKit.pill(this, active ? "当前会议" : "设为当前",
                active ? UiKit.ACCENT : UiKit.TEXT_SECONDARY,
                active ? UiKit.ACCENT_SOFT : Color.rgb(238, 241, 239)));
        card.addView(top);
        TextView meta = UiKit.text(this,
                conference.dateRange + " · " + conference.talkCount + " 场报告 · "
                        + conference.posterCount + " 张海报",
                13, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams metaParams = UiKit.matchWrap();
        metaParams.topMargin = UiKit.dp(this, 6);
        card.addView(meta, metaParams);
        return card;
    }

    private LinearLayout importCard(ConferenceRepository repository) {
        LinearLayout card = UiKit.card(this);
        card.addView(UiKit.text(this,
                "新 ID 会新增会议，相同 ID 会更新日程；录音和照片不受影响。",
                13, UiKit.TEXT_SECONDARY, false));
        TextView source = UiKit.text(this,
                "当前数据：" + repository.loadedAssetName(),
                12, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams sourceParams = UiKit.matchWrap();
        sourceParams.topMargin = UiKit.dp(this, 9);
        card.addView(source, sourceParams);
        TextView choose = UiKit.button(this, "选择会议 JSON", true);
        choose.setOnClickListener(view -> chooseConferenceJson());
        card.addView(choose);
        return card;
    }

    private LinearLayout storageCard() {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card);
        card.setOnClickListener(view -> open(StorageAccessActivity.class, null));
        LinearLayout top = UiKit.horizontal(this);
        top.addView(UiKit.text(this, "Synology 同步目录", 17,
                UiKit.TEXT_PRIMARY, true), UiKit.weight(1f));
        storageState = UiKit.pill(this, "检查中", UiKit.TEXT_SECONDARY,
                Color.rgb(238, 241, 239));
        top.addView(storageState);
        card.addView(top);
        storagePath = UiKit.text(this, "尚未选择", 13, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams pathParams = UiKit.matchWrap();
        pathParams.topMargin = UiKit.dp(this, 7);
        card.addView(storagePath, pathParams);
        return card;
    }

    private void renderStorageState() {
        boolean configured = StorageTargetStore.isConfigured(this);
        storageState.setText(configured ? "已授权" : "导出时再配置");
        storageState.setTextColor(configured ? UiKit.ACCENT : UiKit.WARNING);
        storageState.setBackground(UiKit.roundRect(
                configured ? UiKit.ACCENT_SOFT : UiKit.WARNING_SOFT, 999, this));
        storagePath.setText(configured
                ? StorageTargetStore.displayPath(this)
                : "尚未选择；第一次导出报告包时也会引导授权");
    }

    private void chooseConferenceJson() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                "application/json", "text/json", "text/plain", "application/octet-stream"
        });
        startActivityForResult(intent, REQUEST_CONFERENCE_JSON);
    }
}
