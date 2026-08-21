package com.higs.conferencerecorder;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;

import com.higs.conferencerecorder.data.CaptureSessionStore;

import java.io.File;
import java.io.IOException;

public final class AudioRecordingService extends Service {
    public static final String ACTION_START = "com.higs.conferencerecorder.action.START_RECORDING";
    public static final String ACTION_PAUSE = "com.higs.conferencerecorder.action.PAUSE_RECORDING";
    public static final String ACTION_RESUME = "com.higs.conferencerecorder.action.RESUME_RECORDING";
    public static final String ACTION_STOP = "com.higs.conferencerecorder.action.STOP_RECORDING";
    public static final String ACTION_STATE_CHANGED =
            "com.higs.conferencerecorder.action.RECORDING_STATE_CHANGED";
    public static final String EXTRA_OUTPUT_PATH = "output_path";
    public static final String EXTRA_CAPTURE_KEY = "capture_key";
    public static final String EXTRA_CONFERENCE_ID = "conference_id";
    public static final String EXTRA_SESSION_ID = "session_id";
    public static final String EXTRA_ITEM_ID = "item_id";
    public static final String EXTRA_TITLE = "title";

    public enum State {
        IDLE,
        RECORDING,
        PAUSED
    }

    private static final String CHANNEL_ID = "conference_capture";
    private static final int NOTIFICATION_ID = 4101;
    private static volatile State state = State.IDLE;
    private static volatile String captureKey = "";
    private static volatile String lastError = "";
    private static volatile long accumulatedMillis;
    private static volatile long activeSinceMillis;

    private MediaRecorder recorder;
    private File outputFile;
    private String conferenceId = "";
    private String sessionId = "";
    private String itemId = "";
    private String title = "会议报告录音";

    public static State state() {
        return state;
    }

    public static String captureKey() {
        return captureKey;
    }

    public static String lastError() {
        return lastError;
    }

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
            case ACTION_START:
                startRecording(intent);
                break;
            case ACTION_PAUSE:
                pauseRecording();
                break;
            case ACTION_RESUME:
                resumeRecording();
                break;
            case ACTION_STOP:
                stopRecording();
                break;
            default:
                break;
        }
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (recorder != null) {
            try {
                recorder.stop();
            } catch (RuntimeException ignored) {
                // A process shutdown can leave an incomplete segment; it is excluded if empty.
            }
            recorder.release();
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
        if (!CaptureSessionStore.isManagedAudioFile(this, outputFile)) {
            fail("录音目标不在 App 采集暂存区");
            return;
        }
        captureKey = value(intent, EXTRA_CAPTURE_KEY);
        conferenceId = value(intent, EXTRA_CONFERENCE_ID);
        sessionId = value(intent, EXTRA_SESSION_ID);
        itemId = value(intent, EXTRA_ITEM_ID);
        String requestedTitle = value(intent, EXTRA_TITLE);
        if (!requestedTitle.isEmpty()) title = requestedTitle;
        lastError = "";

        startMicrophoneForeground(buildNotification("正在准备录音…"));
        try {
            recorder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                    ? new MediaRecorder(this)
                    : new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            recorder.setAudioSamplingRate(44_100);
            recorder.setAudioChannels(1);
            recorder.setAudioEncodingBitRate(128_000);
            recorder.setOutputFile(outputFile.getAbsolutePath());
            recorder.prepare();
            recorder.start();
            accumulatedMillis = 0L;
            activeSinceMillis = SystemClock.elapsedRealtime();
            state = State.RECORDING;
            updateNotification("正在录音");
            broadcastState();
        } catch (IOException | RuntimeException error) {
            releaseRecorder();
            fail("无法开始录音：" + safeMessage(error));
        }
    }

    private void pauseRecording() {
        if (state != State.RECORDING || recorder == null) return;
        try {
            recorder.pause();
            accumulatedMillis += Math.max(
                    0L, SystemClock.elapsedRealtime() - activeSinceMillis);
            activeSinceMillis = 0L;
            state = State.PAUSED;
            updateNotification("录音已暂停");
            broadcastState();
        } catch (RuntimeException error) {
            failAndStop("暂停失败：" + safeMessage(error));
        }
    }

    private void resumeRecording() {
        if (state != State.PAUSED || recorder == null) return;
        try {
            recorder.resume();
            activeSinceMillis = SystemClock.elapsedRealtime();
            state = State.RECORDING;
            updateNotification("正在录音");
            broadcastState();
        } catch (RuntimeException error) {
            failAndStop("继续录音失败：" + safeMessage(error));
        }
    }

    private void stopRecording() {
        if (recorder == null) {
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return;
        }
        try {
            recorder.stop();
            lastError = "";
        } catch (RuntimeException error) {
            lastError = "录音结束失败，片段可能过短";
            if (outputFile != null && outputFile.exists()) outputFile.delete();
        } finally {
            releaseRecorder();
            state = State.IDLE;
            captureKey = "";
            resetTimer();
            broadcastState();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
        }
    }

    private void failAndStop(String message) {
        lastError = message;
        releaseRecorder();
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
        recorder.release();
        recorder = null;
    }

    private static void resetTimer() {
        accumulatedMillis = 0L;
        activeSinceMillis = 0L;
    }

    private void startMicrophoneForeground(Notification notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void updateNotification(String status) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.notify(NOTIFICATION_ID, buildNotification(status));
    }

    private Notification buildNotification(String status) {
        Intent content = new Intent(this, PackageActivity.class)
                .putExtra(PackageActivity.EXTRA_CONFERENCE_ID, conferenceId)
                .putExtra(PackageActivity.EXTRA_SESSION_ID, sessionId)
                .putExtra(PackageActivity.EXTRA_ITEM_ID, itemId)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                0,
                content,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        String toggleAction = state == State.PAUSED ? ACTION_RESUME : ACTION_PAUSE;
        String toggleLabel = state == State.PAUSED ? "继续" : "暂停";
        PendingIntent toggle = serviceAction(toggleAction, 1);
        PendingIntent stop = serviceAction(ACTION_STOP, 2);

        Notification.Builder builder = new Notification.Builder(this, CHANNEL_ID);
        return builder
                .setSmallIcon(R.drawable.ic_app)
                .setContentTitle(title)
                .setContentText(status + " · 拍照时录音会继续")
                .setContentIntent(contentIntent)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .addAction(0, toggleLabel, toggle)
                .addAction(0, "结束", stop)
                .build();
    }

    private PendingIntent serviceAction(String action, int requestCode) {
        Intent intent = new Intent(this, AudioRecordingService.class).setAction(action);
        return PendingIntent.getService(
                this,
                requestCode,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private void createNotificationChannel() {
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "会议现场录音",
                NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("显示正在进行的会议报告录音");
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
    }

    private void broadcastState() {
        Intent update = new Intent(ACTION_STATE_CHANGED)
                .setPackage(getPackageName())
                .putExtra("state", state.name())
                .putExtra("error", lastError);
        sendBroadcast(update);
    }

    private static String value(Intent intent, String key) {
        String value = intent.getStringExtra(key);
        return value == null ? "" : value;
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName()
                : message;
    }
}
