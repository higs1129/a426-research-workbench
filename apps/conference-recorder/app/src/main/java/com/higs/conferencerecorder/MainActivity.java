package com.higs.conferencerecorder;

import android.graphics.Color;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.higs.conferencerecorder.data.ActiveConferenceStore;
import com.higs.conferencerecorder.data.CaptureSessionStore;
import com.higs.conferencerecorder.data.ConferenceRepository;
import com.higs.conferencerecorder.data.ConferenceStore;
import com.higs.conferencerecorder.data.ScheduleAdvisor;
import com.higs.conferencerecorder.model.Conference;

import java.io.IOException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;

public final class MainActivity extends BaseActivity {
    private Conference conference;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ConferenceRepository repository = ConferenceStore.get(this);
        conference = ActiveConferenceStore.active(this, repository);
        if (conference == null) {
            LinearLayout empty = createScreen(
                    "会议记录", "尚无会议", false, "管理",
                    view -> open(MeetingManagementActivity.class, null));
            empty.addView(UiKit.text(this,
                    "请先在会议管理中导入会议 JSON。",
                    16, UiKit.TEXT_SECONDARY, false));
            return;
        }

        LinearLayout content = createScreen(
                "会议记录",
                conference.title,
                false,
                "管理",
                view -> open(MeetingManagementActivity.class, null));

        content.addView(currentConferenceCard());

        ScheduleAdvisor.Recommendation primary = ScheduleAdvisor.recommend(
                conference, LocalDateTime.now());
        String primarySection = primary.state == ScheduleAdvisor.State.LIVE
                ? "正在进行" : "下一项";
        content.addView(UiKit.sectionTitle(this, primarySection));
        content.addView(primaryCard(primary));

        if (primary.state != ScheduleAdvisor.State.FINISHED) {
            List<ScheduleAdvisor.Recommendation> upcoming =
                    ScheduleAdvisor.upcomingAfter(conference, primary, 3);
            if (!upcoming.isEmpty()) {
                content.addView(UiKit.sectionTitle(this, "接下来"));
                LinearLayout list = UiKit.card(this);
                for (int index = 0; index < upcoming.size(); index++) {
                    list.addView(upcomingRow(upcoming.get(index)));
                    if (index < upcoming.size() - 1) list.addView(UiKit.divider(this));
                }
                content.addView(list);
            }
        }

