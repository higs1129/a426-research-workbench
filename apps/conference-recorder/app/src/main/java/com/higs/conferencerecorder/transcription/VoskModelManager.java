package com.higs.conferencerecorder.transcription;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class VoskModelManager {
    public interface Listener {
        void onProgress(String status, int percent);

        void onComplete();

        void onFailed(String message);
    }

    public static final String MODEL_NAME = "vosk-model-small-en-us-0.15";
    public static final String DOWNLOAD_URL =
            "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip";
    private static final long MAX_ARCHIVE_BYTES = 100L * 1024L * 1024L;
    private static final long MAX_EXTRACTED_BYTES = 200L * 1024L * 1024L;
    private static final AtomicBoolean DOWNLOADING = new AtomicBoolean();

    private VoskModelManager() {
    }

    public static File modelDirectory(Context context) {
        return new File(baseDirectory(context), MODEL_NAME);
    }

    public static boolean isInstalled(Context context) {
        File model = modelDirectory(context);
        return new File(model, ".ready").isFile()
                && new File(model, "am/final.mdl").isFile()
                && new File(model, "conf/model.conf").isFile()
                && new File(model, "graph/phones/word_boundary.int").isFile();
    }

    public static boolean isDownloading() {
        return DOWNLOADING.get();
    }

    public static void downloadAndInstall(Context context, Listener listener) {
        Context appContext = context.getApplicationContext();
        Handler main = new Handler(Looper.getMainLooper());
        if (isInstalled(appContext)) {
            main.post(listener::onComplete);
            return;
        }
        if (!DOWNLOADING.compareAndSet(false, true)) {
            main.post(() -> listener.onFailed("离线英文模型正在下载"));
            return;
        }
        new Thread(() -> {
            try {
                install(appContext, (status, percent) ->
                        main.post(() -> listener.onProgress(status, percent)));
                main.post(listener::onComplete);
            } catch (IOException error) {
                main.post(() -> listener.onFailed(safeMessage(error)));
            } finally {
                DOWNLOADING.set(false);
            }
        }, "conference-vosk-model-download").start();
    }

    private interface Progress {
        void update(String status, int percent);
    }

    private static void install(Context context, Progress progress) throws IOException {
        File base = baseDirectory(context);
        requireDirectory(base);
        if (new StatFs(base.getAbsolutePath()).getAvailableBytes()
                < 150L * 1024L * 1024L) {
            throw new IOException("手机可用空间不足 150 MB，无法安装离线英文模型");
        }
        File archive = new File(base, MODEL_NAME + ".zip.part");
        File staging = new File(base, "installing-" + MODEL_NAME);
        File destination = modelDirectory(context);
        deleteInside(base, archive);
        deleteInside(base, staging);
        progress.update("正在下载约 40 MB 离线英文模型", 0);
        download(archive, progress);
        progress.update("正在安装离线英文模型", 96);
        requireDirectory(staging);
        unzip(archive, staging);
        File extracted = new File(staging, MODEL_NAME);
        if (!new File(extracted, "am/final.mdl").isFile()
                || !new File(extracted, "conf/model.conf").isFile()) {
            throw new IOException("下载的离线英文模型结构不完整");
        }
        deleteInside(base, destination);
        if (!extracted.renameTo(destination)) {
            throw new IOException("无法把离线英文模型移动到正式目录");
        }
        try (FileOutputStream marker = new FileOutputStream(new File(destination, ".ready"))) {
            marker.write((MODEL_NAME + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
            marker.getFD().sync();
        }
        deleteInside(base, archive);
        deleteInside(base, staging);
        if (!isInstalled(context)) throw new IOException("离线英文模型安装校验失败");
        progress.update("离线英文模型已就绪", 100);
    }

    private static void download(File target, Progress progress) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(DOWNLOAD_URL).openConnection();
        connection.setConnectTimeout(20_000);
        connection.setReadTimeout(30_000);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("User-Agent", "ConferenceRecorder/0.9");
        try {
            int response = connection.getResponseCode();
            if (response < 200 || response >= 300) {
                throw new IOException("离线英文模型下载失败（HTTP " + response + "）");
            }
            long expected = connection.getContentLengthLong();
            if (expected > MAX_ARCHIVE_BYTES) {
                throw new IOException("离线英文模型下载文件超过 100 MB 安全上限");
            }
            long total = 0L;
            int lastPercent = -1;
            try (InputStream input = new BufferedInputStream(connection.getInputStream());
                 FileOutputStream fileOutput = new FileOutputStream(target);
                 BufferedOutputStream output = new BufferedOutputStream(fileOutput)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) >= 0) {
                    output.write(buffer, 0, read);
                    total += read;
                    if (total > MAX_ARCHIVE_BYTES) {
                        throw new IOException("离线英文模型下载超过 100 MB 安全上限");
                    }
                    int percent = expected > 0L
                            ? (int) Math.min(95L, total * 95L / expected) : 0;
                    if (percent != lastPercent) {
                        progress.update("正在下载离线英文模型", percent);
                        lastPercent = percent;
                    }
                }
                output.flush();
                fileOutput.getFD().sync();
            }
            if (total < 10L * 1024L * 1024L) {
                throw new IOException("下载的离线英文模型文件异常偏小");
            }
        } finally {
            connection.disconnect();
        }
    }

    private static void unzip(File archive, File targetRoot) throws IOException {
        String targetPath = targetRoot.getCanonicalPath() + File.separator;
        long extractedBytes = 0L;
        try (ZipInputStream input = new ZipInputStream(
                new BufferedInputStream(new FileInputStream(archive)))) {
            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];
            while ((entry = input.getNextEntry()) != null) {
                File target = new File(targetRoot, entry.getName());
                String canonical = target.getCanonicalPath();
                if (!canonical.startsWith(targetPath)) {
                    throw new IOException("离线模型压缩包包含不安全路径");
                }
                if (entry.isDirectory()) {
                    requireDirectory(target);
                } else {
                    File parent = target.getParentFile();
                    if (parent == null) throw new IOException("离线模型文件没有父目录");
                    requireDirectory(parent);
                    try (BufferedOutputStream output = new BufferedOutputStream(
                            new FileOutputStream(target))) {
                        int read;
                        while ((read = input.read(buffer)) >= 0) {
                            extractedBytes += read;
                            if (extractedBytes > MAX_EXTRACTED_BYTES) {
                                throw new IOException("离线英文模型解压超过 200 MB 安全上限");
                            }
                            output.write(buffer, 0, read);
                        }
                    }
                }
                input.closeEntry();
            }
        }
    }

    private static File baseDirectory(Context context) {
        return new File(context.getNoBackupFilesDir(), "vosk-models");
    }

    private static void requireDirectory(File directory) throws IOException {
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("无法创建离线英文模型目录");
        }
    }

    private static void deleteInside(File base, File target) throws IOException {
        if (!target.exists()) return;
        String basePath = base.getCanonicalPath() + File.separator;
        if (!target.getCanonicalPath().startsWith(basePath)) {
            throw new IOException("拒绝清理模型目录之外的文件");
        }
        if (target.isDirectory()) {
            File[] children = target.listFiles();
            if (children != null) {
                for (File child : children) deleteInside(base, child);
            }
        }
        if (!target.delete()) throw new IOException("无法清理旧的离线英文模型文件");
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName() : message;
    }
}
