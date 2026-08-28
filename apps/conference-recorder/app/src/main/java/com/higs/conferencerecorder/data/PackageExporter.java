package com.higs.conferencerecorder.data;

import android.content.Context;
import android.net.Uri;

import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

import org.json.JSONException;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;

public final class PackageExporter {
    public static final class ExportResult {
        public final String displayPath;

        private ExportResult(String displayPath) {
            this.displayPath = displayPath;
        }
    }

    private PackageExporter() {
    }

    public static ExportResult exportPackage(
            Context context,
            Conference conference,
            SessionBlock session,
            ProgramItem item,
            String fieldNote) throws IOException {
        Uri target = requireTarget(context);
        String timestamp = timestampForPath();
        String kindFolder = item.isPoster() ? "posters" : "talks";
        String packageFolder = "package-" + timestamp;
        CaptureSessionStore.CaptureBundle capture =
                CaptureSessionStore.current(context, conference.id, item.id);
        File[] audioFiles = capture == null || item.isPoster()
                ? new File[0] : capture.audioFiles();
        File[] imageFiles = capture == null ? new File[0] : capture.imageFiles();
        File transcriptFile = capture == null || item.isPoster()
                ? null : capture.transcriptFile();
        File transcriptMetadataFile = capture == null || item.isPoster()
                ? null : capture.transcriptMetadataFile();
        boolean hasTranscript = transcriptFile != null
                && transcriptFile.isFile()
                && transcriptFile.length() > 0L;
        boolean hasTranscriptMetadata = hasTranscript
                && transcriptMetadataFile.isFile()
                && transcriptMetadataFile.length() > 0L;
        StorageTreeWriter writer = new StorageTreeWriter(context, target);
        Uri packageDirectory = writer.ensureDirectory(
                "ConferenceRecorder",
                conference.id,
                kindFolder,
                item.id,
                "packages",
                packageFolder);
        Uri notesDirectory = writer.ensureDirectory(
                "ConferenceRecorder",
                conference.id,
                kindFolder,
                item.id,
                "packages",
                packageFolder,
                "notes");
        Uri audioDirectory = audioFiles.length == 0 ? null : writer.ensureDirectory(
                "ConferenceRecorder",
                conference.id,
                kindFolder,
                item.id,
                "packages",
                packageFolder,
                "audio");
        Uri imageDirectory = imageFiles.length == 0 ? null : writer.ensureDirectory(
                "ConferenceRecorder",
                conference.id,
                kindFolder,
                item.id,
                "packages",
                packageFolder,
                "images");
        Uri transcriptDirectory = hasTranscript ? writer.ensureDirectory(
                "ConferenceRecorder",
                conference.id,
                kindFolder,
                item.id,
                "packages",
                packageFolder,
                "transcript") : null;

        for (File audio : audioFiles) {
            writer.copyNewFile(audioDirectory, audio.getName(), "audio/mp4", audio);
        }
        for (File image : imageFiles) {
            writer.copyNewFile(imageDirectory, image.getName(), "image/jpeg", image);
        }
        if (hasTranscript) {
            writer.copyNewFile(
                    transcriptDirectory,
                    "transcript.txt",
                    "text/plain",
                    transcriptFile);
            if (hasTranscriptMetadata) {
                writer.copyNewFile(
                        transcriptDirectory,
                        "transcription.json",
                        "application/json",
                        transcriptMetadataFile);
            }
        }
        writer.writeNewFile(
                packageDirectory,
                "manifest.json",
                "application/json",
                buildManifest(
                        conference,
                        session,
                        item,
                        timestamp,
                        capture,
                        audioFiles,
                        imageFiles,
                        hasTranscript,
                        hasTranscriptMetadata));
        writer.writeNewFile(
                notesDirectory,
                "field-note.md",
                "text/markdown",
                buildNote(conference, session, item, fieldNote));
        writer.writeNewFile(
                packageDirectory,
                "READY",
                "text/plain",
                "capture_package_ready\n");

        String displayPath = "ConferenceRecorder/" + conference.id + "/" + kindFolder + "/"
                + item.id + "/packages/" + packageFolder + "/";
        StorageTargetStore.saveLastExport(context, displayPath);
        return new ExportResult(displayPath);
    }

