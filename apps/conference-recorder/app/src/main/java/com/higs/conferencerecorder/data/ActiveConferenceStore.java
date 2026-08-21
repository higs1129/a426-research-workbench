package com.higs.conferencerecorder.data;

import android.content.Context;
import android.content.SharedPreferences;

import com.higs.conferencerecorder.model.Conference;

public final class ActiveConferenceStore {
    private static final String FILE_NAME = "active_conference";
    private static final String KEY_ID = "conference_id";

    private ActiveConferenceStore() {
    }

    public static Conference active(Context context, ConferenceRepository repository) {
        String savedId = preferences(context).getString(KEY_ID, "");
        Conference saved = repository.conference(savedId == null ? "" : savedId);
        if (saved != null) return saved;
        if (repository.conferences().isEmpty()) return null;
        Conference first = repository.conferences().get(0);
        setActive(context, first.id);
        return first;
    }

    public static void setActive(Context context, String conferenceId) {
        preferences(context).edit().putString(KEY_ID, conferenceId).apply();
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE);
    }
}
