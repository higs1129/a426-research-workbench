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
            metadata.put("language", "en-US");
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

    public static void saveLive(
            File transcriptFile,
            File metadataFile,
            String text,
            String engineMode,
            String status,
            File sourceAudio,
            int segmentCount) throws IOException {
        String cleanText = text == null ? "" : text.trim();
        if (cleanText.isEmpty()) throw new IOException("英文实时字幕为空");
        String previousText = readUtf8(transcriptFile);
        String combinedText = previousText.isEmpty()
                ? cleanText : previousText + "\n" + cleanText;
        int combinedSegments = segmentCount;
        String combinedStatus = status;
        JSONArray files = new JSONArray();
        java.util.LinkedHashSet<String> sourceNames = new java.util.LinkedHashSet<>();
        String previousMetadata = readUtf8(metadataFile);
        if (!previousMetadata.isEmpty()) {
            try {
                JSONObject previous = new JSONObject(previousMetadata);
                combinedSegments += previous.optInt("segments", 0);
                if ("partial".equals(previous.optString("status"))) combinedStatus = "partial";
                JSONArray previousFiles = previous.optJSONArray("sourceAudio");
                if (previousFiles != null) {
                    for (int index = 0; index < previousFiles.length(); index++) {
                        String name = previousFiles.optString(index, "");
                        if (!name.isEmpty()) sourceNames.add(name);
                    }
                }
            } catch (JSONException ignored) {
                combinedStatus = "partial";
            }
        }
        if (sourceAudio != null) sourceNames.add(sourceAudio.getName());
        for (String name : sourceNames) files.put(name);
        writeUtf8(transcriptFile, combinedText + "\n");
        JSONObject metadata = new JSONObject();
        try {
            metadata.put("schemaVersion", 1);
            metadata.put("engine", "android.speech.SpeechRecognizer");
            metadata.put("engineMode", engineMode);
            metadata.put("language", "en-US");
            metadata.put("status", combinedStatus);
            metadata.put("createdAt", OffsetDateTime.now().format(
                    DateTimeFormatter.ISO_OFFSET_DATE_TIME));
            metadata.put("characters", combinedText.length());
            metadata.put("segments", combinedSegments);
            metadata.put("sourceAudio", files);
            writeUtf8(metadataFile, metadata.toString(2) + "\n");
        } catch (JSONException impossible) {
            throw new IOException("无法生成英文实时转写元数据", impossible);
        }
    }

    public static void delete(CaptureSessionStore.CaptureBundle capture) throws IOException {
        if (capture == null) return;
        deleteIfExists(capture.transcriptMetadataFile());
        deleteIfExists(capture.transcriptFile());
    }

    private static void writeUtf8(File target, String value) throws IOException {
        try (FileOutputStream output = new FileOutputStream(target, false)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        }
    }

    private static void deleteIfExists(File target) throws IOException {
        if (target != null && target.exists() && !target.delete()) {
            throw new IOException("无法删除 " + target.getName());
        }
    }

    private static String readUtf8(File source) {
        if (source == null || !source.isFile() || source.length() <= 0L
                || source.length() > Integer.MAX_VALUE) return "";
        byte[] buffer = new byte[(int) source.length()];
        try (FileInputStream input = new FileInputStream(source)) {
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
}
