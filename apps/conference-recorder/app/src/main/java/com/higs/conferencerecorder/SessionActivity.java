package com.higs.conferencerecorder;

import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.higs.conferencerecorder.data.ConferenceRepository;
import com.higs.conferencerecorder.data.ConferenceStore;
import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

public final class SessionActivity extends BaseActivity {
    public static final String EXTRA_CONFERENCE_ID = "conference_id";
    public static final String EXTRA_SESSION_ID = "session_id";

    private Conference conference;
    private SessionBlock session;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String conferenceId = getIntent().getStringExtra(EXTRA_CONFERENCE_ID);
        String sessionId = getIntent().getStringExtra(EXTRA_SESSION_ID);
        ConferenceRepository repository = ConferenceStore.get(this);
        conference = repository.conference(conferenceId == null ? "" : conferenceId);
        session = repository.session(conferenceId == null ? "" : conferenceId,
                sessionId == null ? "" : sessionId);
        if (conference == null || session == null) {
            finish();
            return;
        }

        LinearLayout content = createScreen(session.title, session.timeRange(), true);
        LinearLayout summary = UiKit.card(this);
        summary.addView(UiKit.eyebrow(this, "SESSION CONTEXT"));
        summary.addView(UiKit.text(this, session.venue, 18, UiKit.TEXT_PRIMARY, true));
        String chair = session.chair.isEmpty() ? "主持人：待确认" : "主持人：" + session.chair;
        summary.addView(UiKit.text(this, chair, 13, UiKit.TEXT_SECONDARY, false));
        if (!session.note.isEmpty()) {
            TextView note = UiKit.text(this, session.note, 13, UiKit.WARNING, false);
            LinearLayout.LayoutParams noteParams = UiKit.matchWrap();
            noteParams.topMargin = UiKit.dp(this, 7);
            summary.addView(note, noteParams);
        }
        content.addView(summary);

        content.addView(UiKit.sectionTitle(this, "选择报告人"));
        for (ProgramItem item : session.items) content.addView(itemCard(item));
    }

    private LinearLayout itemCard(ProgramItem item) {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card);
        card.setOnClickListener(view -> open(PackageActivity.class, intent -> intent
                .putExtra(PackageActivity.EXTRA_CONFERENCE_ID, conference.id)
                .putExtra(PackageActivity.EXTRA_SESSION_ID, session.id)
                .putExtra(PackageActivity.EXTRA_ITEM_ID, item.id)));

        LinearLayout top = UiKit.horizontal(this);
        top.addView(UiKit.text(this, item.timeRange(), 13, UiKit.ACCENT, true), UiKit.weight(1f));
        String badge = item.badge.isEmpty() ? "报告" : item.badge;
        top.addView(UiKit.pill(this, badge, UiKit.CORAL, UiKit.CORAL_SOFT));
        card.addView(top);

        TextView title = UiKit.text(this, item.title, 17, UiKit.TEXT_PRIMARY, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 5);
        card.addView(title, titleParams);
        if (!item.personLine().isEmpty()) {
            TextView person = UiKit.text(this, item.personLine(), 13,
                    UiKit.TEXT_SECONDARY, false);
            LinearLayout.LayoutParams personParams = UiKit.matchWrap();
            personParams.topMargin = UiKit.dp(this, 8);
            card.addView(person, personParams);
        }
        return card;
    }
}
