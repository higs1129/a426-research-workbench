package com.higs.conferencerecorder.data;

import com.higs.conferencerecorder.transcription.SystemAudioTranscriber;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;

public final class TranscriptStore {
    private TranscriptStore() {
    }

    public static boolean hasTranscript(CaptureSessionStore.CaptureBundle capture) {
        File transcript = capture == null ? null : capture.transcriptFile();
        return transcript != null && transcript.isFile() && transcript.length() > 0L;
    }

    public static String read(CaptureSessionStore.CaptureBundle capture) {
        if (!hasTranscript(capture)) return "";
        File transcript = capture.transcriptFile();
        byte[] buffer = new byte[(int) transcript.length()];
        try (FileInputStream input = new FileInputStream(transcript)) {
            int offset = 0;
            while (offset < buffer.length) {
                int read = input.read(buffer, offset, buffer.length - offset);
                if (read < 0) break;
                offset += read;
            }
            return new String(buffer, 0, offset, StandardCharsets.UTF_8).trim();
        } catch (IOException error) {
            return "";
        }
    }

    public static void save(
            CaptureSessionStore.CaptureBundle capture,
            SystemAudioTranscriber.Result result,
            File[] sourceAudio) throws IOException {
        writeUtf8(capture.transcriptFile(), result.text.trim() + "\n");
        JSONObject metadata = new JSONObject();
        try {
            metadata.put("schemaVersion", 1);
            metadata.put("engine", "android.speech.SpeechRecognizer");
            metadata.put("engineMode", result.engineMode);
            metadata.put("language", "zh-CN");
            metadata.put("status", "complete");
            metadata.put("createdAt", OffsetDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME));
            metadata.put("characters", result.text.trim().length());
            metadata.put("segments", result.segmentCount);
            JSONArray files = new JSONArray();
            for (File audio : sourceAudio) files.put(audio.getName());
            metadata.put("sourceAudio", files);
            writeUtf8(capture.transcriptMetadataFile(), metadata.toString(2) + "\n");
        } catch (JSONException impossible) {
            throw new IOException("无法生成转写元数据", impossible);
        }
    }

    private static void writeUtf8(File target, String value) throws IOException {
        try (FileOutputStream output = new FileOutputStream(target, false)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        }
    }
}
