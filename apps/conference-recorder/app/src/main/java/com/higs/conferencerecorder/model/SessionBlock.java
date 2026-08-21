package com.higs.conferencerecorder.model;

import java.util.Collections;
import java.util.List;

public final class SessionBlock {
    public final String id;
    public final String title;
    public final String start;
    public final String end;
    public final String venue;
    public final String chair;
    public final String note;
    public final List<ProgramItem> items;

    public SessionBlock(
            String id,
            String title,
            String start,
            String end,
            String venue,
            String chair,
            String note,
            List<ProgramItem> items) {
        this.id = id;
        this.title = title;
        this.start = start;
        this.end = end;
        this.venue = venue;
        this.chair = chair;
        this.note = note;
        this.items = Collections.unmodifiableList(items);
    }

    public String timeRange() {
        if (start.isEmpty()) return "时间待定";
        if (end.isEmpty()) return start;
        return start + "–" + end;
    }
}
