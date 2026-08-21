package com.higs.conferencerecorder;

import android.graphics.Color;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.higs.conferencerecorder.data.ConferenceRepository;
import com.higs.conferencerecorder.data.ConferenceStore;
import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ProgramItem;

import java.util.List;

public final class PosterSearchActivity extends BaseActivity {
    public static final String EXTRA_CONFERENCE_ID = "conference_id";

    private ConferenceRepository repository;
    private Conference conference;
    private TextView resultCount;
    private LinearLayout results;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String conferenceId = getIntent().getStringExtra(EXTRA_CONFERENCE_ID);
        repository = ConferenceStore.get(this);
        conference = repository.conference(conferenceId == null ? "" : conferenceId);
        if (conference == null) {
            finish();
            return;
        }

        LinearLayout content = createScreen("海报检索", conference.title, true);
        LinearLayout searchCard = UiKit.card(this);
        searchCard.addView(UiKit.eyebrow(this, "POSTER SESSION"));
        searchCard.addView(UiKit.text(
                this,
                "搜索海报编号、题目、作者或单位",
                19,
                UiKit.TEXT_PRIMARY,
                true));

        EditText search = new EditText(this);
        search.setSingleLine(true);
        search.setHint("输入 0630、光力学、姓名……");
        search.setTextSize(15);
        search.setTextColor(UiKit.TEXT_PRIMARY);
        search.setHintTextColor(Color.rgb(144, 153, 157));
        search.setPadding(
                UiKit.dp(this, 14), UiKit.dp(this, 12),
                UiKit.dp(this, 14), UiKit.dp(this, 12));
        android.graphics.drawable.GradientDrawable searchBackground = UiKit.roundRect(
                Color.rgb(248, 249, 247), 13, this);
        searchBackground.setStroke(UiKit.dp(this, 1), UiKit.LINE);
        search.setBackground(searchBackground);
        LinearLayout.LayoutParams searchParams = UiKit.matchWrap();
        searchParams.topMargin = UiKit.dp(this, 14);
        searchCard.addView(search, searchParams);

        resultCount = UiKit.text(this, "", 12, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams countParams = UiKit.matchWrap();
        countParams.topMargin = UiKit.dp(this, 10);
        searchCard.addView(resultCount, countParams);
        content.addView(searchCard);

        results = new LinearLayout(this);
        results.setOrientation(LinearLayout.VERTICAL);
        results.setLayoutParams(UiKit.matchWrap());
        content.addView(results);

        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                render(text.toString());
            }

            @Override
            public void afterTextChanged(Editable text) {
            }
        });
        render("");
    }

    private void render(String query) {
        List<ProgramItem> matches = repository.searchPosters(conference.id, query);
        resultCount.setText(getString(
                R.string.poster_result_count,
                conference.posterCount,
                conference.posters.size(),
                matches.size()));
        results.removeAllViews();
        results.addView(UiKit.sectionTitle(this, query.trim().isEmpty() ? "已载入海报" : "检索结果"));
        if (matches.isEmpty()) {
            LinearLayout empty = UiKit.card(this);
            TextView message = UiKit.text(
                    this,
                    "没有匹配项。初版只载入少量结构测试记录，完整手册导入器会在下一阶段补齐。",
                    14,
                    UiKit.TEXT_SECONDARY,
                    false);
            message.setGravity(Gravity.CENTER);
            empty.addView(message);
            results.addView(empty);
            return;
        }

        int limit = Math.min(matches.size(), 30);
        for (int index = 0; index < limit; index++) results.addView(posterCard(matches.get(index)));
        if (matches.size() > limit) {
            TextView limited = UiKit.text(this, "仅显示前 " + limit + " 项，请继续缩小关键词。",
                    12, UiKit.WARNING, false);
            LinearLayout.LayoutParams params = UiKit.matchWrap();
            params.topMargin = UiKit.dp(this, 12);
            limited.setLayoutParams(params);
            results.addView(limited);
        }
    }

    private LinearLayout posterCard(ProgramItem poster) {
        LinearLayout card = UiKit.card(this);
        UiKit.makeClickable(this, card);
        card.setOnClickListener(view -> open(PackageActivity.class, intent -> intent
                .putExtra(PackageActivity.EXTRA_CONFERENCE_ID, conference.id)
                .putExtra(PackageActivity.EXTRA_ITEM_ID, poster.id)));
        String code = poster.code.isEmpty() ? "编号待定" : poster.code;
        card.addView(UiKit.text(this, code, 12, UiKit.CORAL, true));
        TextView title = UiKit.text(this, poster.title, 17, UiKit.TEXT_PRIMARY, true);
        LinearLayout.LayoutParams titleParams = UiKit.matchWrap();
        titleParams.topMargin = UiKit.dp(this, 7);
        card.addView(title, titleParams);
        if (!poster.personLine().isEmpty()) {
            TextView person = UiKit.text(this, poster.personLine(), 13,
                    UiKit.TEXT_SECONDARY, false);
            LinearLayout.LayoutParams personParams = UiKit.matchWrap();
            personParams.topMargin = UiKit.dp(this, 8);
            card.addView(person, personParams);
        }
        return card;
    }
}
