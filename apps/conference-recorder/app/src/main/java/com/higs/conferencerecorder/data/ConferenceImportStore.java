package com.higs.conferencerecorder.data;

import android.content.Context;
import android.net.Uri;

import com.higs.conferencerecorder.model.Conference;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class ConferenceImportStore {
    private static final int MAX_JSON_BYTES = 10 * 1024 * 1024;
    private static final String DIRECTORY = "conference-catalog";
    private static final String FILE_NAME = "imported-conferences.json";

    private ConferenceImportStore() {
    }

    public static ImportResult importFromUri(
            Context context, Uri uri, Set<String> existingConferenceIds)
            throws IOException, JSONException {
        String incomingJson;
        try (InputStream input = context.getContentResolver().openInputStream(uri)) {
            if (input == null) throw new IOException("无法打开所选文件");
            incomingJson = readUtf8(input);
        }
        ConferenceJsonParser.ParsedCatalog incoming = ConferenceJsonParser.parse(incomingJson);

        LinkedHashMap<String, JSONObject> merged = new LinkedHashMap<>();
        String storedJson = readStoredCatalog(context);
        if (storedJson != null) {
            ConferenceJsonParser.ParsedCatalog stored = ConferenceJsonParser.parse(storedJson);
            for (int index = 0; index < stored.conferences.size(); index++) {
                merged.put(stored.conferences.get(index).id, stored.rawConferences.get(index));
            }
        }

        int added = 0;
        int updated = 0;
        List<String> titles = new ArrayList<>();
        for (int index = 0; index < incoming.conferences.size(); index++) {
            Conference conference = incoming.conferences.get(index);
            if (existingConferenceIds.contains(conference.id)) updated++;
            else added++;
            merged.put(conference.id, incoming.rawConferences.get(index));
            titles.add(conference.title);
        }

        JSONObject root = new JSONObject();
        root.put("schemaVersion", ConferenceJsonParser.MAX_SCHEMA_VERSION);
        root.put("lastImportedAt", System.currentTimeMillis());
        JSONArray conferences = new JSONArray();
        for (Map.Entry<String, JSONObject> entry : merged.entrySet()) {
            conferences.put(entry.getValue());
        }
        root.put("conferences", conferences);
        writeAtomically(context, root.toString(2) + "\n");
        return new ImportResult(added, updated, titles);
    }

    static String readStoredCatalog(Context context) throws IOException {
        File file = catalogFile(context);
        if (!file.isFile()) return null;
        byte[] bytes = Files.readAllBytes(file.toPath());
        if (bytes.length > MAX_JSON_BYTES) throw new IOException("已保存的会议 JSON 超过 10 MB");
        return new String(bytes, StandardCharsets.UTF_8);
    }

    private static String readUtf8(InputStream input) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int total = 0;
        int read;
        while ((read = input.read(buffer)) != -1) {
            total += read;
            if (total > MAX_JSON_BYTES) throw new IOException("会议 JSON 不能超过 10 MB");
            output.write(buffer, 0, read);
        }
        return output.toString(StandardCharsets.UTF_8.name());
    }

    private static void writeAtomically(Context context, String json) throws IOException {
        File target = catalogFile(context);
        File directory = target.getParentFile();
        if (directory == null || (!directory.isDirectory() && !directory.mkdirs())) {
            throw new IOException("无法创建会议数据目录");
        }
        File temporary = new File(directory, FILE_NAME + ".tmp");
        Files.write(temporary.toPath(), json.getBytes(StandardCharsets.UTF_8));
        try {
            Files.move(
                    temporary.toPath(),
                    target.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException unsupported) {
            Files.move(
                    temporary.toPath(),
                    target.toPath(),
                    StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static File catalogFile(Context context) {
        return new File(new File(context.getFilesDir(), DIRECTORY), FILE_NAME);
    }

    public static final class ImportResult {
        public final int added;
        public final int updated;
        public final List<String> titles;

        ImportResult(int added, int updated, List<String> titles) {
            this.added = added;
            this.updated = updated;
            this.titles = java.util.Collections.unmodifiableList(titles);
        }

        public String summary() {
            StringBuilder message = new StringBuilder("导入成功：");
            if (added > 0) message.append("新增 ").append(added).append(" 个会议");
            if (added > 0 && updated > 0) message.append("，");
            if (updated > 0) message.append("更新 ").append(updated).append(" 个会议");
            return message.toString();
        }
    }
}
