package com.higs.conferencerecorder.data;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.File;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Locale;

public final class CaptureSessionStore {
    private static final String FILE_NAME = "capture_sessions";
    private static final DateTimeFormatter TIMESTAMP =
            DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss-SSS");

    public static final class CaptureBundle {
        public final File root;
        public final File audioDirectory;
        public final File imageDirectory;
        public final File transcriptDirectory;
        public final String sessionId;

        private CaptureBundle(File root) throws IOException {
            this.root = root;
            sessionId = root.getName();
            audioDirectory = requireDirectory(new File(root, "audio"));
            imageDirectory = requireDirectory(new File(root, "images"));
            transcriptDirectory = requireDirectory(new File(root, "transcript"));
        }

        public File[] audioFiles() {
            return matchingFiles(audioDirectory, ".m4a");
        }

        public File[] imageFiles() {
            return matchingFiles(imageDirectory, ".jpg");
        }

        public File nextAudioFile() {
            return nextFile(audioDirectory, "segment-", ".m4a");
        }

        public File nextImageFile() {
            return nextFile(imageDirectory, "image-", ".jpg");
        }

        public File transcriptFile() {
            return new File(transcriptDirectory, "transcript.txt");
        }

        public File transcriptMetadataFile() {
            return new File(transcriptDirectory, "transcription.json");
        }
    }

    private CaptureSessionStore() {
    }

    public static synchronized CaptureBundle currentOrCreate(
            Context context, String conferenceId, String itemId) throws IOException {
        File captureRoot = context.getExternalFilesDir("captures");
        if (captureRoot == null) throw new IOException("手机采集暂存区不可用");
        requireDirectory(captureRoot);

        String key = key(conferenceId, itemId);
        String savedPath = preferences(context).getString(key, "");
        if (savedPath != null && !savedPath.isEmpty()) {
            File saved = new File(savedPath);
            if (isInside(captureRoot, saved) && saved.isDirectory()) {
                return new CaptureBundle(saved);
            }
        }

        File itemRoot = requireDirectory(new File(
                new File(captureRoot, sanitize(conferenceId)), sanitize(itemId)));
        File sessionRoot = requireDirectory(new File(
                itemRoot, "capture-" + OffsetDateTime.now().format(TIMESTAMP)));
        preferences(context).edit().putString(key, sessionRoot.getAbsolutePath()).apply();
        return new CaptureBundle(sessionRoot);
    }

    public static synchronized CaptureBundle current(
            Context context, String conferenceId, String itemId) throws IOException {
        File captureRoot = context.getExternalFilesDir("captures");
        if (captureRoot == null) return null;
        String savedPath = preferences(context).getString(key(conferenceId, itemId), "");
        if (savedPath == null || savedPath.isEmpty()) return null;
        File saved = new File(savedPath);
        if (!isInside(captureRoot, saved) || !saved.isDirectory()) return null;
        return new CaptureBundle(saved);
    }

    public static String captureKey(String conferenceId, String itemId) {
        return sanitize(conferenceId) + ":" + sanitize(itemId);
    }

    public static boolean isManagedAudioFile(Context context, File file) {
        File captureRoot = context.getExternalFilesDir("captures");
        if (captureRoot == null || file == null) return false;
        try {
            return isInside(captureRoot, file)
                    && "audio".equals(file.getParentFile().getName())
                    && file.getName().endsWith(".m4a");
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    public static boolean isManagedTranscriptFile(
            Context context, File file, String expectedName) {
        File captureRoot = context.getExternalFilesDir("captures");
        if (captureRoot == null || file == null || expectedName == null) return false;
        try {
            File parent = file.getParentFile();
            return parent != null
                    && isInside(captureRoot, file)
                    && "transcript".equals(parent.getName())
                    && expectedName.equals(file.getName());
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE);
    }

    private static String key(String conferenceId, String itemId) {
        return "active:" + captureKey(conferenceId, itemId);
    }

    private static File requireDirectory(File directory) throws IOException {
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("无法创建采集暂存目录：" + directory.getName());
        }
        return directory;
    }

    private static File[] matchingFiles(File directory, String suffix) {
        File[] files = directory.listFiles(file -> file.isFile()
                && file.getName().endsWith(suffix)
                && file.length() > 0L);
        if (files == null) return new File[0];
        Arrays.sort(files, Comparator.comparing(File::getName));
        return files;
    }

    private static File nextFile(File directory, String prefix, String suffix) {
        int index = 1;
        while (true) {
            File candidate = new File(
                    directory,
                    String.format(Locale.ROOT, "%s%03d%s", prefix, index, suffix));
            if (!candidate.exists()) return candidate;
            index++;
        }
    }

    private static boolean isInside(File root, File candidate) {
        try {
            String rootPath = root.getCanonicalPath() + File.separator;
            String candidatePath = candidate.getCanonicalPath();
            return candidatePath.startsWith(rootPath);
        } catch (IOException error) {
            return false;
        }
    }

    private static String sanitize(String value) {
        String safe = value == null ? "unknown" : value.trim();
        safe = safe.replaceAll("[\\\\/:*?\"<>|]", "_");
        return safe.isEmpty() ? "unknown" : safe;
    }
}
