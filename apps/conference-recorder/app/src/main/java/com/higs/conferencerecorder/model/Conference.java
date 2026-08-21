package com.higs.conferencerecorder.model;

import java.util.Collections;
import java.util.List;

public final class Conference {
    public final String id;
    public final String title;
    public final String subtitle;
    public final String dateRange;
    public final String location;
    public final String sourceNote;
    public final int talkCount;
    public final int posterCount;
    public final List<ConferenceDay> days;
    public final List<ProgramItem> posters;

    public Conference(
            String id,
            String title,
            String subtitle,
            String dateRange,
            String location,
            String sourceNote,
            int talkCount,
            int posterCount,
            List<ConferenceDay> days,
            List<ProgramItem> posters) {
        this.id = id;
        this.title = title;
        this.subtitle = subtitle;
        this.dateRange = dateRange;
        this.location = location;
        this.sourceNote = sourceNote;
        this.talkCount = talkCount;
        this.posterCount = posterCount;
        this.days = Collections.unmodifiableList(days);
        this.posters = Collections.unmodifiableList(posters);
    }
}
