package com.higs.conferencerecorder;

import android.Manifest;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ClipData;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.text.TextUtils;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;
import androidx.core.content.ContextCompat;

import com.higs.conferencerecorder.data.CaptureSessionStore;
import com.higs.conferencerecorder.data.ConferenceRepository;
import com.higs.conferencerecorder.data.ConferenceStore;
import com.higs.conferencerecorder.data.PackageExporter;
import com.higs.conferencerecorder.data.ReportPackageStore;
import com.higs.conferencerecorder.data.StorageTargetStore;
import com.higs.conferencerecorder.data.TranscriptStore;
import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;
import com.higs.conferencerecorder.transcription.SystemAudioTranscriber;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class PackageActivity extends BaseActivity {
    public static final String EXTRA_CONFERENCE_ID = "conference_id";
    public static final String EXTRA_SESSION_ID = "session_id";
    public static final String EXTRA_ITEM_ID = "item_id";

    private static final int REQUEST_AUDIO_PERMISSION = 3101;
    private static final int REQUEST_CAPTURE_PHOTO = 3102;
    private static final String STATE_PENDING_PHOTO = "pending_photo";

    private ProgramItem item;
    private Conference conference;
    private SessionBlock session;
    private EditText noteEditor;
    private TextView recordButton;
    private TextView stopButton;
    private TextView recordState;
    private TextView recordTimer;
    private TextView photoButton;
    private TextView exportButton;
    private TextView exportStatus;
    private TextView audioStatus;
    private TextView imageStatus;
    private TextView noteStatus;
    private TextView transcriptMaterialStatus;
    private TextView captureHint;
    private TextView transcriptionStatus;
    private TextView transcriptionPreview;
    private TextView transcriptionButton;
    private TextView materialsSummary;
    private TextView materialsToggleLabel;
    private LinearLayout capturedMediaList;
    private LinearLayout materialsContainer;
    private File pendingPhotoFile;
    private boolean receiverRegistered;
    private boolean exportRunning;
    private boolean materialsExpanded;
    private boolean transcriptionRunning;
    private SystemAudioTranscriber audioTranscriber;
    private final Handler timerHandler = new Handler(Looper.getMainLooper());
    private final Runnable timerTick = new Runnable() {
        @Override
        public void run() {
            renderRecordingTimer();
            timerHandler.postDelayed(this, 1000L);
        }
    };

    private final BroadcastReceiver recordingReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent.getBooleanExtra("live_update", false)) {
                CaptureSessionStore.CaptureBundle capture = captureBundle(false);
                File[] audioFiles = capture == null ? new File[0] : capture.audioFiles();
                renderTranscriptionState(capture, audioFiles);
                return;
            }
            renderCaptureState();
            renderExportState();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String conferenceId = value(EXTRA_CONFERENCE_ID);
        String sessionId = value(EXTRA_SESSION_ID);
        String itemId = value(EXTRA_ITEM_ID);
        ConferenceRepository repository = ConferenceStore.get(this);
        conference = repository.conference(conferenceId);
        session = repository.session(conferenceId, sessionId);
        item = repository.item(conferenceId, itemId);
        if (conference == null || item == null) {
            finish();
            return;
        }
        if (savedInstanceState != null) {
            String pendingPath = savedInstanceState.getString(STATE_PENDING_PHOTO, "");
            if (!pendingPath.isEmpty()) pendingPhotoFile = new File(pendingPath);
        }

        String packageType = item.isPoster() ? "海报记录" : "报告记录";
        LinearLayout content = createScreen(packageType, conference.title, true);
        content.addView(buildIdentityCard());
        content.addView(UiKit.sectionTitle(this, "现场记录"));
        content.addView(buildCaptureCard());
        if (!item.isPoster()) content.addView(buildPhotoCard());
        if (!item.isPoster()) content.addView(buildTranscriptionCard());
        content.addView(UiKit.sectionTitle(this, "快速备注"));
        content.addView(buildNoteCard());
        content.addView(UiKit.sectionTitle(this, "下一步"));
        content.addView(buildExportCard());
        content.addView(buildMaterialsToggle());
        materialsContainer = buildMaterialsContainer();
        materialsContainer.setVisibility(View.GONE);
        content.addView(materialsContainer);
        renderCaptureState();
        renderExportState();
    }

    @Override
    protected void onStart() {
        super.onStart();
        IntentFilter filter = new IntentFilter(AudioRecordingService.ACTION_STATE_CHANGED);
        ContextCompat.registerReceiver(
                this,
                recordingReceiver,
                filter,
                ContextCompat.RECEIVER_NOT_EXPORTED);
        receiverRegistered = true;
        renderCaptureState();
        timerHandler.removeCallbacks(timerTick);
        timerHandler.post(timerTick);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (exportButton != null) renderExportState();
        if (capturedMediaList != null) renderCaptureState();
    }

    @Override
    protected void onPause() {
        if (noteEditor != null && item != null) saveNote();
        super.onPause();
    }

    @Override
    protected void onStop() {
        if (receiverRegistered) {
            unregisterReceiver(recordingReceiver);
            receiverRegistered = false;
        }
        timerHandler.removeCallbacks(timerTick);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        if (audioTranscriber != null) {
            audioTranscriber.close();
            audioTranscriber = null;
        }
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        super.onDestroy();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        if (pendingPhotoFile != null) {
            outState.putString(STATE_PENDING_PHOTO, pendingPhotoFile.getAbsolutePath());
        }
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_CAPTURE_PHOTO) return;
        if (pendingPhotoFile != null
                && pendingPhotoFile.isFile()
                && pendingPhotoFile.length() > 0L) {
            Toast.makeText(this, "照片已加入当前报告包", Toast.LENGTH_SHORT).show();
        } else {
            if (pendingPhotoFile != null
                    && pendingPhotoFile.exists()
                    && pendingPhotoFile.length() == 0L) {
                pendingPhotoFile.delete();
            }
            Toast.makeText(this, "本次拍摄未保存", Toast.LENGTH_SHORT).show();
        }
        pendingPhotoFile = null;
        renderCaptureState();
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_AUDIO_PERMISSION) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED) {
            startNewAudioSegment();
        } else {
            Toast.makeText(this, "需要麦克风权限才能记录报告", Toast.LENGTH_LONG).show();
        }
    }

    private LinearLayout buildIdentityCard() {
        LinearLayout identity = UiKit.card(this);
        identity.addView(UiKit.pill(
                this,
                item.isPosterSession()
                        ? "POSTER SESSION"
                        : (item.isPoster() ? "POSTER PACKAGE" : "TALK PACKAGE"),
                item.isPoster() ? UiKit.CORAL : UiKit.ACCENT,
                item.isPoster() ? UiKit.CORAL_SOFT : UiKit.ACCENT_SOFT));
        TextView title = UiKit.text(this, item.title, 22, UiKit.TEXT_PRIMARY, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 6);
        identity.addView(title, titleParams);
        if (!item.personLine().isEmpty()) {
            TextView person = UiKit.text(this, item.personLine(), 14,
                    UiKit.TEXT_SECONDARY, false);
            LinearLayout.LayoutParams personParams = UiKit.matchWrap();
            personParams.topMargin = UiKit.dp(this, 9);
            identity.addView(person, personParams);
        }
        String contextLine = item.isPoster() && !item.isPosterSession()
                ? (item.code.isEmpty() ? "海报编号待定" : item.code)
                : item.timeRange() + (session == null ? "" : " · " + session.title);
        TextView context = UiKit.text(this, contextLine, 13, UiKit.ACCENT, true);
        LinearLayout.LayoutParams contextParams = UiKit.matchWrap();
        contextParams.topMargin = UiKit.dp(this, 11);
        identity.addView(context, contextParams);
        return identity;
    }

    private LinearLayout buildCaptureCard() {
        LinearLayout capture = UiKit.card(this);
        if (!item.isPoster()) {
            capture.setBackground(UiKit.roundRect(UiKit.INK, 20, this));
            recordState = UiKit.text(this, "准备记录", 13,
                    Color.rgb(202, 218, 221), true);
            recordState.setGravity(Gravity.CENTER);
            capture.addView(recordState);
            recordTimer = UiKit.text(this, "00:00:00", 36, Color.WHITE, true);
            recordTimer.setGravity(Gravity.CENTER);
            LinearLayout.LayoutParams timerParams = UiKit.matchWrap();
            timerParams.topMargin = UiKit.dp(this, 7);
            capture.addView(recordTimer, timerParams);

            LinearLayout recordingRow = UiKit.horizontal(this);
            LinearLayout.LayoutParams recordingParams = UiKit.matchWrap();
            recordingParams.topMargin = UiKit.dp(this, 13);
            recordingRow.setLayoutParams(recordingParams);
            recordButton = captureAction(
                    "开始录音",
                    "主操作",
                    UiKit.ACCENT,
                    Color.WHITE);
            recordButton.setOnClickListener(view -> handleRecordAction());
            LinearLayout.LayoutParams recordParams = UiKit.weight(1f);
            recordParams.setMarginEnd(UiKit.dp(this, 7));
            recordingRow.addView(recordButton, recordParams);

            stopButton = captureAction(
                    "结束本段",
                    "保存 M4A",
                    Color.rgb(50, 72, 81),
                    Color.WHITE);
            stopButton.setOnClickListener(view -> stopRecording());
            LinearLayout.LayoutParams stopParams = UiKit.weight(1f);
            stopParams.setMarginStart(UiKit.dp(this, 7));
            recordingRow.addView(stopButton, stopParams);
            capture.addView(recordingRow);
            captureHint = UiKit.text(this,
                    "录音会保存在 App 暂存区；打开相机时录音继续。",
                    12, Color.rgb(202, 218, 221), false);
            captureHint.setGravity(Gravity.CENTER);
            LinearLayout.LayoutParams hintParams = UiKit.matchWrap();
            hintParams.topMargin = UiKit.dp(this, 12);
            capture.addView(captureHint, hintParams);
        } else {
            capture.setBackground(UiKit.roundRect(UiKit.CORAL_SOFT, 20, this));
            capture.addView(UiKit.text(this,
                    "让海报完整入镜，再补拍关键图表和结论。",
                    14, UiKit.TEXT_PRIMARY, false));
            photoButton = captureAction(
                    "拍摄海报",
                    "可连续补拍细节",
                    UiKit.CORAL,
                    Color.WHITE);
            LinearLayout.LayoutParams photoParams = UiKit.matchWrap();
            photoParams.topMargin = UiKit.dp(this, 12);
            photoButton.setLayoutParams(photoParams);
            photoButton.setOnClickListener(view -> takePhoto());
            capture.addView(photoButton);
            captureHint = UiKit.text(this,
                    "照片先保存在 App 暂存区，导出时进入报告包。",
                    12, UiKit.TEXT_SECONDARY, false);
            LinearLayout.LayoutParams hintParams = UiKit.matchWrap();
            hintParams.topMargin = UiKit.dp(this, 10);
            capture.addView(captureHint, hintParams);
        }
        return capture;
    }

    private LinearLayout buildPhotoCard() {
        LinearLayout card = UiKit.card(this);
        LinearLayout top = UiKit.horizontal(this);
        top.addView(UiKit.text(this, "PPT 照片", 16,
                UiKit.TEXT_PRIMARY, true), UiKit.weight(1f));
        TextView hint = UiKit.text(this, "录音中可拍", 12, UiKit.TEXT_SECONDARY, false);
        top.addView(hint);
        card.addView(top);
        photoButton = UiKit.button(this, "拍摄 PPT", false);
        photoButton.setOnClickListener(view -> takePhoto());
        card.addView(photoButton);
        return card;
    }

    private LinearLayout buildTranscriptionCard() {
        LinearLayout card = UiKit.card(this);
        LinearLayout heading = UiKit.horizontal(this);
        heading.addView(UiKit.text(this, "英文实时字幕", 16,
                UiKit.TEXT_PRIMARY, true), UiKit.weight(1f));
        transcriptionStatus = UiKit.text(
                this, capabilityLabel(), 12, UiKit.TEXT_SECONDARY, false);
        heading.addView(transcriptionStatus);
        card.addView(heading);

        transcriptionPreview = UiKit.text(
                this,
                "开始录音后，这里会滚动显示系统识别出的英文；录音始终独立保存。",
                13,
                UiKit.TEXT_SECONDARY,
                false);
        transcriptionPreview.setTextIsSelectable(true);
        transcriptionPreview.setMaxLines(6);
        transcriptionPreview.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams previewParams = UiKit.matchWrap();
        previewParams.topMargin = UiKit.dp(this, 9);
        card.addView(transcriptionPreview, previewParams);

        transcriptionButton = UiKit.button(this, "重新转写已有录音", false);
        transcriptionButton.setOnClickListener(view -> requestTranscription());
        card.addView(transcriptionButton);
        return card;
    }

    private String capabilityLabel() {
        switch (SystemAudioTranscriber.availability(this)) {
            case ON_DEVICE:
                return "本机英文识别可用";
            case SYSTEM_MAY_USE_NETWORK:
                return "系统英文识别可用";
            case ANDROID_TOO_OLD:
                return "需要 Android 13+";
            default:
                return "系统识别不可用";
        }
    }

    private void requestTranscription() {
        if (isCurrentCaptureRecording()) {
            Toast.makeText(this, "请先结束录音，再转写已保存片段", Toast.LENGTH_LONG).show();
            return;
        }
        CaptureSessionStore.CaptureBundle capture = captureBundle(false);
        File[] audioFiles = capture == null ? new File[0] : capture.audioFiles();
        if (audioFiles.length == 0) {
            Toast.makeText(this, "当前报告还没有录音", Toast.LENGTH_LONG).show();
            return;
        }
        Runnable chooseEngine = () -> chooseTranscriptionEngine(capture, audioFiles);
        if (TranscriptStore.hasTranscript(capture)) {
            new AlertDialog.Builder(this)
                    .setTitle("重新转写当前录音？")
                    .setMessage("新结果会替换 App 暂存区里的旧逐字稿；已导出的不可变报告包不受影响。")
                    .setNegativeButton("取消", null)
                    .setPositiveButton("重新转写", (dialog, which) -> chooseEngine.run())
                    .show();
        } else {
            chooseEngine.run();
        }
    }

    private void chooseTranscriptionEngine(
            CaptureSessionStore.CaptureBundle capture, File[] audioFiles) {
        SystemAudioTranscriber.Availability availability =
                SystemAudioTranscriber.availability(this);
        if (availability == SystemAudioTranscriber.Availability.ON_DEVICE) {
            beginTranscription(capture, audioFiles, true);
        } else if (availability
                == SystemAudioTranscriber.Availability.SYSTEM_MAY_USE_NETWORK) {
            new AlertDialog.Builder(this)
                    .setTitle("系统识别可能联网")
                    .setMessage("这台手机没有向 App 提供可确认的离线识别器。继续后，录音数据可能由手机当前的系统语音服务处理。")
                    .setNegativeButton("取消", null)
                    .setPositiveButton("继续转写", (dialog, which) ->
                            beginTranscription(capture, audioFiles, false))
                    .show();
        } else if (availability == SystemAudioTranscriber.Availability.ANDROID_TOO_OLD) {
            Toast.makeText(
                    this,
                    "已有录音直接转写需要 Android 13 或更高版本",
                    Toast.LENGTH_LONG).show();
        } else {
            Toast.makeText(
                    this,
                    "没有检测到可供第三方 App 调用的系统识别服务",
                    Toast.LENGTH_LONG).show();
        }
    }

    private void beginTranscription(
            CaptureSessionStore.CaptureBundle capture,
            File[] audioFiles,
            boolean onDevice) {
        if (transcriptionRunning) return;
        transcriptionRunning = true;
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        renderCaptureState();
        transcriptionStatus.setText(onDevice ? "正在使用本机识别" : "正在使用系统识别");
        transcriptionPreview.setText("正在准备英文录音…");

        audioTranscriber = new SystemAudioTranscriber(
                this,
                audioFiles,
                transcriptionBiases(),
                onDevice,
                new SystemAudioTranscriber.Listener() {
                    @Override
                    public void onStatus(String status) {
                        transcriptionStatus.setText(status);
                    }

                    @Override
                    public void onPartial(String text) {
                        if (!text.isEmpty()) transcriptionPreview.setText(text);
                    }

                    @Override
                    public void onFinished(SystemAudioTranscriber.Result result) {
                        try {
                            TranscriptStore.save(capture, result, audioFiles);
                            Toast.makeText(
                                    PackageActivity.this,
                                    "逐字稿已保存，导出时会写入报告包",
                                    Toast.LENGTH_LONG).show();
                        } catch (IOException error) {
                            Toast.makeText(
                                    PackageActivity.this,
                                    "转写完成，但保存失败：" + error.getMessage(),
                                    Toast.LENGTH_LONG).show();
                        }
                        endTranscription();
                    }

                    @Override
                    public void onFailed(String message, String partialText) {
                        if (!partialText.isEmpty()) {
                            transcriptionPreview.setText(partialText);
                        }
                        Toast.makeText(PackageActivity.this, message, Toast.LENGTH_LONG).show();
                        endTranscription();
                    }
                });
        try {
            audioTranscriber.start();
        } catch (IOException error) {
            Toast.makeText(this, error.getMessage(), Toast.LENGTH_LONG).show();
            endTranscription();
        }
    }

    private List<String> transcriptionBiases() {
        ArrayList<String> values = new ArrayList<>();
        addBias(values, item.title);
        addBias(values, item.speaker);
        addBias(values, item.affiliation);
        addBias(values, "microcavity photonics");
        addBias(values, "lithium niobate");
        addBias(values, "optical quality factor");
        addBias(values, "stimulated Brillouin scattering");
        addBias(values, "whispering gallery mode");
        return values;
    }

    private static void addBias(List<String> values, String value) {
        if (value != null && !value.trim().isEmpty() && !values.contains(value.trim())) {
            values.add(value.trim());
        }
    }

    private void endTranscription() {
        transcriptionRunning = false;
        audioTranscriber = null;
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        renderCaptureState();
        renderExportState();
    }

    private LinearLayout buildStatusCard() {
        LinearLayout status = UiKit.card(this);
        if (!item.isPoster()) {
            audioStatus = UiKit.pill(this, "未采集", UiKit.TEXT_SECONDARY,
                    Color.rgb(238, 241, 239));
            status.addView(statusRow("原始录音", audioStatus));
            status.addView(UiKit.divider(this));
        }
        imageStatus = UiKit.pill(this, "0 张", UiKit.TEXT_SECONDARY,
                Color.rgb(238, 241, 239));
        status.addView(statusRow(item.isPoster() ? "海报照片" : "PPT 照片", imageStatus));
        status.addView(UiKit.divider(this));
        noteStatus = statusPill(noteState(), !noteState().equals("未填写"));
        status.addView(statusRow("现场备注", noteStatus));
        status.addView(UiKit.divider(this));
        transcriptMaterialStatus = statusPill(
                item.isPoster() ? "待生成" : "未生成", false);
        status.addView(statusRow(item.isPoster() ? "图像识别" : "逐字稿",
                transcriptMaterialStatus));
        status.addView(UiKit.divider(this));
        status.addView(statusRow("结构化内容", statusPill("待生成", false)));
        return status;
    }

    private LinearLayout buildMaterialsToggle() {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card);
        card.setOnClickListener(view -> toggleMaterials());
        LinearLayout top = UiKit.horizontal(this);
        top.addView(UiKit.text(this, "材料与报告包", 17,
                UiKit.TEXT_PRIMARY, true), UiKit.weight(1f));
        materialsToggleLabel = UiKit.text(this, "展开  ›", 13, UiKit.ACCENT, true);
        top.addView(materialsToggleLabel);
        card.addView(top);
        materialsSummary = UiKit.text(this, "正在检查材料…", 13,
                UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams summaryParams = UiKit.matchWrap();
        summaryParams.topMargin = UiKit.dp(this, 7);
        card.addView(materialsSummary, summaryParams);
        return card;
    }

    private LinearLayout buildMaterialsContainer() {
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setLayoutParams(UiKit.matchWrap());
        container.addView(buildStatusCard());
        capturedMediaList = UiKit.card(this);
        container.addView(capturedMediaList);
        container.addView(buildPathCard());
        return container;
    }

    private void toggleMaterials() {
        materialsExpanded = !materialsExpanded;
        materialsContainer.setVisibility(materialsExpanded ? View.VISIBLE : View.GONE);
        materialsToggleLabel.setText(materialsExpanded ? "收起  ⌃" : "展开  ›");
    }

    private LinearLayout buildNoteCard() {
        LinearLayout notes = UiKit.card(this);
        noteEditor = new EditText(this);
        noteEditor.setHint("例如：关键结论、值得追问的问题、与自己工作的联系……");
        noteEditor.setText(ReportPackageStore.loadNote(this, conference.id, item.id));
        noteEditor.setTextSize(15);
        noteEditor.setTextColor(UiKit.TEXT_PRIMARY);
        noteEditor.setHintTextColor(Color.rgb(144, 153, 157));
        noteEditor.setGravity(Gravity.TOP | Gravity.START);
        noteEditor.setMinLines(3);
        noteEditor.setPadding(
                UiKit.dp(this, 14), UiKit.dp(this, 13),
                UiKit.dp(this, 14), UiKit.dp(this, 13));
        noteEditor.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        android.graphics.drawable.GradientDrawable editorBackground = UiKit.roundRect(
                Color.rgb(248, 249, 247), 13, this);
        editorBackground.setStroke(UiKit.dp(this, 1), UiKit.LINE);
        noteEditor.setBackground(editorBackground);
        notes.addView(noteEditor, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        TextView save = UiKit.button(this, "保存备注", false);
        save.setOnClickListener(view -> {
            saveNote();
            renderCaptureState();
            Toast.makeText(this, "备注已保存", Toast.LENGTH_SHORT).show();
        });
        notes.addView(save);
        return notes;
    }

    private LinearLayout buildExportCard() {
        LinearLayout exportCard = UiKit.card(this);
        exportCard.addView(UiKit.text(
                this,
                "结束现场采集后，将当前材料生成一个新的不可变报告包。",
                13,
                UiKit.TEXT_SECONDARY,
                false));
        exportButton = UiKit.button(this, "导出当前报告包", true);
        exportButton.setOnClickListener(view -> exportCurrentPackage());
        exportCard.addView(exportButton);
        exportStatus = UiKit.text(this, "", 12, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams exportStatusParams = UiKit.matchWrap();
        exportStatusParams.topMargin = UiKit.dp(this, 10);
        exportCard.addView(exportStatus, exportStatusParams);
        return exportCard;
    }

    private LinearLayout buildPathCard() {
        LinearLayout pathCard = UiKit.card(this);
        String folder = "ConferenceRecorder/" + conference.id + "/"
                + (item.isPoster() ? "posters/" : "talks/") + item.id + "/packages/";
        TextView path = UiKit.text(this, folder, 13, UiKit.TEXT_PRIMARY, true);
        path.setTextIsSelectable(true);
        path.setPadding(
                UiKit.dp(this, 12), UiKit.dp(this, 12),
                UiKit.dp(this, 12), UiKit.dp(this, 12));
        path.setBackground(UiKit.roundRect(Color.rgb(238, 241, 239), 10, this));
        pathCard.addView(path);
        TextView pathNote = UiKit.text(
                this,
                "手机写入同步目录后由 Synology Drive 上传。A426 后续只读 W:，整理结果另存本机。",
                12,
                UiKit.TEXT_SECONDARY,
                false);
        LinearLayout.LayoutParams pathNoteParams = UiKit.matchWrap();
        pathNoteParams.topMargin = UiKit.dp(this, 10);
        pathCard.addView(pathNote, pathNoteParams);
        return pathCard;
    }

    private void handleRecordAction() {
        String ownKey = captureKey();
        AudioRecordingService.State state = AudioRecordingService.state();
        if (state != AudioRecordingService.State.IDLE
                && !ownKey.equals(AudioRecordingService.captureKey())) {
            Toast.makeText(this, "另一个报告正在录音，请先结束它", Toast.LENGTH_LONG).show();
            return;
        }
        if (state == AudioRecordingService.State.RECORDING) {
            sendRecordingAction(AudioRecordingService.ACTION_PAUSE);
        } else if (state == AudioRecordingService.State.PAUSED) {
            sendRecordingAction(AudioRecordingService.ACTION_RESUME);
        } else if (state == AudioRecordingService.State.FINALIZING) {
            Toast.makeText(this, "正在保存录音和最后的英文字幕", Toast.LENGTH_SHORT).show();
        } else {
            requestAudioAndStart();
        }
    }

    private void requestAudioAndStart() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED) {
            startNewAudioSegment();
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(
                    new String[]{
                            Manifest.permission.RECORD_AUDIO,
                            Manifest.permission.POST_NOTIFICATIONS
                    },
                    REQUEST_AUDIO_PERMISSION);
        } else {
            requestPermissions(
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    REQUEST_AUDIO_PERMISSION);
        }
    }

    private void startNewAudioSegment() {
        CaptureSessionStore.CaptureBundle capture = captureBundle(true);
        if (capture == null) return;
        SystemAudioTranscriber.Availability availability =
                SystemAudioTranscriber.availability(this);
        if (availability == SystemAudioTranscriber.Availability.ON_DEVICE) {
            startPreparedAudioSegment(capture, true, true);
        } else if (availability
                == SystemAudioTranscriber.Availability.SYSTEM_MAY_USE_NETWORK) {
            new AlertDialog.Builder(this)
                    .setTitle("英文实时字幕可能联网")
                    .setMessage("这台手机没有向 App 提供可确认的离线识别器。选择实时字幕后，会议音频可能由当前系统语音服务处理；无论选择哪项，原始录音都会保存在 App 暂存区。")
                    .setNegativeButton("仅录音", (dialog, which) ->
                            startPreparedAudioSegment(capture, false, false))
                    .setPositiveButton("录音并显示字幕", (dialog, which) ->
                            startPreparedAudioSegment(capture, true, false))
                    .show();
        } else {
            Toast.makeText(
                    this,
                    "当前系统不支持实时英文字幕，本段仍会正常录音",
                    Toast.LENGTH_LONG).show();
            startPreparedAudioSegment(capture, false, false);
        }
    }

    private void startPreparedAudioSegment(
            CaptureSessionStore.CaptureBundle capture,
            boolean liveTranscription,
            boolean onDevice) {
        try {
            File output = capture.nextAudioFile();
            Intent intent = new Intent(this, AudioRecordingService.class)
                    .setAction(AudioRecordingService.ACTION_START)
                    .putExtra(AudioRecordingService.EXTRA_OUTPUT_PATH, output.getAbsolutePath())
                    .putExtra(
                            AudioRecordingService.EXTRA_TRANSCRIPT_PATH,
                            capture.transcriptFile().getAbsolutePath())
                    .putExtra(
                            AudioRecordingService.EXTRA_TRANSCRIPT_METADATA_PATH,
                            capture.transcriptMetadataFile().getAbsolutePath())
                    .putExtra(AudioRecordingService.EXTRA_CAPTURE_KEY, captureKey())
                    .putExtra(AudioRecordingService.EXTRA_CONFERENCE_ID, conference.id)
                    .putExtra(AudioRecordingService.EXTRA_SESSION_ID, session == null ? "" : session.id)
                    .putExtra(AudioRecordingService.EXTRA_ITEM_ID, item.id)
                    .putExtra(AudioRecordingService.EXTRA_TITLE, item.title)
                    .putExtra(AudioRecordingService.EXTRA_LIVE_TRANSCRIPTION, liveTranscription)
                    .putExtra(AudioRecordingService.EXTRA_LIVE_ON_DEVICE, onDevice)
                    .putStringArrayListExtra(
                            AudioRecordingService.EXTRA_TRANSCRIPTION_BIASES,
                            new ArrayList<>(transcriptionBiases()));
            startForegroundService(intent);
            captureHint.setText(liveTranscription
                    ? "正在启动录音和英文实时字幕；打开相机时录音会继续。"
                    : "正在启动录音；打开相机拍摄时录音会继续运行。");
        } catch (RuntimeException error) {
            Toast.makeText(this, "无法准备录音：" + error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void stopRecording() {
        if (!isCurrentCaptureRecording()) return;
        sendRecordingAction(AudioRecordingService.ACTION_STOP);
    }

    private void sendRecordingAction(String action) {
        startService(new Intent(this, AudioRecordingService.class).setAction(action));
    }

    private void takePhoto() {
        CaptureSessionStore.CaptureBundle capture = captureBundle(true);
        if (capture == null) return;
        try {
            pendingPhotoFile = capture.nextImageFile();
            Uri output = FileProvider.getUriForFile(
                    this,
                    getPackageName() + ".capture-files",
                    pendingPhotoFile);
            Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                    .putExtra(MediaStore.EXTRA_OUTPUT, output)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            camera.setClipData(ClipData.newRawUri("会议照片", output));
            if (camera.resolveActivity(getPackageManager()) == null) {
                pendingPhotoFile = null;
                Toast.makeText(this, "没有找到可用的相机应用", Toast.LENGTH_LONG).show();
                return;
            }
            startActivityForResult(camera, REQUEST_CAPTURE_PHOTO);
        } catch (IllegalArgumentException error) {
            pendingPhotoFile = null;
            Toast.makeText(this, "无法准备照片：" + error.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void previewPhoto(File photo) {
        try {
            Uri uri = FileProvider.getUriForFile(
                    this,
                    getPackageName() + ".capture-files",
                    photo);
            Intent preview = new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "image/jpeg")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(preview);
        } catch (RuntimeException error) {
            Toast.makeText(this, "无法打开照片预览", Toast.LENGTH_LONG).show();
        }
    }

    private void confirmDeletePhoto(File photo) {
        new AlertDialog.Builder(this)
                .setTitle("删除这张本机照片？")
                .setMessage("只删除尚未导出的 App 暂存照片；已经导出的不可变报告包不受影响。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (dialog, which) -> {
                    if (!photo.delete()) {
                        Toast.makeText(this, "照片删除失败", Toast.LENGTH_LONG).show();
                    }
                    renderCaptureState();
                })
                .show();
    }

    private void confirmDeleteAudio(File audio) {
        if (isCurrentCaptureRecording()) {
            Toast.makeText(this, "请先结束当前录音，再删除音频", Toast.LENGTH_LONG).show();
            return;
        }
        if (!CaptureSessionStore.isManagedAudioFile(this, audio)) {
            Toast.makeText(this, "该文件不属于 App 录音暂存区", Toast.LENGTH_LONG).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("删除这段本机录音？")
                .setMessage("只删除尚保存在 App 暂存区的音频；已经导出的不可变报告包不受影响。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (dialog, which) -> {
                    if (!audio.delete()) {
                        Toast.makeText(this, "录音删除失败", Toast.LENGTH_LONG).show();
                    }
                    renderCaptureState();
                    renderExportState();
                })
                .show();
    }

    private void renderCaptureState() {
        if (item == null || imageStatus == null) return;
        CaptureSessionStore.CaptureBundle capture = captureBundle(false);
        File[] audioFiles = capture == null ? new File[0] : capture.audioFiles();
        File[] imageFiles = capture == null ? new File[0] : capture.imageFiles();
        boolean ownRecording = isCurrentCaptureRecording();
        AudioRecordingService.State recordingState = AudioRecordingService.state();

        if (audioStatus != null) {
            if (ownRecording && recordingState == AudioRecordingService.State.RECORDING) {
                setPill(audioStatus, "录音中", true);
            } else if (ownRecording && recordingState == AudioRecordingService.State.PAUSED) {
                setPill(audioStatus, "已暂停", true);
            } else {
                setPill(audioStatus,
                        audioFiles.length == 0 ? "未采集" : audioFiles.length + " 段",
                        audioFiles.length > 0);
            }
        }
        setPill(imageStatus, imageFiles.length + " 张", imageFiles.length > 0);
        if (noteStatus != null) {
            String currentNoteState = noteState();
            setPill(noteStatus, currentNoteState, "已保存".equals(currentNoteState));
        }
        if (!item.isPoster()) renderTranscriptionState(capture, audioFiles);
        renderMaterialsSummary(audioFiles, imageFiles);

        if (recordButton != null) {
            boolean otherRecording = recordingState != AudioRecordingService.State.IDLE
                    && !captureKey().equals(AudioRecordingService.captureKey());
            boolean finalizing = ownRecording
                    && recordingState == AudioRecordingService.State.FINALIZING;
            recordButton.setEnabled(
                    !exportRunning && !transcriptionRunning && !otherRecording && !finalizing);
            recordButton.setAlpha(recordButton.isEnabled() ? 1f : 0.5f);
            if (ownRecording && recordingState == AudioRecordingService.State.RECORDING) {
                recordButton.setText("暂停录音\n正在记录当前报告");
                recordState.setText("正在录音");
            } else if (ownRecording && recordingState == AudioRecordingService.State.PAUSED) {
                recordButton.setText("继续录音\n当前片段已暂停");
                recordState.setText("录音已暂停");
            } else if (finalizing) {
                recordButton.setText("正在保存\n请稍候");
                recordState.setText("正在整理英文字幕");
            } else if (audioFiles.length > 0) {
                recordButton.setText(getString(R.string.capture_append_recording, audioFiles.length));
                recordState.setText(String.format(
                        Locale.ROOT, "本次已保存 %d 段录音", audioFiles.length));
            } else {
                recordButton.setText("开始录音\n支持暂停和继续");
                recordState.setText("准备记录");
            }
            stopButton.setEnabled(!exportRunning
                    && !transcriptionRunning
                    && ownRecording
                    && recordingState != AudioRecordingService.State.FINALIZING);
            stopButton.setAlpha(stopButton.isEnabled() ? 1f : 0.45f);
        }
        photoButton.setEnabled(!exportRunning && !transcriptionRunning);
        photoButton.setAlpha(photoButton.isEnabled() ? 1f : 0.5f);

        String error = AudioRecordingService.lastError();
        if (!error.isEmpty()) {
            captureHint.setText(error);
            captureHint.setTextColor(item.isPoster() ? UiKit.WARNING : UiKit.WARNING_SOFT);
        } else if (ownRecording) {
            captureHint.setText(R.string.capture_hint_recording);
            captureHint.setTextColor(item.isPoster()
                    ? UiKit.ACCENT : Color.rgb(214, 239, 235));
        } else {
            captureHint.setText(R.string.capture_hint_idle);
            captureHint.setTextColor(item.isPoster()
                    ? UiKit.TEXT_SECONDARY : Color.rgb(202, 218, 221));
        }
        renderRecordingTimer();
        renderMediaList(audioFiles, imageFiles);
    }

    private void renderRecordingTimer() {
        if (recordTimer == null) return;
        long totalSeconds = AudioRecordingService.elapsedMillis() / 1000L;
        long hours = totalSeconds / 3600L;
        long minutes = (totalSeconds % 3600L) / 60L;
        long seconds = totalSeconds % 60L;
        recordTimer.setText(String.format(
                Locale.ROOT, "%02d:%02d:%02d", hours, minutes, seconds));
    }

    private void renderMaterialsSummary(File[] audioFiles, File[] imageFiles) {
        if (materialsSummary == null) return;
        StringBuilder summary = new StringBuilder();
        if (!item.isPoster()) summary.append("录音 ").append(audioFiles.length).append(" 段 · ");
        summary.append("照片 ").append(imageFiles.length).append(" 张 · 备注")
                .append("已保存".equals(noteState()) ? "已保存" : "未填写");
        if (!item.isPoster()) {
            CaptureSessionStore.CaptureBundle capture = captureBundle(false);
            summary.append(" · 逐字稿")
                    .append(TranscriptStore.hasTranscript(capture) ? "已生成" : "未生成");
        }
        materialsSummary.setText(summary.toString());
    }

    private void renderTranscriptionState(
            CaptureSessionStore.CaptureBundle capture, File[] audioFiles) {
        if (transcriptionButton == null || transcriptionStatus == null) return;
        boolean hasTranscript = TranscriptStore.hasTranscript(capture);
        String transcript = hasTranscript ? TranscriptStore.read(capture) : "";
        boolean liveRecording = isCurrentCaptureRecording()
                && (AudioRecordingService.state() == AudioRecordingService.State.RECORDING
                || AudioRecordingService.state() == AudioRecordingService.State.PAUSED
                || AudioRecordingService.state() == AudioRecordingService.State.FINALIZING);
        if (liveRecording && !transcriptionRunning) {
            transcriptionStatus.setText(AudioRecordingService.liveStatus());
            String livePreview = AudioRecordingService.liveTranscriptPreview();
            transcriptionPreview.setText(livePreview.isEmpty()
                    ? "正在等待系统返回英文字幕……"
                    : livePreview);
        } else if (!transcriptionRunning) {
            transcriptionStatus.setText(hasTranscript
                    ? "已生成 " + transcript.length() + " 字"
                    : capabilityLabel());
            transcriptionPreview.setText(hasTranscript
                    ? transcript
                    : "开始录音后可显示英文实时字幕；也可在结束后重新转写 M4A。");
        }
        boolean enabled = !transcriptionRunning
                && !exportRunning
                && !isCurrentCaptureRecording()
                && audioFiles.length > 0;
        transcriptionButton.setEnabled(enabled);
        transcriptionButton.setAlpha(enabled ? 1f : 0.45f);
        transcriptionButton.setText(transcriptionRunning
                ? "正在转写…"
                : (hasTranscript ? "重新转写已有录音" : "转写已有录音"));
        if (transcriptMaterialStatus != null) {
            setPill(
                    transcriptMaterialStatus,
                    hasTranscript ? "已生成" : (transcriptionRunning ? "生成中" : "未生成"),
                    hasTranscript || transcriptionRunning);
        }
    }

    private void renderMediaList(File[] audioFiles, File[] imageFiles) {
        if (capturedMediaList == null) return;
        capturedMediaList.removeAllViews();
        if (audioFiles.length == 0 && imageFiles.length == 0) {
            capturedMediaList.addView(UiKit.text(
                    this, "尚未采集录音或照片。", 14, UiKit.TEXT_SECONDARY, false));
            return;
        }
        for (int index = 0; index < audioFiles.length; index++) {
            File audio = audioFiles[index];
            LinearLayout row = UiKit.horizontal(this);
            String audioLabel = item.isPoster() ? "旧版录音 " : "录音 ";
            row.addView(UiKit.text(
                    this,
                    audioLabel + (index + 1) + " · " + audio.getName()
                            + " · " + formatBytes(audio.length()),
                    13,
                    UiKit.TEXT_PRIMARY,
                    true), UiKit.weight(1f));
            TextView delete = smallAction("删除", UiKit.CORAL);
            delete.setEnabled(!isCurrentCaptureRecording());
            delete.setAlpha(delete.isEnabled() ? 1f : 0.45f);
            delete.setOnClickListener(view -> confirmDeleteAudio(audio));
            row.addView(delete);
            capturedMediaList.addView(row);
            if (index < audioFiles.length - 1 || imageFiles.length > 0) {
                capturedMediaList.addView(UiKit.divider(this));
            }
        }
        for (int index = 0; index < imageFiles.length; index++) {
            File image = imageFiles[index];
            LinearLayout row = UiKit.horizontal(this);
            row.addView(UiKit.text(
                    this,
                    "照片 " + (index + 1) + " · " + formatBytes(image.length()),
                    13,
                    UiKit.TEXT_PRIMARY,
                    true), UiKit.weight(1f));
            TextView preview = smallAction("预览", UiKit.ACCENT);
            preview.setOnClickListener(view -> previewPhoto(image));
            row.addView(preview);
            TextView delete = smallAction("删除", UiKit.CORAL);
            delete.setOnClickListener(view -> confirmDeletePhoto(image));
            row.addView(delete);
            capturedMediaList.addView(row);
            if (index < imageFiles.length - 1) capturedMediaList.addView(UiKit.divider(this));
        }
    }

    private TextView smallAction(String label, int color) {
        TextView action = UiKit.text(this, label, 12, color, true);
        action.setGravity(Gravity.CENTER);
        action.setPadding(
                UiKit.dp(this, 10), UiKit.dp(this, 8),
                UiKit.dp(this, 10), UiKit.dp(this, 8));
        action.setBackground(UiKit.roundRect(Color.rgb(240, 244, 242), 10, this));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMarginStart(UiKit.dp(this, 6));
        action.setLayoutParams(params);
        return action;
    }

    private CaptureSessionStore.CaptureBundle captureBundle(boolean create) {
        try {
            return create
                    ? CaptureSessionStore.currentOrCreate(this, conference.id, item.id)
                    : CaptureSessionStore.current(this, conference.id, item.id);
        } catch (IOException error) {
            if (create) {
                Toast.makeText(this, "采集暂存区不可用：" + error.getMessage(), Toast.LENGTH_LONG).show();
            }
            return null;
        }
    }

    private boolean isCurrentCaptureRecording() {
        return AudioRecordingService.state() != AudioRecordingService.State.IDLE
                && captureKey().equals(AudioRecordingService.captureKey());
    }

    private String captureKey() {
        return CaptureSessionStore.captureKey(conference.id, item.id);
    }

    private TextView captureAction(
            String title, String detail, int background, int foreground) {
        TextView action = UiKit.text(this, title + "\n" + detail, 15, foreground, true);
        action.setGravity(Gravity.CENTER);
        action.setMinHeight(UiKit.dp(this, 88));
        action.setPadding(
                UiKit.dp(this, 10), UiKit.dp(this, 13),
                UiKit.dp(this, 10), UiKit.dp(this, 13));
        action.setBackground(UiKit.roundRect(background, 15, this));
        action.setClickable(true);
        action.setFocusable(true);
        return action;
    }

    private LinearLayout statusRow(String label, TextView valueView) {
        LinearLayout row = UiKit.horizontal(this);
        row.addView(UiKit.text(this, label, 14, UiKit.TEXT_PRIMARY, true), UiKit.weight(1f));
        row.addView(valueView);
        return row;
    }

    private TextView statusPill(String value, boolean ready) {
        return UiKit.pill(
                this,
                value,
                ready ? UiKit.ACCENT : UiKit.TEXT_SECONDARY,
                ready ? UiKit.ACCENT_SOFT : Color.rgb(238, 241, 239));
    }

    private void setPill(TextView pill, String value, boolean ready) {
        pill.setText(value);
        pill.setTextColor(ready ? UiKit.ACCENT : UiKit.TEXT_SECONDARY);
        pill.setBackground(UiKit.roundRect(
                ready ? UiKit.ACCENT_SOFT : Color.rgb(238, 241, 239), 999, this));
    }

    private String noteState() {
        String note = ReportPackageStore.loadNote(this, conference.id, item.id);
        return note.trim().isEmpty() ? "未填写" : "已保存";
    }

    private void saveNote() {
        ReportPackageStore.saveNote(
                this, conference.id, item.id, noteEditor.getText().toString().trim());
    }

    private void renderExportState() {
        if (exportButton == null) return;
        boolean configured = StorageTargetStore.isConfigured(this);
        boolean recording = isCurrentCaptureRecording();
        exportButton.setEnabled(!exportRunning && !recording && !transcriptionRunning);
        if (exportRunning) {
            exportButton.setText("正在生成报告包……");
        } else if (recording) {
            exportButton.setText("请先结束录音");
        } else if (transcriptionRunning) {
            exportButton.setText("请等待手机转写完成");
        } else {
            exportButton.setText(configured ? "导出报告包" : "导出报告包并选择目录");
        }
        exportStatus.setText(configured
                ? "同步目录已就绪 · 上次写入：" + StorageTargetStore.lastExport(this)
                : "首次导出时再授权同步目录即可");
    }

    private void exportCurrentPackage() {
        if (isCurrentCaptureRecording()) {
            Toast.makeText(this, "请先结束录音，再导出完整文件", Toast.LENGTH_LONG).show();
            return;
        }
        if (transcriptionRunning) {
            Toast.makeText(this, "请等待手机转写完成，再导出报告包", Toast.LENGTH_LONG).show();
            return;
        }
        if (!StorageTargetStore.isConfigured(this)) {
            open(StorageAccessActivity.class, null);
            return;
        }
        saveNote();
        setExportRunning(true);
        String note = noteEditor.getText().toString().trim();
        new Thread(() -> {
            try {
                PackageExporter.ExportResult result = PackageExporter.exportPackage(
                        this, conference, session, item, note);
                runOnUiThread(() -> {
                    setExportRunning(false);
                    Toast.makeText(
                            this,
                            "已写入手机同步目录：" + result.displayPath,
                            Toast.LENGTH_LONG).show();
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    setExportRunning(false);
                    Toast.makeText(this, "导出失败：" + error.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }, "conference-package-export").start();
    }

    private void setExportRunning(boolean running) {
        exportRunning = running;
        renderCaptureState();
        renderExportState();
    }

    private String value(String key) {
        String value = getIntent().getStringExtra(key);
        return value == null ? "" : value;
    }

    private static String formatBytes(long bytes) {
        if (bytes < 1024L) return bytes + " B";
        if (bytes < 1024L * 1024L) {
            return String.format(Locale.US, "%.1f KB", bytes / 1024.0);
        }
        return String.format(Locale.US, "%.1f MB", bytes / (1024.0 * 1024.0));
    }
}