    public static ExportResult writeConnectionTest(Context context) throws IOException {
        Uri target = requireTarget(context);
        String timestamp = timestampForPath();
        String packageFolder = "test-" + timestamp;
        StorageTreeWriter writer = new StorageTreeWriter(context, target);
        Uri directory = writer.ensureDirectory(
                "ConferenceRecorder", "_connection-tests", packageFolder);
        JSONObject status = new JSONObject();
        String statusJson;
        try {
            status.put("schemaVersion", 1);
            status.put("kind", "synology_folder_write_test");
            status.put("sourceDevice", "v2359a");
            status.put("createdAt", OffsetDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME));
            status.put("expectedNextHop", "Synology Drive mobile sync task");
            statusJson = status.toString(2) + "\n";
        } catch (JSONException impossible) {
            throw new IOException("无法生成测试清单", impossible);
        }
        writer.writeNewFile(directory, "status.json", "application/json", statusJson);
        writer.writeNewFile(directory, "READY", "text/plain", "connection_test_ready\n");
        String displayPath = "ConferenceRecorder/_connection-tests/" + packageFolder + "/";
        StorageTargetStore.saveLastExport(context, displayPath);
        return new ExportResult(displayPath);
    }

    private static Uri requireTarget(Context context) throws IOException {
        if (!StorageTargetStore.isConfigured(context)) {
            throw new IOException("尚未选择可写的同步根目录");
        }
        Uri target = StorageTargetStore.targetUri(context);
        if (target == null) throw new IOException("同步根目录授权已失效");
        return target;
    }

    private static String buildManifest(
            Conference conference,
            SessionBlock session,
            ProgramItem item,
            String timestamp,
            CaptureSessionStore.CaptureBundle capture,
            File[] audioFiles,
            File[] imageFiles,
            boolean hasTranscript,
            boolean hasTranscriptMetadata) throws IOException {
        JSONObject manifest = new JSONObject();
        try {
            manifest.put("schemaVersion", 2);
            manifest.put("packageId", item.id + "-" + timestamp);
            manifest.put("conferenceId", conference.id);
            manifest.put("itemId", item.id);
            manifest.put("itemType", item.isPoster() ? "poster" : "talk");
            manifest.put("title", item.title);
            manifest.put("speaker", item.speaker);
            manifest.put("affiliation", item.affiliation);
            manifest.put("code", item.code);
            manifest.put("sessionId", session == null ? JSONObject.NULL : session.id);
            manifest.put("start", item.start);
            manifest.put("end", item.end);
            manifest.put("exportedAt", OffsetDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME));
            manifest.put("sourceDevice", "v2359a");
            manifest.put("captureSessionId", capture == null ? JSONObject.NULL : capture.sessionId);
            manifest.put("captureStatus", captureStatus(audioFiles, imageFiles));
            manifest.put("synologyStatus", "waiting_for_drive_mobile");
            JSONObject files = new JSONObject();
            files.put("fieldNote", "notes/field-note.md");
            files.put("audio", fileEntries("audio", audioFiles));
            files.put("images", fileEntries("images", imageFiles));
            files.put("transcript", hasTranscript
                    ? "transcript/transcript.txt" : JSONObject.NULL);
            files.put("transcriptionMetadata", hasTranscriptMetadata
                    ? "transcript/transcription.json" : JSONObject.NULL);
            manifest.put("files", files);
            manifest.put(
                    "transcriptionStatus",
                    hasTranscript
                            ? transcriptionStatus(capture, hasTranscriptMetadata)
                            : "not_generated");
            return manifest.toString(2) + "\n";
        } catch (JSONException error) {
            throw new IOException("无法生成报告包清单", error);
        }
    }

    private static String buildNote(
            Conference conference,
            SessionBlock session,
            ProgramItem item,
            String note) {
        StringBuilder markdown = new StringBuilder();
        markdown.append("---\n");
        markdown.append("type: ").append(item.isPoster() ? "conference-poster" : "conference-talk").append("\n");
        markdown.append("conference_id: ").append(conference.id).append("\n");
        markdown.append("item_id: ").append(item.id).append("\n");
        if (session != null) markdown.append("session_id: ").append(session.id).append("\n");
        markdown.append("source_device: v2359a\n");
        markdown.append("status: field-note\n");
        markdown.append("---\n\n");
        markdown.append("# ").append(item.title).append("\n\n");
        markdown.append("- 报告人/作者：").append(item.speaker.isEmpty() ? "待确认" : item.speaker).append("\n");
        markdown.append("- 单位：").append(item.affiliation.isEmpty() ? "待确认" : item.affiliation).append("\n");
        markdown.append("- 时间：").append(item.timeRange()).append("\n\n");
        markdown.append("## 现场备注\n\n");
        markdown.append(note == null || note.trim().isEmpty() ? "（未填写）" : note.trim());
        markdown.append("\n");
        return markdown.toString();
    }

    private static String timestampForPath() {
        return OffsetDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss-SSS"));
    }

    private static String captureStatus(File[] audioFiles, File[] imageFiles) {
        if (audioFiles.length > 0 && imageFiles.length > 0) return "audio_and_images";
        if (audioFiles.length > 0) return "audio_only";
        if (imageFiles.length > 0) return "images_only";
        return "metadata_and_note_only";
    }

    private static String transcriptionStatus(
            CaptureSessionStore.CaptureBundle capture,
            boolean hasMetadata) {
        if (!hasMetadata || capture == null) return "complete";
        File metadata = capture.transcriptMetadataFile();
        if (metadata.length() <= 0L || metadata.length() > Integer.MAX_VALUE) return "complete";
        byte[] buffer = new byte[(int) metadata.length()];
        try (FileInputStream input = new FileInputStream(metadata)) {
            int offset = 0;
            while (offset < buffer.length) {
                int read = input.read(buffer, offset, buffer.length - offset);
                if (read < 0) break;
                offset += read;
            }
            JSONObject value = new JSONObject(new String(
                    buffer, 0, offset, java.nio.charset.StandardCharsets.UTF_8));
            return "partial".equals(value.optString("status")) ? "partial" : "complete";
        } catch (IOException | JSONException ignored) {
            return "complete";
        }
    }

    private static JSONArray fileEntries(String folder, File[] sourceFiles) throws IOException {
        JSONArray entries = new JSONArray();
        for (File source : sourceFiles) {
            JSONObject entry = new JSONObject();
            try {
                entry.put("path", folder + "/" + source.getName());
                entry.put("bytes", source.length());
                entry.put("sha256", sha256(source));
                entries.put(entry);
            } catch (JSONException impossible) {
                throw new IOException("无法生成采集文件清单", impossible);
            }
        }
        return entries;
    }

    private static String sha256(File source) throws IOException {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IOException("手机不支持 SHA-256", impossible);
        }
        try (FileInputStream input = new FileInputStream(source)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                digest.update(buffer, 0, read);
            }
        }
        StringBuilder value = new StringBuilder();
        for (byte part : digest.digest()) value.append(String.format("%02x", part));
        return value.toString();
    }
}
