package com.higs.conferencerecorder;

import android.os.Bundle;
import android.view.View;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.higs.conferencerecorder.data.ConferenceRepository;
import com.higs.conferencerecorder.data.ConferenceStore;
import com.higs.conferencerecorder.data.ScheduleAdvisor;
import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ConferenceDay;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public final class ConferenceActivity extends BaseActivity {
    public static final String EXTRA_CONFERENCE_ID = "conference_id";

    private Conference conference;
    private LinearLayout chipRow;
    private LinearLayout sessionContainer;
    private int selectedDay;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String conferenceId = getIntent().getStringExtra(EXTRA_CONFERENCE_ID);
        ConferenceRepository repository = ConferenceStore.get(this);
        conference = repository.conference(conferenceId == null ? "" : conferenceId);
        if (conference == null) {
            finish();
            return;
        }

        LinearLayout content = createScreen(
                conference.title,
                conference.dateRange + " · " + conference.location,
                true);

        content.addView(recommendationCard());

        LinearLayout source = UiKit.card(this);
        source.addView(UiKit.eyebrow(this, "SCHEDULE SOURCE"));
        source.addView(UiKit.text(this, conference.sourceNote, 14,
                UiKit.TEXT_PRIMARY, false));
        content.addView(source);

        content.addView(UiKit.sectionTitle(this, "按日期选择"));
        HorizontalScrollView chipScroll = new HorizontalScrollView(this);
        chipScroll.setHorizontalScrollBarEnabled(false);
        chipScroll.setClipToPadding(false);
        chipRow = UiKit.horizontal(this);
        chipScroll.addView(chipRow);
        content.addView(chipScroll);

        sessionContainer = new LinearLayout(this);
        sessionContainer.setOrientation(LinearLayout.VERTICAL);
        sessionContainer.setLayoutParams(UiKit.matchWrap());
        content.addView(sessionContainer);

        renderDay(0);
    }

    private LinearLayout recommendationCard() {
        ScheduleAdvisor.Recommendation recommendation = ScheduleAdvisor.recommend(
                conference, LocalDateTime.now());
        LinearLayout card = UiKit.card(this);
        card.setBackground(UiKit.roundRect(UiKit.ACCENT, 20, this));
        if (recommendation.state == ScheduleAdvisor.State.EMPTY || recommendation.item == null) {
            card.addView(UiKit.text(this, "暂无可推荐日程", 18,
                    android.graphics.Color.WHITE, true));
            return card;
        }

        String stateLabel;
        if (recommendation.state == ScheduleAdvisor.State.LIVE) {
            stateLabel = "正在进行 · 推荐选中";
        } else if (recommendation.state == ScheduleAdvisor.State.NEXT) {
            stateLabel = "下一项 · 自动推荐";
        } else {
            stateLabel = "会议日程已结束";
        }
        TextView state = UiKit.text(this, stateLabel, 12,
                android.graphics.Color.rgb(211, 239, 234), true);
        state.setLetterSpacing(0.06f);
        card.addView(state);
        TextView title = UiKit.text(this, recommendation.item.title, 20,
                android.graphics.Color.WHITE, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 8);
        card.addView(title, titleParams);
        String start = recommendation.startsAt == null
                ? recommendation.item.timeRange()
                : recommendation.startsAt.format(DateTimeFormatter.ofPattern("M月d日 HH:mm"));
        card.addView(UiKit.text(
                this,
                start + " · " + recommendation.session.title,
                14,
                android.graphics.Color.rgb(211, 239, 234),
                false));

        if (recommendation.state != ScheduleAdvisor.State.FINISHED) {
            TextView open = UiKit.button(this, "进入这个报告包", false);
            open.setTextColor(android.graphics.Color.WHITE);
            open.setOnClickListener(view -> openPackage(
                    recommendation.session.id, recommendation.item.id));
            card.addView(open);
        }
        return card;
    }

    private void renderDay(int index) {
        if (conference.days.isEmpty()) return;
        selectedDay = Math.max(0, Math.min(index, conference.days.size() - 1));
        chipRow.removeAllViews();
        for (int dayIndex = 0; dayIndex < conference.days.size(); dayIndex++) {
            ConferenceDay day = conference.days.get(dayIndex);
            TextView chip = UiKit.chip(this, day.label, day.weekday, dayIndex == selectedDay);
            int target = dayIndex;
            chip.setOnClickListener(view -> renderDay(target));
            chipRow.addView(chip);
        }

        sessionContainer.removeAllViews();
        ConferenceDay day = conference.days.get(selectedDay);
        sessionContainer.addView(UiKit.sectionTitle(this, day.label + " 日程"));
        for (SessionBlock session : day.sessions) {
            sessionContainer.addView(sessionCard(session));
        }
        if ("2026-08-11".equals(day.id) && conference.posterCount > 0) {
            sessionContainer.addView(posterCard());
        }
    }

    private LinearLayout sessionCard(SessionBlock session) {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card);
        card.setOnClickListener(view -> open(
                SessionActivity.class,
                intent -> intent
                        .putExtra(SessionActivity.EXTRA_CONFERENCE_ID, conference.id)
                        .putExtra(SessionActivity.EXTRA_SESSION_ID, session.id)));

        LinearLayout top = UiKit.horizontal(this);
        top.addView(UiKit.text(this, session.timeRange(), 13,
                UiKit.ACCENT, true), UiKit.weight(1f));
        top.addView(UiKit.pill(this, session.items.size() + " 项",
                UiKit.ACCENT, UiKit.ACCENT_SOFT));
        card.addView(top);

        TextView title = UiKit.text(this, session.title, 20, UiKit.TEXT_PRIMARY, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 3);
        card.addView(title, titleParams);

        String details = session.venue;
        if (!session.chair.isEmpty()) details += " · 主持：" + session.chair;
        TextView meta = UiKit.text(this, details, 13, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams metaParams = UiKit.matchWrap();
        metaParams.topMargin = UiKit.dp(this, 8);
        card.addView(meta, metaParams);
        if (!session.note.isEmpty()) {
            TextView note = UiKit.text(this, session.note, 12, UiKit.WARNING, false);
            LinearLayout.LayoutParams noteParams = UiKit.matchWrap();
            noteParams.topMargin = UiKit.dp(this, 8);
            card.addView(note, noteParams);
        }
        return card;
    }

    private LinearLayout posterCard() {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card, UiKit.CORAL_SOFT);
        card.setOnClickListener(view -> open(
                PosterSearchActivity.class,
                intent -> intent.putExtra(PosterSearchActivity.EXTRA_CONFERENCE_ID, conference.id)));
        card.addView(UiKit.eyebrow(this, "POSTER SESSION · 16:10–17:30"));
        TextView title = UiKit.text(this, "海报检索与海报包", 20,
                UiKit.TEXT_PRIMARY, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 7);
        card.addView(title, titleParams);
        card.addView(UiKit.text(
                this,
                "按编号、题目或作者搜索；手册共 " + conference.posterCount + " 项",
                14,
                UiKit.TEXT_SECONDARY,
                false));
        return card;
    }

    private void openPackage(String sessionId, String itemId) {
        open(PackageActivity.class, intent -> intent
                .putExtra(PackageActivity.EXTRA_CONFERENCE_ID, conference.id)
                .putExtra(PackageActivity.EXTRA_SESSION_ID, sessionId)
                .putExtra(PackageActivity.EXTRA_ITEM_ID, itemId));
    }
}
