package com.higs.conferencerecorder.model;

import java.util.Collections;
import java.util.List;

public final class ConferenceDay {
    public final String id;
    public final String label;
    public final String weekday;
    public final List<SessionBlock> sessions;

    public ConferenceDay(String id, String label, String weekday, List<SessionBlock> sessions) {
        this.id = id;
        this.label = label;
        this.weekday = weekday;
        this.sessions = Collections.unmodifiableList(sessions);
    }
}
