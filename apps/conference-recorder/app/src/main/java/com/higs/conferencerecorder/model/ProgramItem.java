package com.higs.conferencerecorder.model;

public final class ProgramItem {
    public final String id;
    public final String kind;
    public final String code;
    public final String title;
    public final String speaker;
    public final String affiliation;
    public final String start;
    public final String end;
    public final String badge;

    public ProgramItem(
            String id,
            String kind,
            String code,
            String title,
            String speaker,
            String affiliation,
            String start,
            String end,
            String badge) {
        this.id = id;
        this.kind = kind;
        this.code = code;
        this.title = title;
        this.speaker = speaker;
        this.affiliation = affiliation;
        this.start = start;
        this.end = end;
        this.badge = badge;
    }

    public boolean isPoster() {
        return "poster".equals(kind) || isPosterSession();
    }

    public boolean isPosterSession() {
        return "poster-session".equals(kind);
    }

    public String timeRange() {
        if (start.isEmpty()) return "时间待定";
        if (end.isEmpty()) return start;
        return start + "–" + end;
    }

    public String personLine() {
        if (speaker.isEmpty()) return affiliation;
        if (affiliation.isEmpty()) return speaker;
        return speaker + " · " + affiliation;
    }
}
