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

import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

/** Feeds live PCM to Android 13+'s caller-provided speech-recognition audio source. */
public final class LiveSystemTranscriber implements RecognitionListener, LiveTranscriber {
    private static final byte[] END = new byte[0];
    private static final int MAX_QUEUED_FRAMES = 20; // At most two seconds of 100 ms frames.

    private final Context context;
    private final ArrayList<String> biasingStrings;
    private final boolean onDevice;
    private final Listener listener;
    private final BlockingQueue<byte[]> audioQueue =
            new ArrayBlockingQueue<>(MAX_QUEUED_FRAMES);
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private SpeechRecognizer recognizer;
    private ParcelFileDescriptor readPipe;
    private ParcelFileDescriptor writePipe;
    private Thread writerThread;
    private volatile boolean finishing;
    private volatile boolean closed;
    private boolean terminal;
    private String lastPartial = "";
    private int droppedFrames;

    public LiveSystemTranscriber(
            Context context,
            List<String> biasingStrings,
            boolean onDevice,
            Listener listener) {
        this.context = context.getApplicationContext();
        this.biasingStrings = new ArrayList<>(biasingStrings);
        this.onDevice = onDevice;
        this.listener = listener;
    }

    @SuppressLint("InlinedApi")
    @Override
    public void start(int sampleRate) throws IOException {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            throw new IOException("英文实时转写需要 Android 13 或更高版本");
        }
        ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createPipe();
        readPipe = pipe[0];
        writePipe = pipe[1];
        try {
            recognizer = onDevice
                    ? SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
                    : SpeechRecognizer.createSpeechRecognizer(context);
            recognizer.setRecognitionListener(this);
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US");
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, onDevice);
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, readPipe);
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, 1);
            intent.putExtra(
                    RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING,
                    AudioFormat.ENCODING_PCM_16BIT);
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, sampleRate);
            intent.putExtra(
                    RecognizerIntent.EXTRA_SEGMENTED_SESSION,
                    RecognizerIntent.EXTRA_AUDIO_SOURCE);
            intent.putStringArrayListExtra(
                    RecognizerIntent.EXTRA_BIASING_STRINGS,
                    biasingStrings);
            recognizer.startListening(intent);
            startWriter();
            listener.onStatus(onDevice ? "本机英文字幕启动中" : "系统英文字幕启动中");
        } catch (RuntimeException error) {
            close();
            throw new IOException("无法启动英文实时转写：" + safeMessage(error), error);
        }
    }

    /** Never blocks microphone capture. Old frames are discarded if recognition falls behind. */
    @Override
    public void offer(byte[] pcm, int length) {
        if (closed || finishing || length <= 0) return;
        byte[] copy = Arrays.copyOf(pcm, length);
        if (audioQueue.offer(copy)) return;
        audioQueue.poll();
        if (!audioQueue.offer(copy)) return;
        droppedFrames++;
        if (droppedFrames == 1 || droppedFrames % 50 == 0) {
            listener.onStatus("英文字幕处理较慢，录音仍在正常保存");
        }
    }

    /** Drains queued audio and closes the pipe so segmented recognition can return final results. */
    @Override
    public void finish() {
        if (closed || finishing) return;
        finishing = true;
        while (!audioQueue.offer(END)) audioQueue.poll();
        listener.onStatus("录音已保存，正在整理最后的英文字幕");
    }

    private void startWriter() {
        writerThread = new Thread(() -> {
            try (FileOutputStream output = new FileOutputStream(writePipe.getFileDescriptor())) {
                while (!closed) {
                    byte[] frame = audioQueue.take();
                    if (frame == END) break;
                    output.write(frame);
                }
                output.flush();
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            } catch (IOException error) {
                if (!closed) mainHandler.post(() ->
                        fail("系统识别器无法接收实时音频"));
            } finally {
                closeQuietly(writePipe);
                writePipe = null;
            }
        }, "conference-live-transcription-audio");
        writerThread.start();
    }

    @Override
    public void onReadyForSpeech(Bundle params) {
        listener.onStatus(onDevice ? "本机英文字幕运行中" : "系统英文字幕运行中");
    }

    @Override
    public void onBeginningOfSpeech() {
        listener.onStatus("正在识别英文报告");
    }

    @Override
    public void onRmsChanged(float rmsdB) {
    }

    @Override
    public void onBufferReceived(byte[] buffer) {
    }

    @Override
    public void onEndOfSpeech() {
        listener.onStatus("正在确认英文句子");
    }

    @Override
    public void onError(int error) {
        fail(errorMessage(error));
    }

    @Override
    public void onResults(Bundle results) {
        String text = best(results);
        if (!text.isEmpty()) listener.onSegment(text);
        complete();
    }

    @Override
    public void onPartialResults(Bundle partialResults) {
        lastPartial = best(partialResults);
        if (!lastPartial.isEmpty()) listener.onPartial(lastPartial);
    }

    @Override
    public void onEvent(int eventType, Bundle params) {
    }

    @Override
    public void onSegmentResults(Bundle segmentResults) {
        String text = best(segmentResults);
        if (!text.isEmpty()) {
            lastPartial = "";
            listener.onSegment(text);
        }
    }

    @Override
    public void onEndOfSegmentedSession() {
        complete();
    }

    private void complete() {
        if (terminal) return;
        terminal = true;
        listener.onCompleted();
        release(false);
    }

    private void fail(String message) {
        if (terminal) return;
        terminal = true;
        listener.onFailed(message, lastPartial);
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
        closed = true;
        audioQueue.clear();
        audioQueue.offer(END);
        closeQuietly(writePipe);
        writePipe = null;
        closeQuietly(readPipe);
        readPipe = null;
        if (writerThread != null) writerThread.interrupt();
        if (recognizer != null) {
            if (cancelRecognizer) {
                try {
                    recognizer.cancel();
                } catch (RuntimeException ignored) {
                }
            }
            recognizer.destroy();
            recognizer = null;
        }
    }

    private static String best(Bundle results) {
        if (results == null) return "";
        ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return matches == null || matches.isEmpty() ? "" : matches.get(0).trim();
    }

    private static void closeQuietly(ParcelFileDescriptor descriptor) {
        if (descriptor == null) return;
        try {
            descriptor.close();
        } catch (IOException ignored) {
        }
    }

    private static String errorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "系统英文识别器无法读取音频";
            case SpeechRecognizer.ERROR_CLIENT:
                return "系统英文识别任务被中断";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "系统英文识别缺少权限";
            case SpeechRecognizer.ERROR_NETWORK:
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                return "系统英文识别网络不可用";
            case SpeechRecognizer.ERROR_NO_MATCH:
                return "系统暂时没有识别出英文";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "系统英文识别器正忙";
            case SpeechRecognizer.ERROR_SERVER:
            case SpeechRecognizer.ERROR_SERVER_DISCONNECTED:
                return "系统英文识别服务暂时不可用";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "系统英文识别没有接收到语音";
            case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED:
                return "系统识别器不支持英语";
            case SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE:
                return "系统英语识别模型尚未就绪";
            case SpeechRecognizer.ERROR_TOO_MANY_REQUESTS:
                return "系统英文识别请求过多";
            default:
                return "系统英文识别失败（错误 " + error + "）";
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName()
                : message;
    }
}
