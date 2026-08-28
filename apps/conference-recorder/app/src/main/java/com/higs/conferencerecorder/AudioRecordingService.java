package com.higs.conferencerecorder;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;

import com.higs.conferencerecorder.data.CaptureSessionStore;
import com.higs.conferencerecorder.data.TranscriptStore;
import com.higs.conferencerecorder.recording.PcmAacRecorder;
import com.higs.conferencerecorder.transcription.LiveSystemTranscriber;
import com.higs.conferencerecorder.transcription.LiveTranscriber;
import com.higs.conferencerecorder.transcription.VoskLiveTranscriber;
import com.higs.conferencerecorder.transcription.VoskModelManager;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public final class AudioRecordingService extends Service {
    public static final String ACTION_START = "com.higs.conferencerecorder.action.START_RECORDING";
    public static final String ACTION_PAUSE = "com.higs.conferencerecorder.action.PAUSE_RECORDING";
    public static final String ACTION_RESUME = "com.higs.conferencerecorder.action.RESUME_RECORDING";
    public static final String ACTION_STOP = "com.higs.conferencerecorder.action.STOP_RECORDING";
    public static final String ACTION_STATE_CHANGED =
            "com.higs.conferencerecorder.action.RECORDING_STATE_CHANGED";
    public static final String EXTRA_OUTPUT_PATH = "output_path";
    public static final String EXTRA_TRANSCRIPT_PATH = "transcript_path";
    public static final String EXTRA_TRANSCRIPT_METADATA_PATH = "transcript_metadata_path";
    public static final String EXTRA_CAPTURE_KEY = "capture_key";
    public static final String EXTRA_CONFERENCE_ID = "conference_id";
    public static final String EXTRA_SESSION_ID = "session_id";
    public static final String EXTRA_ITEM_ID = "item_id";
    public static final String EXTRA_TITLE = "title";
    public static final String EXTRA_LIVE_TRANSCRIPTION = "live_transcription";
    public static final String EXTRA_LIVE_ON_DEVICE = "live_on_device";
    public static final String EXTRA_LIVE_ENGINE = "live_engine";
    public static final String EXTRA_TRANSCRIPTION_BIASES = "transcription_biases";
    public static final String ENGINE_ANDROID = "android";
    public static final String ENGINE_VOSK = "vosk_offline";

    public enum State {
        IDLE,
        RECORDING,
        PAUSED,
        FINALIZING
    }

    private static final String CHANNEL_ID = "conference_capture";
    private static final int NOTIFICATION_ID = 4101;
    private static final long TRANSCRIPTION_FINISH_TIMEOUT_MS = 5_000L;
    private static volatile State state = State.IDLE;
    private static volatile String captureKey = "";
    private static volatile String lastError = "";
    private static volatile String liveStatus = "英文实时字幕未启动";
    private static volatile String liveTranscriptPreview = "";
    private static volatile long accumulatedMillis;
    private static volatile long activeSinceMillis;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final List<String> liveSegments = new ArrayList<>();
    private final Set<String> seenSegments = new LinkedHashSet<>();
    private final ArrayList<String> transcriptionBiases = new ArrayList<>();

    private PcmAacRecorder recorder;
    private LiveTranscriber liveTranscriber;
    private File outputFile;
    private File transcriptFile;
    private File transcriptMetadataFile;
    private String conferenceId = "";
    private String sessionId = "";
    private String itemId = "";
    private String title = "会议报告录音";
    private String latestPartial = "";
    private boolean liveRequested;
    private boolean liveOnDevice;
    private String liveEngine = ENGINE_ANDROID;
    private boolean liveHadFailure;
    private boolean stopFinished;
    private int liveRetryCount;

    private final Runnable transcriptionFinishTimeout = () -> {
        if (state != State.FINALIZING || stopFinished) return;
        liveHadFailure = true;
        finishStop(true);
    };

    public static State state() { return state; }

    public static String captureKey() { return captureKey; }

    public static String lastError() { return lastError; }

    public static String liveStatus() { return liveStatus; }

    public static String liveTranscriptPreview() { return liveTranscriptPreview; }

    public static long elapsedMillis() {
        long elapsed = accumulatedMillis;
        if (state == State.RECORDING && activeSinceMillis > 0L) {
            elapsed += Math.max(0L, SystemClock.elapsedRealtime() - activeSinceMillis);
        }
        return elapsed;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || intent.getAction() == null) return START_NOT_STICKY;
        switch (intent.getAction()) {
            case ACTION_START: startRecording(intent); break;
            case ACTION_PAUSE: pauseRecording(); break;
            case ACTION_RESUME: resumeRecording(); break;
            case ACTION_STOP: stopRecording(); break;
            default: break;
        }
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public void onDestroy() {
        mainHandler.removeCallbacksAndMessages(null);
        if (liveTranscriber != null) {
            liveTranscriber.close();
            liveTranscriber = null;
        }
        if (recorder != null) {
            recorder.close();
            recorder = null;
        }
        state = State.IDLE;
        captureKey = "";
        resetTimer();
        broadcastState();
        super.onDestroy();
    }

    private void startRecording(Intent intent) {
        if (state != State.IDLE || recorder != null) return;
        outputFile = new File(value(intent, EXTRA_OUTPUT_PATH));
        transcriptFile = new File(value(intent, EXTRA_TRANSCRIPT_PATH));
        transcriptMetadataFile = new File(value(intent, EXTRA_TRANSCRIPT_METADATA_PATH));
        if (!CaptureSessionStore.isManagedAudioFile(this, outputFile)) {
            fail("录音目标不在 App 采集暂存区");
            return;
        }
        if (!CaptureSessionStore.isManagedTranscriptFile(this, transcriptFile, "transcript.txt")
                || !CaptureSessionStore.isManagedTranscriptFile(
                this, transcriptMetadataFile, "transcription.json")) {
            fail("英文字幕目标不在 App 采集暂存区");
            return;
        }

        captureKey = value(intent, EXTRA_CAPTURE_KEY);
        conferenceId = value(intent, EXTRA_CONFERENCE_ID);
        sessionId = value(intent, EXTRA_SESSION_ID);
        itemId = value(intent, EXTRA_ITEM_ID);
        String requestedTitle = value(intent, EXTRA_TITLE);
        if (!requestedTitle.isEmpty()) title = requestedTitle;
        liveRequested = intent.getBooleanExtra(EXTRA_LIVE_TRANSCRIPTION, false);
        liveOnDevice = intent.getBooleanExtra(EXTRA_LIVE_ON_DEVICE, false);
        liveEngine = value(intent, EXTRA_LIVE_ENGINE);
        if (!ENGINE_VOSK.equals(liveEngine)) liveEngine = ENGINE_ANDROID;
        ArrayList<String> biases = intent.getStringArrayListExtra(EXTRA_TRANSCRIPTION_BIASES);
        transcriptionBiases.clear();
        if (biases != null) transcriptionBiases.addAll(biases);
        liveSegments.clear();
        seenSegments.clear();
        latestPartial = "";
        lastError = "";
        liveTranscriptPreview = "";
        liveStatus = liveRequested ? "正在准备英文实时字幕" : "本段仅保存录音";
        liveHadFailure = false;
        liveRetryCount = 0;
        stopFinished = false;

        startMicrophoneForeground(buildNotification("正在准备录音…"));
        try {
            recorder = new PcmAacRecorder(new PcmAacRecorder.Listener() {
                @Override
                public void onPcm(byte[] pcm, int length, int sampleRate) {
                    LiveTranscriber current = liveTranscriber;
                    if (current != null) current.offer(pcm, length);
                }

                @Override
                public void onFailure(String message) {
                    mainHandler.post(() -> failAndStop(message));
                }
            });
            recorder.start(outputFile);
            accumulatedMillis = 0L;
            activeSinceMillis = SystemClock.elapsedRealtime();
            state = State.RECORDING;
            if (liveRequested) startLiveTranscription();
            updateNotification(liveRequested ? "正在录音并生成英文字幕" : "正在录音");
            broadcastState();
        } catch (IOException | RuntimeException error) {
            releaseRecorder();
            fail("无法开始录音：" + safeMessage(error));
        }
    }

    private void startLiveTranscription() {
        if (!liveRequested || liveTranscriber != null
                || (state != State.RECORDING && state != State.PAUSED)) return;
        final LiveTranscriber[] holder = new LiveTranscriber[1];
        LiveTranscriber.Listener listener = new LiveTranscriber.Listener() {
                    private boolean isCurrent() { return liveTranscriber == holder[0]; }

                    @Override
                    public void onStatus(String status) {
                        mainHandler.post(() -> {
                            if (!isCurrent()) return;
                            liveStatus = status;
                            broadcastLiveUpdate();
                        });
                    }

                    @Override
                    public void onPartial(String text) {
                        mainHandler.post(() -> {
                            if (!isCurrent()) return;
                            latestPartial = text;
                            updateLivePreview();
                            broadcastLiveUpdate();
                        });
                    }

                    @Override
                    public void onSegment(String text) {
                        mainHandler.post(() -> {
                            if (!isCurrent()) return;
                            addSegment(text);
                            latestPartial = "";
                            updateLivePreview();
                            broadcastLiveUpdate();
                        });
                    }

                    @Override
                    public void onCompleted() {
                        mainHandler.post(() -> handleLiveCompleted(holder[0]));
                    }

                    @Override
                    public void onFailed(String message, String lastPartial) {
                        mainHandler.post(() -> handleLiveFailure(
                                holder[0], message, lastPartial));
                    }
                };
        LiveTranscriber candidate = ENGINE_VOSK.equals(liveEngine)
                ? new VoskLiveTranscriber(VoskModelManager.modelDirectory(this), listener)
                : new LiveSystemTranscriber(
                        this, transcriptionBiases, liveOnDevice, listener);
        holder[0] = candidate;
        liveTranscriber = candidate;
        try {
            candidate.start(recorder.sampleRate());
        } catch (IOException error) {
            liveTranscriber = null;
            candidate.close();
            handleLiveFailure(candidate, error.getMessage(), latestPartial);
        }
    }

    private void handleLiveCompleted(LiveTranscriber source) {
        if (liveTranscriber != source) return;
        liveTranscriber = null;
        if (state == State.FINALIZING) {
            finishStop(false);
        } else if (state == State.RECORDING || state == State.PAUSED) {
            liveHadFailure = true;
            liveStatus = "系统提前结束英文字幕，正在恢复；录音正常";
            scheduleLiveRestart();
        }
    }

    private void handleLiveFailure(
            LiveTranscriber source, String message, String partialText) {
        if (source != null && liveTranscriber != null && liveTranscriber != source) return;
        if (liveTranscriber == source) liveTranscriber = null;
        if (partialText != null && !partialText.trim().isEmpty()) latestPartial = partialText.trim();
        updateLivePreview();
        liveHadFailure = true;
        liveStatus = message + "；录音仍在正常保存";
        broadcastState();
        if (state == State.FINALIZING) {
            finishStop(true);
        } else if (state == State.RECORDING || state == State.PAUSED) {
            scheduleLiveRestart();
        }
    }

    private void scheduleLiveRestart() {
        if (++liveRetryCount > 3) {
            liveStatus = ENGINE_VOSK.equals(liveEngine)
                    ? "离线英文字幕已停止；录音仍在正常保存"
                    : "英文实时字幕已停止；录音仍在正常保存，可在结束后重新转写";
            broadcastState();
            return;
        }
        long delay = liveRetryCount == 1 ? 1_500L : (liveRetryCount == 2 ? 5_000L : 15_000L);
        mainHandler.postDelayed(() -> {
            if ((state == State.RECORDING || state == State.PAUSED)
                    && liveTranscriber == null) startLiveTranscription();
        }, delay);
    }

    private void pauseRecording() {
        if (state != State.RECORDING || recorder == null) return;
        try {
            recorder.pause();
            accumulatedMillis += Math.max(0L, SystemClock.elapsedRealtime() - activeSinceMillis);
            activeSinceMillis = 0L;
            state = State.PAUSED;
            updateNotification("录音和英文字幕已暂停");
            broadcastState();
        } catch (IOException | RuntimeException error) {
            failAndStop("暂停失败：" + safeMessage(error));
        }
    }

    private void resumeRecording() {
        if (state != State.PAUSED || recorder == null) return;
        try {
            recorder.resume();
            activeSinceMillis = SystemClock.elapsedRealtime();
            state = State.RECORDING;
            updateNotification(liveRequested ? "正在录音并生成英文字幕" : "正在录音");
            broadcastState();
        } catch (IOException | RuntimeException error) {
            failAndStop("继续失败：" + safeMessage(error));
        }
    }

    private void stopRecording() {
        if (state == State.FINALIZING) return;
        if (recorder == null) {
            finishStop(true);
            return;
        }
        if (state == State.RECORDING && activeSinceMillis > 0L) {
            accumulatedMillis += Math.max(0L, SystemClock.elapsedRealtime() - activeSinceMillis);
        }
        activeSinceMillis = 0L;
        state = State.FINALIZING;
        updateNotification("正在保存录音和英文字幕");
        broadcastState();
        try {
            recorder.stop();
            recorder = null;
        } catch (IOException | RuntimeException error) {
            lastError = "录音结束异常：" + safeMessage(error);
            releaseRecorder();
        }

        if (liveTranscriber != null) {
            liveTranscriber.finish();
            mainHandler.postDelayed(transcriptionFinishTimeout, TRANSCRIPTION_FINISH_TIMEOUT_MS);
        } else {
            finishStop(liveRequested && liveHadFailure);
        }
    }

    private void finishStop(boolean partial) {
        if (stopFinished) return;
        stopFinished = true;
        mainHandler.removeCallbacks(transcriptionFinishTimeout);
        if (liveTranscriber != null) {
            liveTranscriber.close();
            liveTranscriber = null;
        }
        if (!latestPartial.isEmpty()) addSegment(latestPartial);
        updateLivePreview();
        if (!liveSegments.isEmpty()) {
            try {
                TranscriptStore.saveLive(
                        transcriptFile,
                        transcriptMetadataFile,
                        joinedSegments(),
                        ENGINE_VOSK.equals(liveEngine)
                                ? "vosk_offline_live"
                                : (liveOnDevice
                                ? "android_on_device_live"
                                : "android_system_service_live"),
                        partial || liveHadFailure ? "partial" : "complete",
                        outputFile,
                        liveSegments.size());
                liveStatus = partial || liveHadFailure
                        ? "已保存英文字幕（可能不完整）" : "已保存英文字幕";
            } catch (IOException error) {
                liveStatus = "英文字幕保存失败：" + safeMessage(error);
            }
        } else if (liveRequested) {
            liveStatus = ENGINE_VOSK.equals(liveEngine)
                    ? "本段没有生成离线英文字幕，原始录音已保存"
                    : "本段没有生成英文字幕，可使用录音结束后转写";
        }
        state = State.IDLE;
        captureKey = "";
        resetTimer();
        broadcastState();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void addSegment(String text) {
        String value = text == null ? "" : text.trim();
        if (!value.isEmpty() && seenSegments.add(value)) liveSegments.add(value);
    }

    private void updateLivePreview() {
        StringBuilder preview = new StringBuilder();
        int firstVisible = Math.max(0, liveSegments.size() - 5);
        for (int index = firstVisible; index < liveSegments.size(); index++) {
            if (preview.length() > 0) preview.append('\n');
            preview.append(liveSegments.get(index));
        }
        if (!latestPartial.isEmpty()) {
            if (preview.length() > 0) preview.append('\n');
            preview.append(latestPartial);
        }
        String value = preview.toString();
        liveTranscriptPreview = value.length() <= 1_500
                ? value : value.substring(value.length() - 1_500);
    }

    private String joinedSegments() {
        StringBuilder text = new StringBuilder();
        for (String segment : liveSegments) {
            if (text.length() > 0) text.append('\n');
            text.append(segment);
        }
        return text.toString().trim();
    }

    private void failAndStop(String message) {
        lastError = message;
        if (liveTranscriber != null) {
            liveTranscriber.close();
            liveTranscriber = null;
        }
        releaseRecorder();
        if (outputFile != null && outputFile.exists() && outputFile.length() == 0L) {
            outputFile.delete();
        }
        state = State.IDLE;
        captureKey = "";
        resetTimer();
        broadcastState();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void fail(String message) {
        lastError = message;
        state = State.IDLE;
        captureKey = "";
        resetTimer();
        broadcastState();
        stopSelf();
    }

    private void releaseRecorder() {
        if (recorder == null) return;
        recorder.close();
        recorder = null;
    }

    private static void resetTimer() {
        accumulatedMillis = 0L;
        activeSinceMillis = 0L;
    }

    private void startMicrophoneForeground(Notification notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void updateNotification(String status) {
        getSystemService(NotificationManager.class).notify(
                NOTIFICATION_ID, buildNotification(status));
    }

    private Notification buildNotification(String status) {
        Intent content = new Intent(this, PackageActivity.class)
                .putExtra(PackageActivity.EXTRA_CONFERENCE_ID, conferenceId)
                .putExtra(PackageActivity.EXTRA_SESSION_ID, sessionId)
                .putExtra(PackageActivity.EXTRA_ITEM_ID, itemId)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this, 0, content,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        PendingIntent toggle = serviceAction(
                state == State.PAUSED ? ACTION_RESUME : ACTION_PAUSE, 1);
        PendingIntent stop = serviceAction(ACTION_STOP, 2);
        Notification.Builder builder = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_app)
                .setContentTitle(title)
                .setContentText(status + " · 拍照时录音会继续")
                .setContentIntent(contentIntent)
                .setOngoing(true)
                .setOnlyAlertOnce(true);
        if (state != State.FINALIZING) {
            builder.addAction(0, state == State.PAUSED ? "继续" : "暂停", toggle)
                    .addAction(0, "结束", stop);
        }
        return builder.build();
    }

    private PendingIntent serviceAction(String action, int requestCode) {
        Intent intent = new Intent(this, AudioRecordingService.class).setAction(action);
        return PendingIntent.getService(this, requestCode, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private void createNotificationChannel() {
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "会议现场录音", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("显示正在进行的会议报告录音和英文实时字幕");
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
    }

    private void broadcastState() {
        Intent update = new Intent(ACTION_STATE_CHANGED)
                .setPackage(getPackageName())
                .putExtra("state", state.name())
                .putExtra("error", lastError)
                .putExtra("live_status", liveStatus);
        sendBroadcast(update);
    }

    private void broadcastLiveUpdate() {
        Intent update = new Intent(ACTION_STATE_CHANGED)
                .setPackage(getPackageName())
                .putExtra("live_update", true)
                .putExtra("live_status", liveStatus);
        sendBroadcast(update);
    }

    private static String value(Intent intent, String key) {
        String value = intent.getStringExtra(key);
        return value == null ? "" : value;
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName() : message;
    }
}
