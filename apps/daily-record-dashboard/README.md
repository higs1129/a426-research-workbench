# 每日记录面板

一个本地优先的极简自由画布：选择日期后，可以在任意位置输入文字、粘贴并移动/缩放图片，或直接随手绘画。内容会自动保存，记录阶段不要求分类、打标签或建立关联。电脑端使用连续网格画布；手机端可进入全屏画布，在选择模式下单指移动、双指缩放和平移，并可通过“图片”按钮从手机相册选择一张或多张图片上传到当前画布。

## 启动

双击：

```text
start_daily_record_dashboard.bat
```

启动脚本会保留本机入口，并在 Tailscale 已连接时额外显示一个手机访问地址。手机与 A426 登录同一 Tailnet 后，在手机浏览器打开该地址即可。普通局域网不会被开放。

手机和电脑打开同一天时，一端保存的笔画通常会在约 1 秒内出现在另一端。为了避免无声覆盖，同一天若在两端同时落笔，较晚保存的一端会暂停自动保存并提示刷新；初版建议由手机书写、电脑查看。

记录目录优先读取用户环境变量 `DAILY_DRAFT_DATA_ROOT`。如果没有设置，则使用：

```text
%USERPROFILE%\Documents\DailyRecordDashboard
```

也可以显式启动：

```powershell
python server.py --data-root "E:\daily-records" --open-browser
```

需要同时开放 Tailscale 手机入口时：

```powershell
python server.py --data-root "E:\daily-records" --open-browser --share-tailscale
```

脚本拒绝把记录写进代码仓库。

## 数据结构

```text
<DATA_ROOT>/
  daily/
    YYYY-MM-DD.md
  assets/
    YYYY-MM-DD/
      HHMMSS-xxxxxxxxxx.png
  .state/
    YYYY-MM-DD.json
```

- `daily/` 是给人和 AI 阅读的 Markdown。
- `assets/` 保存粘贴的原始图片和自动生成的整张画布预览。
- `.state/` 保存文字框、图片位置/尺寸和笔画，供页面继续编辑。
- 画布内容在设备间同步；缩放比例和观察位置只保存在各自浏览器中，手机操作不会改变电脑视角。
- Markdown 会按画布位置提取文字，并引用画布预览和原始图片，方便周总结读取。
- 旧版纵向文字/图片记录在浏览器中自动排入自由画布，原文件不会被删除。

图片从记录中移除时，只移除当天记录里的引用，不立即删除原始图片，避免误删。
