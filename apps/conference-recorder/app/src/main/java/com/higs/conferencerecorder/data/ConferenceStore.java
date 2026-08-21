package com.higs.conferencerecorder.data;

import android.content.Context;

public final class ConferenceStore {
    private static volatile ConferenceRepository repository;

    private ConferenceStore() {
    }

    public static ConferenceRepository get(Context context) {
        ConferenceRepository current = repository;
        if (current != null) return current;
        synchronized (ConferenceStore.class) {
            if (repository == null) {
                repository = new AssetConferenceRepository(context.getApplicationContext());
            }
            return repository;
        }
    }

    public static synchronized ConferenceRepository reload(Context context) {
        repository = new AssetConferenceRepository(context.getApplicationContext());
        return repository;
    }
}
