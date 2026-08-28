package com.higs.conferencerecorder.transcription;

import org.json.JSONException;
import org.json.JSONObject;
import org.vosk.Model;
import org.vosk.Recognizer;

import java.io.File;
import java.io.IOException;
import java.util.Arrays;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

/** Offline English streaming recognizer fed by the recorder's existing PCM stream. */
public final class VoskLiveTranscriber implements LiveTranscriber {
    private static final byte[] END = new byte[0];
    private static final int MAX_QUEUED_FRAMES = 30;

    private final File modelDirectory;
    private final Listener listener;
    private final BlockingQueue<byte[]> audioQueue =
            new ArrayBlockingQueue<>(MAX_QUEUED_FRAMES);
    private volatile boolean finishing;
    private volatile boolean closed;
    private Thread worker;
    private String lastPartial = "";
    private int droppedFrames;

    public VoskLiveTranscriber(File modelDirectory, Listener listener) {
        this.modelDirectory = modelDirectory;
        this.listener = listener;
    }

    @Override
    public void start(int sampleRate) throws IOException {
        if (!modelDirectory.isDirectory()) throw new IOException("离线英文模型尚未安装");
        worker = new Thread(() -> recognize(sampleRate), "conference-vosk-live-asr");
        worker.start();
    }

    @Override
    public void offer(byte[] pcm, int length) {
        if (closed || finishing || length <= 0) return;
        byte[] copy = Arrays.copyOf(pcm, length);
        if (audioQueue.offer(copy)) return;
        audioQueue.poll();
        if (!audioQueue.offer(copy)) return;
        droppedFrames++;
        if (droppedFrames == 1 || droppedFrames % 50 == 0) {
            listener.onStatus("离线字幕处理较慢，录音仍在正常保存");
        }
    }

    @Override
    public void finish() {
        if (closed || finishing) return;
        finishing = true;
        while (!audioQueue.offer(END)) audioQueue.poll();
        listener.onStatus("录音已保存，正在整理最后的离线英文字幕");
    }

    @Override
    public void close() {
        closed = true;
        audioQueue.clear();
        audioQueue.offer(END);
        if (worker != null) worker.interrupt();
    }

    private void recognize(int sampleRate) {
        listener.onStatus("正在加载离线英文模型");
        try (Model model = new Model(modelDirectory.getAbsolutePath());
             Recognizer recognizer = new Recognizer(model, (float) sampleRate)) {
            listener.onStatus("离线英文字幕运行中");
            while (!closed) {
                byte[] frame = audioQueue.take();
                if (frame == END) {
                    String finalText = value(recognizer.getFinalResult(), "text");
                    if (!finalText.isEmpty()) listener.onSegment(finalText);
                    listener.onCompleted();
                    return;
                }
                if (recognizer.acceptWaveForm(frame, frame.length)) {
                    String text = value(recognizer.getResult(), "text");
                    if (!text.isEmpty()) listener.onSegment(text);
                    lastPartial = "";
                } else {
                    String partial = value(recognizer.getPartialResult(), "partial");
                    if (!partial.isEmpty() && !partial.equals(lastPartial)) {
                        lastPartial = partial;
                        listener.onPartial(partial);
                    }
                }
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        } catch (IOException | RuntimeException error) {
            if (!closed) listener.onFailed(
                    "离线英文识别失败：" + safeMessage(error), lastPartial);
        }
    }

    private static String value(String json, String key) {
        if (json == null || json.isEmpty()) return "";
        try {
            return new JSONObject(json).optString(key, "").trim();
        } catch (JSONException ignored) {
            return "";
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName() : message;
    }
}
