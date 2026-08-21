package com.higs.conferencerecorder;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.Space;
import android.widget.TextView;

public final class UiKit {
    public static final int INK = Color.rgb(18, 36, 45);
    public static final int PAPER = Color.rgb(244, 242, 236);
    public static final int SURFACE = Color.WHITE;
    public static final int ACCENT = Color.rgb(11, 117, 107);
    public static final int ACCENT_SOFT = Color.rgb(221, 237, 233);
    public static final int CORAL = Color.rgb(206, 104, 76);
    public static final int CORAL_SOFT = Color.rgb(245, 227, 220);
    public static final int TEXT_PRIMARY = Color.rgb(23, 38, 45);
    public static final int TEXT_SECONDARY = Color.rgb(101, 115, 122);
    public static final int LINE = Color.rgb(220, 225, 223);
    public static final int WARNING = Color.rgb(155, 101, 28);
    public static final int WARNING_SOFT = Color.rgb(255, 240, 214);

    private UiKit() {
    }

    public static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    public static TextView text(
            Context context, String value, float sizeSp, int color, boolean bold) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(sizeSp);
        view.setTextColor(color);
        view.setLineSpacing(0f, 1.16f);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    public static TextView eyebrow(Context context, String value) {
        TextView view = text(context, value, 11, ACCENT, true);
        view.setLetterSpacing(0.08f);
        return view;
    }

    public static TextView sectionTitle(Context context, String value) {
        TextView view = text(context, value, 19, TEXT_PRIMARY, true);
        LinearLayout.LayoutParams params = matchWrap();
        params.topMargin = dp(context, 24);
        params.bottomMargin = dp(context, 4);
        view.setLayoutParams(params);
        return view;
    }

    public static LinearLayout card(Context context) {
        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.VERTICAL);
        int padding = dp(context, 18);
        card.setPadding(padding, padding, padding, padding);
        card.setBackground(roundRect(SURFACE, 18, context));
        card.setElevation(dp(context, 1.5f));
        LinearLayout.LayoutParams params = matchWrap();
        params.topMargin = dp(context, 12);
        card.setLayoutParams(params);
        return card;
    }

    public static void makeClickable(Context context, View view) {
        makeClickable(context, view, SURFACE);
    }

    public static void makeClickable(Context context, View view, int fillColor) {
        GradientDrawable content = roundRect(fillColor, 18, context);
        RippleDrawable ripple = new RippleDrawable(
                ColorStateList.valueOf(Color.argb(35, 11, 117, 107)), content, null);
        view.setBackground(ripple);
        view.setClickable(true);
        view.setFocusable(true);
    }

    public static TextView pill(Context context, String value, int foreground, int background) {
        TextView view = text(context, value, 12, foreground, true);
        view.setGravity(Gravity.CENTER);
        view.setPadding(dp(context, 11), dp(context, 6), dp(context, 11), dp(context, 6));
        view.setBackground(roundRect(background, 999, context));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMarginEnd(dp(context, 8));
        params.bottomMargin = dp(context, 8);
        view.setLayoutParams(params);
        return view;
    }

    public static TextView button(Context context, String value, boolean primary) {
        int fill = primary ? ACCENT : Color.TRANSPARENT;
        int foreground = primary ? Color.WHITE : ACCENT;
        int stroke = primary ? ACCENT : Color.rgb(166, 196, 191);
        TextView view = text(context, value, 15, foreground, true);
        view.setGravity(Gravity.CENTER);
        view.setMinHeight(dp(context, 48));
        view.setPadding(dp(context, 16), dp(context, 12), dp(context, 16), dp(context, 12));
        GradientDrawable content = roundRect(fill, 14, context);
        content.setStroke(dp(context, 1), stroke);
        RippleDrawable ripple = new RippleDrawable(
                ColorStateList.valueOf(primary
                        ? Color.argb(55, 255, 255, 255)
                        : Color.argb(35, 11, 117, 107)),
                content,
                null);
        view.setBackground(ripple);
        view.setClickable(true);
        view.setFocusable(true);
        LinearLayout.LayoutParams params = matchWrap();
        params.topMargin = dp(context, 14);
        view.setLayoutParams(params);
        return view;
    }

    public static TextView chip(Context context, String top, String bottom, boolean active) {
        TextView view = text(
                context,
                top + "\n" + bottom,
                13,
                active ? Color.WHITE : TEXT_SECONDARY,
                true);
        view.setGravity(Gravity.CENTER);
        view.setMinWidth(dp(context, 92));
        view.setPadding(dp(context, 16), dp(context, 10), dp(context, 16), dp(context, 10));
        GradientDrawable background = roundRect(active ? INK : SURFACE, 15, context);
        if (!active) background.setStroke(dp(context, 1), LINE);
        view.setBackground(background);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMarginEnd(dp(context, 10));
        view.setLayoutParams(params);
        view.setClickable(true);
        view.setFocusable(true);
        return view;
    }

    public static View divider(Context context) {
        View view = new View(context);
        view.setBackgroundColor(LINE);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(context, 1));
        params.topMargin = dp(context, 14);
        params.bottomMargin = dp(context, 14);
        view.setLayoutParams(params);
        return view;
    }

    public static Space space(Context context, int heightDp) {
        Space space = new Space(context);
        space.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(context, heightDp)));
        return space;
    }

    public static LinearLayout horizontal(Context context) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setLayoutParams(matchWrap());
        return row;
    }

    public static LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    public static LinearLayout.LayoutParams weight(float weight) {
        return new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, weight);
    }

    public static GradientDrawable roundRect(int color, float radiusDp, Context context) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(color);
        background.setCornerRadius(dp(context, radiusDp));
        return background;
    }
}
