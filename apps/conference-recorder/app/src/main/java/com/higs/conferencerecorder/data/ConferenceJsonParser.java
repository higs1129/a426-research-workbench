package com.higs.conferencerecorder.data;

import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ConferenceDay;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

final class ConferenceJsonParser {
    static final int MAX_SCHEMA_VERSION = 2;

    private ConferenceJsonParser() {
    }

    static ParsedCatalog parse(String json) throws JSONException {
        JSONObject root = new JSONObject(json);
        int schemaVersion = root.optInt("schemaVersion", 1);
        if (schemaVersion < 1 || schemaVersion > MAX_SCHEMA_VERSION) {
            throw new JSONException("不支持 schemaVersion " + schemaVersion
                    + "；当前 App 支持 1–" + MAX_SCHEMA_VERSION);
        }

        JSONArray array = root.optJSONArray("conferences");
        if (array == null || array.length() == 0) {
            throw new JSONException("JSON 中没有 conferences，或会议列表为空");
        }

        List<Conference> conferences = new ArrayList<>();
        List<JSONObject> rawConferences = new ArrayList<>();
        Set<String> conferenceIds = new HashSet<>();
        for (int index = 0; index < array.length(); index++) {
            JSONObject object = array.optJSONObject(index);
            if (object == null) {
                throw new JSONException("conferences[" + index + "] 不是 JSON 对象");
            }
            Conference conference = parseConference(object, index);
            if (!conferenceIds.add(conference.id)) {
                throw new JSONException("会议 ID 重复：" + conference.id);
            }
            conferences.add(conference);
            rawConferences.add(new JSONObject(object.toString()));
        }
        return new ParsedCatalog(schemaVersion, conferences, rawConferences);
    }

    private static Conference parseConference(JSONObject object, int conferenceIndex)
            throws JSONException {
        String path = "conferences[" + conferenceIndex + "]";
        String id = requiredString(object, "id", path);
        String title = requiredString(object, "title", path);
        Set<String> dayIds = new HashSet<>();
        Set<String> sessionIds = new HashSet<>();
        Set<String> itemIds = new HashSet<>();
        Set<String> posterCodes = new HashSet<>();
        int[] talkCount = new int[]{0};

        List<ConferenceDay> days = parseDays(
                object.optJSONArray("days"), path, dayIds, sessionIds, itemIds, talkCount);
        List<ProgramItem> posters = parseItems(
                object.optJSONArray("posters"), "poster", path + ".posters",
                itemIds, posterCodes, null);
        if (days.isEmpty() && posters.isEmpty()) {
            throw new JSONException("会议 “" + title + "” 没有 days 或 posters 内容");
        }

        return new Conference(
                id,
                title,
                object.optString("subtitle").trim(),
                object.optString("dateRange").trim(),
                object.optString("location").trim(),
                object.optString("sourceNote").trim(),
                talkCount[0],
                posters.size(),
                days,
                posters);
    }

    private static List<ConferenceDay> parseDays(
            JSONArray array,
            String conferencePath,
            Set<String> dayIds,
            Set<String> sessionIds,
            Set<String> itemIds,
            int[] talkCount) throws JSONException {
        List<ConferenceDay> days = new ArrayList<>();
        if (array == null) return days;
        for (int index = 0; index < array.length(); index++) {
            JSONObject object = array.optJSONObject(index);
            String path = conferencePath + ".days[" + index + "]";
            if (object == null) throw new JSONException(path + " 不是 JSON 对象");
            String id = requiredString(object, "id", path);
            if (!dayIds.add(id)) throw new JSONException("日期 ID 重复：" + id);
            days.add(new ConferenceDay(
                    id,
                    object.optString("label").trim(),
                    object.optString("weekday").trim(),
                    parseSessions(object.optJSONArray("sessions"), path,
                            sessionIds, itemIds, talkCount)));
        }
        return days;
    }

    private static List<SessionBlock> parseSessions(
            JSONArray array,
            String dayPath,
            Set<String> sessionIds,
            Set<String> itemIds,
            int[] talkCount) throws JSONException {
        List<SessionBlock> sessions = new ArrayList<>();
        if (array == null) return sessions;
        for (int index = 0; index < array.length(); index++) {
            JSONObject object = array.optJSONObject(index);
            String path = dayPath + ".sessions[" + index + "]";
            if (object == null) throw new JSONException(path + " 不是 JSON 对象");
            String id = requiredString(object, "id", path);
            if (!sessionIds.add(id)) throw new JSONException("Session ID 重复：" + id);
            sessions.add(new SessionBlock(
                    id,
                    requiredString(object, "title", path),
                    object.optString("start").trim(),
                    object.optString("end").trim(),
                    object.optString("venue").trim(),
                    object.optString("chair").trim(),
                    object.optString("note").trim(),
                    parseItems(object.optJSONArray("items"), "talk", path + ".items",
                            itemIds, null, talkCount)));
        }
        return sessions;
    }

    private static List<ProgramItem> parseItems(
            JSONArray array,
            String fallbackKind,
            String itemsPath,
            Set<String> itemIds,
            Set<String> posterCodes,
            int[] talkCount) throws JSONException {
        List<ProgramItem> items = new ArrayList<>();
        if (array == null) return items;
        for (int index = 0; index < array.length(); index++) {
            JSONObject object = array.optJSONObject(index);
            String path = itemsPath + "[" + index + "]";
            if (object == null) throw new JSONException(path + " 不是 JSON 对象");
            String id = requiredString(object, "id", path);
            if (!itemIds.add(id)) throw new JSONException("报告或海报 ID 重复：" + id);
            String kind = object.optString("kind", fallbackKind).trim();
            if (kind.isEmpty()) kind = fallbackKind;
            String code = object.optString("code").trim();
            if (posterCodes != null && !code.isEmpty() && !posterCodes.add(code)) {
                throw new JSONException("海报编号重复：" + code);
            }
            if (talkCount != null && "talk".equals(kind)) talkCount[0]++;
            items.add(new ProgramItem(
                    id,
                    kind,
                    code,
                    requiredString(object, "title", path),
                    object.optString("speaker").trim(),
                    object.optString("affiliation").trim(),
                    object.optString("start").trim(),
                    object.optString("end").trim(),
                    object.optString("badge").trim()));
        }
        return items;
    }

    private static String requiredString(JSONObject object, String key, String path)
            throws JSONException {
        String value = object.optString(key).trim();
        if (value.isEmpty()) throw new JSONException(path + "." + key + " 不能为空");
        return value;
    }

    static final class ParsedCatalog {
        final int schemaVersion;
        final List<Conference> conferences;
        final List<JSONObject> rawConferences;

        ParsedCatalog(
                int schemaVersion,
                List<Conference> conferences,
                List<JSONObject> rawConferences) {
            this.schemaVersion = schemaVersion;
            this.conferences = Collections.unmodifiableList(conferences);
            this.rawConferences = Collections.unmodifiableList(rawConferences);
        }
    }
}
