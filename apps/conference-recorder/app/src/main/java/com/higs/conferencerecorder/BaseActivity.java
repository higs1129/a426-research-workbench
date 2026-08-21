package com.higs.conferencerecorder;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public abstract class BaseActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        window.setStatusBarColor(UiKit.INK);
        window.setNavigationBarColor(UiKit.INK);
    }

    protected LinearLayout createScreen(String title, String subtitle, boolean showBack) {
        return createScreen(title, subtitle, showBack, null, null);
    }

    protected LinearLayout createScreen(
            String title,
            String subtitle,
            boolean showBack,
            String headerAction,
            View.OnClickListener actionListener) {
        LinearLayout shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setBackgroundColor(UiKit.PAPER);
        shell.setFitsSystemWindows(true);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(
                UiKit.dp(this, 16),
                UiKit.dp(this, 15),
                UiKit.dp(this, 20),
                UiKit.dp(this, 15));
        header.setBackgroundColor(UiKit.INK);
        header.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        if (showBack) {
            TextView back = UiKit.text(this, "‹", 38, Color.WHITE, false);
            back.setGravity(Gravity.CENTER);
            back.setContentDescription("返回");
            back.setMinWidth(UiKit.dp(this, 44));
            back.setOnClickListener(view -> finish());
            header.addView(back, new LinearLayout.LayoutParams(
                    UiKit.dp(this, 44), ViewGroup.LayoutParams.MATCH_PARENT));
        }

        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        titles.setPadding(showBack ? UiKit.dp(this, 4) : 0, 0, 0, 0);
        titles.addView(UiKit.text(this, title, 20, Color.WHITE, true));
        if (subtitle != null && !subtitle.isEmpty()) {
            TextView subtitleView = UiKit.text(
                    this, subtitle, 12, Color.rgb(193, 211, 216), false);
            LinearLayout.LayoutParams subtitleParams = UiKit.matchWrap();
            subtitleParams.topMargin = UiKit.dp(this, 2);
            titles.addView(subtitleView, subtitleParams);
        }
        header.addView(titles, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (headerAction != null && !headerAction.isEmpty()) {
            TextView action = UiKit.text(this, headerAction, 14, Color.WHITE, true);
            action.setGravity(Gravity.CENTER);
            action.setMinWidth(UiKit.dp(this, 58));
            action.setMinHeight(UiKit.dp(this, 42));
            action.setPadding(
                    UiKit.dp(this, 10), UiKit.dp(this, 8),
                    UiKit.dp(this, 10), UiKit.dp(this, 8));
            action.setBackground(UiKit.roundRect(Color.rgb(38, 63, 73), 12, this));
            action.setOnClickListener(actionListener);
            header.addView(action);
        }
        shell.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(
                UiKit.dp(this, 18),
                UiKit.dp(this, 10),
                UiKit.dp(this, 18),
                UiKit.dp(this, 34));
        scroll.addView(content, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        shell.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        setContentView(shell);
        return content;
    }

    protected void open(Class<? extends Activity> activity, IntentConfigurer configurer) {
        Intent intent = new Intent(this, activity);
        if (configurer != null) configurer.configure(intent);
        startActivity(intent);
    }

    protected static void addVerticalMargin(View view, int topDp, int bottomDp) {
        ViewGroup.LayoutParams raw = view.getLayoutParams();
        if (!(raw instanceof LinearLayout.LayoutParams)) return;
        LinearLayout.LayoutParams params = (LinearLayout.LayoutParams) raw;
        params.topMargin = UiKit.dp(view.getContext(), topDp);
        params.bottomMargin = UiKit.dp(view.getContext(), bottomDp);
        view.setLayoutParams(params);
    }

    protected interface IntentConfigurer {
        void configure(Intent intent);
    }
}
