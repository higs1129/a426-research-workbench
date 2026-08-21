package com.higs.conferencerecorder.data;

import android.content.Context;
import android.content.SharedPreferences;

public final class ReportPackageStore {
    private static final String FILE_NAME = "report_package_drafts";

    private ReportPackageStore() {
    }

    public static String loadNote(Context context, String conferenceId, String itemId) {
        SharedPreferences preferences = preferences(context);
        String currentKey = key(conferenceId, itemId);
        if (preferences.contains(currentKey)) {
            String note = preferences.getString(currentKey, "");
            return note == null ? "" : note;
        }

        String legacy = preferences.getString("note:" + itemId, "");
        if (legacy != null && !legacy.isEmpty()) {
            preferences.edit().putString(currentKey, legacy).apply();
            return legacy;
        }
        return "";
    }

    public static void saveNote(
            Context context, String conferenceId, String itemId, String note) {
        preferences(context).edit().putString(key(conferenceId, itemId), note).apply();
    }

    private static String key(String conferenceId, String itemId) {
        return "note:" + conferenceId + ":" + itemId;
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE);
    }
}
