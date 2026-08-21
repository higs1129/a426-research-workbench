package com.higs.conferencerecorder.data;

import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ConferenceDay;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class ScheduleAdvisor {
    public enum State { LIVE, NEXT, FINISHED, EMPTY }

    public static final class Recommendation {
        public final State state;
        public final ConferenceDay day;
        public final SessionBlock session;
        public final ProgramItem item;
        public final LocalDateTime startsAt;

        private Recommendation(
                State state,
                ConferenceDay day,
                SessionBlock session,
                ProgramItem item,
                LocalDateTime startsAt) {
            this.state = state;
            this.day = day;
            this.session = session;
            this.item = item;
            this.startsAt = startsAt;
        }

        public static Recommendation empty() {
            return new Recommendation(State.EMPTY, null, null, null, null);
        }
    }

    private ScheduleAdvisor() {
    }

    public static Recommendation recommend(Conference conference, LocalDateTime now) {
        Recommendation last = null;
        for (ConferenceDay day : conference.days) {
            LocalDate date;
            try {
                date = LocalDate.parse(day.id);
            } catch (RuntimeException invalidDate) {
                continue;
            }
            for (SessionBlock session : day.sessions) {
                for (ProgramItem item : session.items) {
                    LocalTime start = parseTime(item.start);
                    LocalTime end = parseTime(item.end);
                    if (start == null) continue;
                    if (end == null) end = start.plusMinutes(15);
                    LocalDateTime startsAt = LocalDateTime.of(date, start);
                    LocalDateTime endsAt = LocalDateTime.of(date, end);
                    Recommendation candidate = new Recommendation(
                            State.NEXT, day, session, item, startsAt);
                    if (!now.isBefore(startsAt) && now.isBefore(endsAt)) {
                        return new Recommendation(State.LIVE, day, session, item, startsAt);
                    }
                    if (now.isBefore(startsAt)) return candidate;
                    last = candidate;
                }
            }
        }
        if (last == null) return Recommendation.empty();
        return new Recommendation(
                State.FINISHED, last.day, last.session, last.item, last.startsAt);
    }

    public static List<Recommendation> upcomingAfter(
            Conference conference, Recommendation anchor, int limit) {
        if (anchor == null || anchor.item == null || limit <= 0) return Collections.emptyList();
        List<Recommendation> upcoming = new ArrayList<>();
        boolean foundAnchor = false;
        for (ConferenceDay day : conference.days) {
            LocalDate date;
            try {
                date = LocalDate.parse(day.id);
            } catch (RuntimeException invalidDate) {
                continue;
            }
            for (SessionBlock session : day.sessions) {
                for (ProgramItem item : session.items) {
                    if (!foundAnchor) {
                        foundAnchor = item.id.equals(anchor.item.id);
                        continue;
                    }
                    LocalTime start = parseTime(item.start);
                    LocalDateTime startsAt = start == null ? null : LocalDateTime.of(date, start);
                    upcoming.add(new Recommendation(State.NEXT, day, session, item, startsAt));
                    if (upcoming.size() >= limit) return upcoming;
                }
            }
        }
        return upcoming;
    }

    private static LocalTime parseTime(String value) {
        if (value == null || value.isEmpty()) return null;
        try {
            return LocalTime.parse(value);
        } catch (RuntimeException invalidTime) {
            return null;
        }
    }
}