        content.addView(UiKit.sectionTitle(this, "浏览会议"));
        content.addView(browseCard());
    }

    @Override
    protected void onRestart() {
        super.onRestart();
        recreate();
    }

    private LinearLayout currentConferenceCard() {
        LinearLayout card = UiKit.card(this);
        card.setBackground(UiKit.roundRect(UiKit.INK, 20, this));
        card.addView(UiKit.eyebrow(this, "CURRENT CONFERENCE"));
        TextView title = UiKit.text(this, conference.title, 23, Color.WHITE, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 7);
        card.addView(title, titleParams);
        TextView meta = UiKit.text(this,
                conference.dateRange + " · " + conference.location,
                13, Color.rgb(198, 216, 220), false);
        LinearLayout.LayoutParams metaParams = UiKit.matchWrap();
        metaParams.topMargin = UiKit.dp(this, 7);
        card.addView(meta, metaParams);
        return card;
    }

    private LinearLayout primaryCard(ScheduleAdvisor.Recommendation recommendation) {
        LinearLayout card = UiKit.card(this);
        card.setBackground(UiKit.roundRect(UiKit.ACCENT, 20, this));
        if (recommendation.item == null || recommendation.session == null) {
            card.addView(UiKit.text(this, "暂无可用日程", 18, Color.WHITE, true));
            return card;
        }
        if (recommendation.state == ScheduleAdvisor.State.FINISHED) {
            card.addView(UiKit.text(this, "本次会议日程已结束", 19, Color.WHITE, true));
            card.addView(UiKit.text(this,
                    "仍可从完整日程中进入任意报告并补充记录。",
                    13, Color.rgb(214, 239, 235), false));
            return card;
        }

        String time = recommendation.startsAt == null
                ? recommendation.item.timeRange()
                : recommendation.startsAt.format(DateTimeFormatter.ofPattern("M月d日 HH:mm"));
        card.addView(UiKit.text(this,
                time + " · " + recommendation.session.title,
                13, Color.rgb(214, 239, 235), true));
        TextView title = UiKit.text(this,
                recommendation.item.title, 21, Color.WHITE, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 8);
        card.addView(title, titleParams);
        if (!recommendation.item.personLine().isEmpty()) {
            TextView person = UiKit.text(this,
                    recommendation.item.personLine(), 13,
                    Color.rgb(214, 239, 235), false);
            LinearLayout.LayoutParams personParams = UiKit.matchWrap();
            personParams.topMargin = UiKit.dp(this, 7);
            card.addView(person, personParams);
        }
        TextView open = UiKit.button(this, primaryActionLabel(recommendation), false);
        open.setTextColor(Color.WHITE);
        open.setOnClickListener(view -> openPackage(recommendation));
        card.addView(open);
        return card;
    }

    private String primaryActionLabel(ScheduleAdvisor.Recommendation recommendation) {
        if (AudioRecordingService.state() != AudioRecordingService.State.IDLE
                && CaptureSessionStore.captureKey(conference.id, recommendation.item.id)
                .equals(AudioRecordingService.captureKey())) {
            return "返回正在录音的报告";
        }
        try {
            CaptureSessionStore.CaptureBundle capture = CaptureSessionStore.current(
                    this, conference.id, recommendation.item.id);
            if (capture != null
                    && (capture.audioFiles().length > 0 || capture.imageFiles().length > 0)) {
                return "继续记录";
            }
        } catch (IOException ignored) {
            // The detail page will show a concrete storage error if capture is attempted.
        }
        return recommendation.item.isPoster() ? "开始拍摄" : "开始记录";
    }

    private LinearLayout upcomingRow(ScheduleAdvisor.Recommendation recommendation) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.VERTICAL);
        row.setPadding(0, UiKit.dp(this, 3), 0, UiKit.dp(this, 3));
        row.setOnClickListener(view -> openPackage(recommendation));
        row.setClickable(true);
        row.setFocusable(true);
        String time = recommendation.startsAt == null
                ? recommendation.item.timeRange()
                : recommendation.startsAt.format(DateTimeFormatter.ofPattern("M月d日 HH:mm"));
        row.addView(UiKit.text(this,
                time + " · " + recommendation.session.title,
                12, UiKit.ACCENT, true));
        TextView title = UiKit.text(this,
                recommendation.item.title, 15, UiKit.TEXT_PRIMARY, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 3);
        row.addView(title, titleParams);
        return row;
    }

    private LinearLayout browseCard() {
        LinearLayout card = UiKit.card(this);
        TextView schedule = UiKit.button(this, "查看全部日程", true);
        schedule.setOnClickListener(view -> open(
                ConferenceActivity.class,
                intent -> intent.putExtra(ConferenceActivity.EXTRA_CONFERENCE_ID, conference.id)));
        card.addView(schedule);
        if (conference.posterCount > 0) {
            TextView posters = UiKit.button(this,
                    "查找海报（" + conference.posterCount + "）", false);
            posters.setOnClickListener(view -> open(
                    PosterSearchActivity.class,
                    intent -> intent.putExtra(
                            PosterSearchActivity.EXTRA_CONFERENCE_ID, conference.id)));
            card.addView(posters);
        }
        return card;
    }

    private void openPackage(ScheduleAdvisor.Recommendation recommendation) {
        open(PackageActivity.class, intent -> intent
                .putExtra(PackageActivity.EXTRA_CONFERENCE_ID, conference.id)
                .putExtra(PackageActivity.EXTRA_SESSION_ID, recommendation.session.id)
                .putExtra(PackageActivity.EXTRA_ITEM_ID, recommendation.item.id));
    }
}
