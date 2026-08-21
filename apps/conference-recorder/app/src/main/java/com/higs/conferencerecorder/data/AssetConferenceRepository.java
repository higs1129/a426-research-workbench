package com.higs.conferencerecorder.data;

import android.content.Context;

import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ConferenceDay;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

import org.json.JSONException;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.ArrayList;

public final class AssetConferenceRepository implements ConferenceRepository {
    private static final String LOCAL_ASSET = "conference.local.json";
    private static final String EXAMPLE_ASSET = "conference.example.json";

    private final List<Conference> conferences;
    private final String loadedAssetName;

    public AssetConferenceRepository(Context context) {
        String json;
        String asset;
        try {
            json = readAsset(context, LOCAL_ASSET);
            asset = LOCAL_ASSET;
        } catch (IOException localMissing) {
            try {
                json = readAsset(context, EXAMPLE_ASSET);
                asset = EXAMPLE_ASSET;
            } catch (IOException fallbackMissing) {
                throw new IllegalStateException("会议配置文件缺失", fallbackMissing);
            }
        }

        try {
            ConferenceJsonParser.ParsedCatalog bundled = ConferenceJsonParser.parse(json);
            LinkedHashMap<String, Conference> merged = new LinkedHashMap<>();
            for (Conference conference : bundled.conferences) merged.put(conference.id, conference);

            int importedCount = 0;
            String importState = "";
            try {
                String importedJson = ConferenceImportStore.readStoredCatalog(context);
                if (importedJson != null) {
                    ConferenceJsonParser.ParsedCatalog imported = ConferenceJsonParser.parse(importedJson);
                    importedCount = imported.conferences.size();
                    for (Conference conference : imported.conferences) {
                        merged.put(conference.id, conference);
                    }
                }
            } catch (IOException | JSONException invalidImport) {
                importState = " + 导入数据异常，已回退";
            }

            this.conferences = Collections.unmodifiableList(new ArrayList<>(merged.values()));
            this.loadedAssetName = asset + (importedCount > 0
                    ? " + 手机导入 " + importedCount + " 个会议"
                    : importState);
        } catch (JSONException invalidJson) {
            throw new IllegalStateException("会议配置格式无效: " + asset, invalidJson);
        }
    }

    @Override
    public List<Conference> conferences() {
        return conferences;
    }

    @Override
    public Conference conference(String conferenceId) {
        for (Conference conference : conferences) {
            if (conference.id.equals(conferenceId)) return conference;
        }
        return null;
    }

    @Override
    public SessionBlock session(String conferenceId, String sessionId) {
        Conference conference = conference(conferenceId);
        if (conference == null) return null;
        for (ConferenceDay day : conference.days) {
            for (SessionBlock session : day.sessions) {
                if (session.id.equals(sessionId)) return session;
            }
        }
        return null;
    }

    @Override
    public ProgramItem item(String conferenceId, String itemId) {
        Conference conference = conference(conferenceId);
        if (conference == null) return null;
        for (ConferenceDay day : conference.days) {
            for (SessionBlock session : day.sessions) {
                for (ProgramItem item : session.items) {
                    if (item.id.equals(itemId)) return item;
                }
            }
        }
        for (ProgramItem poster : conference.posters) {
            if (poster.id.equals(itemId)) return poster;
        }
        return null;
    }

    @Override
    public List<ProgramItem> searchPosters(String conferenceId, String query) {
        Conference conference = conference(conferenceId);
        if (conference == null) return Collections.emptyList();
        String needle = query == null ? "" : query.trim().toLowerCase(Locale.ROOT);
        if (needle.isEmpty()) return conference.posters;

        List<ProgramItem> matches = new ArrayList<>();
        for (ProgramItem poster : conference.posters) {
            String haystack = (poster.code + " " + poster.title + " " + poster.speaker + " "
                    + poster.affiliation).toLowerCase(Locale.ROOT);
            if (haystack.contains(needle)) matches.add(poster);
        }
        return matches;
    }

    @Override
    public String loadedAssetName() {
        return loadedAssetName;
    }

    private static String readAsset(Context context, String name) throws IOException {
        StringBuilder text = new StringBuilder();
        try (InputStream input = context.getAssets().open(name);
             BufferedReader reader = new BufferedReader(
                     new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) text.append(line).append('\n');
        }
        return text.toString();
    }

}
