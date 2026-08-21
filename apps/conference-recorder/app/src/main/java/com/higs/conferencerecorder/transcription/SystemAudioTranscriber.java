package com.higs.conferencerecorder.transcription;

import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.media.AudioFormat;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public final class SystemAudioTranscriber implements RecognitionListener, AutoCloseable {
    public enum Availability {
        ON_DEVICE,
        SYSTEM_MAY_USE_NETWORK,
        ANDROID_TOO_OLD,
        UNAVAILABLE
    }

    public interface Listener {
        void onStatus(String status);

        void onPartial(String text);

        void onFinished(Result result);

        void onFailed(String message, String partialText);
    }

    public static final class Result {
        public final String text;
        public final String engineMode;
        public final int segmentCount;

        private Result(String text, String engineMode, int segmentCount) {
            this.text = text;
            this.engineMode = engineMode;
            this.segmentCount = segmentCount;
        }
    }

    private final Context context;
    private final File[] audioFiles;
    private final ArrayList<String> biasingStrings;
    private final boolean onDevice;
    private final Listener listener;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final List<String> segments = new ArrayList<>();
    private final Set<String> seenSegments = new LinkedHashSet<>();

    private SpeechRecognizer recognizer;
    private ParcelFileDescriptor readPipe;
    private ParcelFileDescriptor writePipe;
    private Thread streamThread;
    private volatile boolean cancelled;
    private volatile boolean streamCompleted;
    private boolean terminal;

    public SystemAudioTranscriber(
            Context context,
            File[] audioFiles,
            List<String> biasingStrings,
            boolean onDevice,
            Listener listener) {
        this.context = context.getApplicationContext();
        this.audioFiles = audioFiles.clone();
        this.biasingStrings = new ArrayList<>(biasingStrings);
        this.onDevice = onDevice;
        this.listener = listener;
    }

    public static Availability availability(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return Availability.ANDROID_TOO_OLD;
        }
        if (SpeechRecognizer.isOnDeviceRecognitionAvailable(context)) {
            return Availability.ON_DEVICE;
        }
        if (SpeechRecognizer.isRecognitionAvailable(context)) {
            return Availability.SYSTEM_MAY_USE_NETWORK;
        }
        return Availability.UNAVAILABLE;
    }

    public void start() throws IOException {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            throw new IOException("已有录音转写需要 Android 13 或更高版本");
        }
        M4aPcmStreamer.AudioSpec spec = M4aPcmStreamer.probe(audioFiles);
        ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createPipe();
        readPipe = pipe[0];
        writePipe = pipe[1];

        try {
            recognizer = onDevice
                    ? SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
                    : SpeechRecognizer.createSpeechRecognizer(context);
            recognizer.setRecognitionListener(this);
            Intent intent = recognitionIntent(spec);
            listener.onStatus(onDevice ? "正在启动本机识别…" : "正在启动系统识别…");
            recognizer.startListening(intent);
            startStreaming(spec);
        } catch (RuntimeException error) {
            close();
            throw new IOException("无法启动系统转写：" + safeMessage(error), error);
        }
    }

    @SuppressLint("InlinedApi")
    private Intent recognitionIntent(M4aPcmStreamer.AudioSpec spec) {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, onDevice);
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, readPipe);
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, spec.channelCount);
        intent.putExtra(
                RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING,
                AudioFormat.ENCODING_PCM_16BIT);
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, spec.sampleRate);
        intent.putExtra(
                RecognizerIntent.EXTRA_SEGMENTED_SESSION,
                RecognizerIntent.EXTRA_AUDIO_SOURCE);
        intent.putStringArrayListExtra(RecognizerIntent.EXTRA_BIASING_STRINGS, biasingStrings);
        return intent;
    }

    private void startStreaming(M4aPcmStreamer.AudioSpec spec) {
        streamThread = new Thread(() -> {
            try (FileOutputStream output = new FileOutputStream(writePipe.getFileDescriptor())) {
                M4aPcmStreamer.stream(
                        audioFiles,
                        output,
                        spec,
                        () -> cancelled,
                        (completed, total) -> mainHandler.post(() -> {
                            if (!terminal) {
                                listener.onStatus("已送入录音 " + completed + "/" + total + " 段，正在识别…");
                            }
                        }));
                if (!cancelled) streamCompleted = true;
            } catch (IOException error) {
                if (!cancelled) {
                    mainHandler.post(() -> fail("无法读取录音：" + safeMessage(error)));
                }
            } finally {
                closeQuietly(writePipe);
                writePipe = null;
            }
        }, "conference-system-transcription-audio");
        streamThread.start();
    }

    @Override
    public void onReadyForSpeech(Bundle params) {
        listener.onStatus("系统识别器已就绪，正在转写…");
    }

    @Override
    public void onBeginningOfSpeech() {
        listener.onStatus("已检测到报告语音，正在转写…");
    }

    @Override
    public void onRmsChanged(float rmsdB) {
    }

    @Override
    public void onBufferReceived(byte[] buffer) {
    }

    @Override
    public void onEndOfSpeech() {
        listener.onStatus("音频已读取，正在整理结果…");
    }

    @Override
    public void onError(int error) {
        fail(errorMessage(error));
    }

    @Override
    public void onResults(Bundle results) {
        appendBest(results);
        if (streamCompleted) {
            succeed();
        } else {
            mainHandler.postDelayed(() -> {
                if (terminal) return;
                if (streamCompleted) {
                    succeed();
                } else {
                    fail("系统识别服务未接收完整录音，本次不保存为完整逐字稿");
                }
            }, 300L);
        }
    }

    @Override
    public void onPartialResults(Bundle partialResults) {
        String value = best(partialResults);
        if (!value.isEmpty()) listener.onPartial(value);
    }

    @Override
    public void onEvent(int eventType, Bundle params) {
    }

    @Override
    public void onSegmentResults(Bundle segmentResults) {
        appendBest(segmentResults);
        listener.onPartial(joinedText());
    }

    @Override
    public void onEndOfSegmentedSession() {
        succeed();
    }

    private void appendBest(Bundle results) {
        String value = best(results);
        if (!value.isEmpty() && seenSegments.add(value)) segments.add(value);
    }

    private static String best(Bundle results) {
        if (results == null) return "";
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return matches == null || matches.isEmpty() ? "" : matches.get(0).trim();
    }

    private String joinedText() {
        StringBuilder text = new StringBuilder();
        for (String segment : segments) {
            if (segment.isEmpty()) continue;
            if (text.length() > 0) text.append('\n');
            text.append(segment);
        }
        return text.toString().trim();
    }

    private void succeed() {
        if (terminal) return;
        String text = joinedText();
        if (text.isEmpty()) {
            fail("系统识别结束，但没有返回文字");
            return;
        }
        terminal = true;
        listener.onFinished(new Result(
                text,
                onDevice ? "android_on_device" : "android_system_service",
                segments.size()));
        release(false);
    }

    private void fail(String message) {
        if (terminal) return;
        terminal = true;
        listener.onFailed(message, joinedText());
        release(false);
    }

    @Override
    public void close() {
        if (terminal) {
            release(false);
            return;
        }
        terminal = true;
        release(true);
    }

    private void release(boolean cancelRecognizer) {
        cancelled = true;
        closeQuietly(writePipe);
        writePipe = null;
        closeQuietly(readPipe);
        readPipe = null;
        if (recognizer != null) {
            if (cancelRecognizer) {
                try {
                    recognizer.cancel();
                } catch (RuntimeException ignored) {
                    // Some vendor services throw while already finishing.
                }
            }
            recognizer.destroy();
            recognizer = null;
        }
    }

    private static void closeQuietly(ParcelFileDescriptor descriptor) {
        if (descriptor == null) return;
        try {
            descriptor.close();
        } catch (IOException ignored) {
            // Closing is best effort during recognizer teardown.
        }
    }

    private static String errorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "系统识别器无法读取这段音频";
            case SpeechRecognizer.ERROR_CLIENT:
                return "系统识别任务被中断";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "缺少系统语音识别权限";
            case SpeechRecognizer.ERROR_NETWORK:
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                return "系统识别服务网络不可用";
            case SpeechRecognizer.ERROR_NO_MATCH:
                return "系统没有从录音中识别到文字";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "系统识别器正忙，请稍后重试";
            case SpeechRecognizer.ERROR_SERVER:
            case SpeechRecognizer.ERROR_SERVER_DISCONNECTED:
                return "系统识别服务暂时不可用";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "系统识别器未接收到录音数据";
            case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED:
                return "系统识别器不支持中文";
            case SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE:
                return "系统中文识别模型尚未就绪";
            case SpeechRecognizer.ERROR_TOO_MANY_REQUESTS:
                return "系统识请求过多，请稍后重试";
            default:
                return "系统识别失败（错误 " + error + "）";
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName()
                : message;
    }
}
