package com.higs.conferencerecorder;

import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class ArchitectureActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout content = createScreen("初版架构", "先验证信息结构，再接采集能力", true);

        content.addView(UiKit.sectionTitle(this, "信息层级"));
        LinearLayout hierarchy = UiKit.card(this);
        hierarchy.addView(level("会议", "可以保存多届、多场会议"));
        hierarchy.addView(UiKit.divider(this));
        hierarchy.addView(level("日期 / Session", "允许未来增加平行会场和房间"));
        hierarchy.addView(UiKit.divider(this));
        hierarchy.addView(level("报告人 / 海报", "现场选择，也允许时间自动推荐"));
        hierarchy.addView(UiKit.divider(this));
        hierarchy.addView(level("独立报告包", "音频、照片、备注、逐字稿、结构化内容"));
        content.addView(hierarchy);

        content.addView(UiKit.sectionTitle(this, "手机到电脑的数据流"));
        LinearLayout flow = UiKit.card(this);
        flow.addView(flowStep("手机本地原始包", "先写入用户授权目录，断网也能工作", UiKit.ACCENT));
        flow.addView(UiKit.divider(this));
        flow.addView(flowStep("Synology Drive 单向上传", "手机写入成功与群晖收到必须分开标记", UiKit.ACCENT));
        flow.addView(UiKit.divider(this));
        flow.addView(flowStep("A426 只读 W: 处理", "读取群晖原始包，结果写到外部 conferences 目录", UiKit.CORAL));
        flow.addView(UiKit.divider(this));
        flow.addView(flowStep("会议级批量汇总", "在保留来源链接的前提下合并多个报告包", UiKit.CORAL));
        content.addView(flow);

        content.addView(UiKit.sectionTitle(this, "这版已经验证什么"));
        LinearLayout ready = UiKit.card(this);
        ready.addView(check("多会议入口的数据模型"));
        ready.addView(check("日期、Session、报告人的选择路径"));
        ready.addView(check("海报检索与海报包入口"));
        ready.addView(check("每个对象都有独立逻辑目录与状态槽"));
        ready.addView(check("本机快速备注可保存"));
        ready.addView(check("可选择 Synology 本地同步根目录"));
        ready.addView(check("可导出 manifest、现场备注和 READY 测试包"));
        content.addView(ready);

        content.addView(UiKit.sectionTitle(this, "明确没有做的部分"));
        LinearLayout pending = UiKit.card(this);
        pending.setBackground(UiKit.roundRect(UiKit.WARNING_SOFT, 18, this));
        pending.addView(pending("麦克风录音与录音中断恢复"));
        pending.addView(pending("相机拍 PPT / 海报与自动归包"));
        pending.addView(pending("实时或准实时语音转写"));
        pending.addView(pending("群晖到达确认、W: 扫描与完整性校验"));
        pending.addView(pending("会议手册 PDF 的完整导入与版本 diff"));
        content.addView(pending);

        LinearLayout decision = UiKit.card(this);
        decision.setBackground(UiKit.roundRect(UiKit.INK, 18, this));
        decision.addView(UiKit.text(this, "建议你这轮只判断两件事", 18,
                android.graphics.Color.WHITE, true));
        TextView text = UiKit.text(
                this,
                "① 现场是否能在 1–2 次点击内选到正确报告；\n② 报告包页面里的入口和状态是否符合你的思路。",
                14,
                android.graphics.Color.rgb(205, 219, 222),
                false);
        LinearLayout.LayoutParams params = UiKit.matchWrap();
        params.topMargin = UiKit.dp(this, 9);
        decision.addView(text, params);
        content.addView(decision);
    }

    private LinearLayout level(String title, String detail) {
        LinearLayout row = UiKit.horizontal(this);
        row.addView(UiKit.pill(this, title, UiKit.ACCENT, UiKit.ACCENT_SOFT));
        row.addView(UiKit.text(this, detail, 13, UiKit.TEXT_SECONDARY, false), UiKit.weight(1f));
        return row;
    }

    private LinearLayout flowStep(String title, String detail, int color) {
        LinearLayout block = new LinearLayout(this);
        block.setOrientation(LinearLayout.VERTICAL);
        block.setLayoutParams(UiKit.matchWrap());
        block.addView(UiKit.text(this, title, 16, color, true));
        TextView copy = UiKit.text(this, detail, 13, UiKit.TEXT_SECONDARY, false);
        LinearLayout.LayoutParams params = UiKit.matchWrap();
        params.topMargin = UiKit.dp(this, 3);
        block.addView(copy, params);
        return block;
    }

    private TextView check(String value) {
        TextView view = UiKit.text(this, "✓  " + value, 14, UiKit.TEXT_PRIMARY, false);
        view.setPadding(0, UiKit.dp(this, 6), 0, UiKit.dp(this, 6));
        return view;
    }

    private TextView pending(String value) {
        TextView view = UiKit.text(this, "○  " + value, 14, UiKit.WARNING, false);
        view.setPadding(0, UiKit.dp(this, 6), 0, UiKit.dp(this, 6));
        return view;
    }
}
