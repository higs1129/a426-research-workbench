# 会议记录（Android 架构原型）

这是面向 vivo / OriginOS 手机的原生 Android 初版，用来先验证会议现场的信息结构与点击路径：

```text
会议
  -> 日期 / Session
    -> 报告人 -> 报告包
  -> Poster Session
    -> 海报检索 -> 海报包
```

当前版本号为 `0.9.2-clickable-transcript-test`。它已经可以生成包含真实录音、PPT / 海报照片、现场备注和校验信息的最小报告包，也可以直接从手机文件选择器导入会议 JSON。本版把麦克风 PCM 同时送入 AAC 录音编码器和英文识别器，并在 vivo 未提供 Android 系统识别服务时改用 App 自带的 Vosk 离线引擎；OCR 和 AI 整理仍由后续电脑端流程完成。

## 已连通

- 多会议入口的数据模型。
- 会议手册第一版的完整详细议程：4 场大会报告和 6 个专题中的 36 场报告。
- 131 张海报的编号、题目、作者、单位、作者-单位映射和通讯作者标记。
- 通过 Android 系统文件选择器离线导入会议 JSON；新 ID 追加会议，相同 ID 更新议程。
- 导入前校验 schema 版本、必填字段以及会议 / 日期 / Session / 报告 / 海报 ID 唯一性，失败时不覆盖现有数据。
- 导入后的会议目录保存在 App 私有目录并即时刷新，不依赖重新安装 APK。
- 首页只显示当前会议、正在进行或下一项报告、后续三项和浏览入口；JSON、会议切换与同步授权移入会议管理页。
- 多会议场景可以在会议管理页切换“当前会议”，首页始终围绕一个现场上下文工作。
- 报告详情页以录音状态和计时为主视觉，PPT / 海报拍摄与快速备注为第二层，文件清单、处理状态和逻辑路径默认折叠。
- 未配置同步目录时，用户可以先完成现场采集；第一次导出报告包时再进入目录授权。
- 保存快速备注后，“现场备注”和材料摘要会立即更新；备注先按会议 ID + 条目 ID 保存到 App 私有草稿，导出时写入 `notes/field-note.md`。
- 本机材料清单支持确认删除未导出的录音；已导出的不可变报告包不受影响，录音过程中禁止删除。
- `poster` 与日程中的 `poster-session` 统一为海报记录模式，只显示拍图、快速备注和导出，不再提供录音；旧版误录的音频不会进入新海报包。
- 日期、Session、报告人的选择路径。
- 根据现场时间推荐“正在进行 / 下一项”报告。
- 按编号、题目、作者或单位检索海报。
- 报告包 / 海报包页面及音频、照片、备注、转写、结构化内容状态槽。
- 每个报告包的本机快速备注，使用应用私有 `SharedPreferences` 保存。
- 报告包的逻辑目录预览，但不在电脑或仓库中实际创建数据目录。
- 通过 Android Storage Access Framework 选择 `vivo-synology` 等用户目录，不申请宽泛文件权限。
- 在所选目录下写出不可变 `manifest.json + notes/field-note.md + READY` 报告包。
- 独立写入连接测试包，验证 Synology Drive 是否能把手机目录上传到群晖。
- 报告录音支持开始、暂停、继续、结束和追加片段，使用前台麦克风服务保持录音。
- 录音服务只占用一次麦克风，将 16 kHz 单声道 PCM 非阻塞地分流给 AAC/M4A 编码器和英文实时识别器；字幕处理缓慢或失败不会阻塞录音。
- Android 13+ 录音时可显示 `en-US` 系统英文识别的临时结果和已确认分段；识别器异常时最多自动恢复三次，录音继续保存。
- 若手机没有可用的 Android `RecognitionService`，页面可从 Vosk 官方地址下载约 40 MB 的 `vosk-model-small-en-us-0.15`。模型保存在 App 私有免备份目录，安装后实时字幕完全离线运行。
- 结束录音后将实时英文结果保存为 `transcript/transcript.txt + transcription.json`；不完整结果在元数据中标为 `partial`。
- 字幕卡只滚动预览最近 5 个确认片段和当前临时句；结束后可直接点击预览文字或“查看完整逐字稿”打开全部内容，也可单独删除本机逐字稿及元数据，不影响 M4A 或已经导出的报告包。
- Android 13+ 仍可将已录制的 M4A 解码为 PCM 音频流，重新交给手机系统英文识别服务；优先选择可确认的本机识别，只有可能联网的系统识别时会在发起前明确二次确认。
- 手机转写成功后保存 `transcript/transcript.txt + transcription.json`，并随报告包导出；系统服务未接收完整音频时不会标记为完整逐字稿。
- 调用手机系统相机拍摄多张 PPT / 海报照片；录音期间也可以进入相机。
- 本机查看照片清单、调用图片查看器预览，以及删除尚未导出的暂存照片。
- 导出时复制 M4A/JPEG 原始文件，并在 `manifest.json` 中记录字节数和 SHA-256。

## 代码结构

```text
app/src/main/java/com/higs/conferencerecorder/
  model/                       # Conference / Day / Session / ProgramItem
  data/
    ConferenceRepository.java # 页面依赖的稳定读取接口
    AssetConferenceRepository # 合并内置数据与手机私有导入数据
    ConferenceJsonParser.java # JSON schema 与 ID 完整性校验
    ConferenceImportStore.java # SAF 导入、同 ID 合并与原子保存
    ActiveConferenceStore.java # 当前会议选择，避免首页同时展开多个会议
    ScheduleAdvisor.java       # 当前 / 下一项推荐
    ReportPackageStore.java    # 原型阶段的本机备注草稿
    CaptureSessionStore.java   # App 私有采集暂存区与音频/照片片段清单
    TranscriptStore.java       # 手机系统转写文本与元数据
    StorageTargetStore.java    # 持久化用户授予的目录 URI
    StorageTreeWriter.java     # SAF 目录与文件写入，不覆盖旧包
    PackageExporter.java       # 生成不可变报告包和 READY
  MainActivity.java            # 当前会议、当前 / 下一项与后续日程
  MeetingManagementActivity.java # 会议切换、JSON 导入与同步配置
  ConferenceActivity.java      # 日期与 Session
  SessionActivity.java         # 报告人选择
  PosterSearchActivity.java    # 海报检索
  PackageActivity.java         # 报告包 / 海报包
  AudioRecordingService.java   # 可暂停的前台麦克风录音服务
  recording/
    PcmAacRecorder.java        # 单次麦克风采集、AAC/M4A 编码与实时 PCM 分流
  transcription/
    M4aPcmStreamer.java        # 将 App 录制的单声道 M4A 解码为 PCM 流
    SystemAudioTranscriber.java # 调用 Android SpeechRecognizer 转写已有录音
    LiveSystemTranscriber.java # 非阻塞接收实时 PCM 并生成英文系统字幕
    LiveTranscriber.java       # 系统与离线识别器共用的实时音频接口
    VoskLiveTranscriber.java   # 消费同一 PCM 的本地 Vosk 英文流式识别
    VoskModelManager.java      # HTTPS 下载、安全解压并校验离线英文模型
  ArchitectureActivity.java    # 初版边界说明
  StorageAccessActivity.java   # 同步目录授权与连接测试
```

页面不直接读取 PDF，也不依赖具体会议文件。会议来源通过 `ConferenceRepository` 隔离，因此后续可以加入：

1. 手册 PDF 导入与版本差异检查；
2. 手机本地数据库与采集状态；
3. A426 同步队列；
4. 电脑端转写、OCR 与批量会议报告生成。

## 本机会议数据边界

- `app/src/main/assets/conference.example.json` 是可提交的通用配置示例。
- `app/src/debug/assets/conference.local.json` 是从用户本机手册生成的真实会议数据，已被本目录 `.gitignore` 排除，不进入 Git。
- 用户在 App 中选择的 JSON 会复制到 Android App 私有目录；以后导入同一会议 ID 时只替换会议目录数据，不修改采集暂存区或报告包。
- `tools/import_microcavity_2026_pdf.py` 是可提交的导入与校验代码；它自动识别 54 页第一版和 58 页完整版，只接受显式 PDF 输入和显式 JSON 输出，不会写入 W 盘。
- 手册第一版中有 3 场报告题目原文为“更新中”，并且圆桌论坛结束时间在总体表与详细表中分别为 17:00 和 17:30；App 采用详细表的 17:30，同时保留待核验说明。

## 从会议手册重新生成本机数据

导入器依赖 `pdfplumber`，使用 PDF 表格边界、字体和字符坐标恢复跨行报告、作者单位上标和通讯作者星号。先执行只读校验：

```powershell
python tools/import_microcavity_2026_pdf.py `
  --input-pdf 'C:\path\to\2026微腔光子学会议手册_第一版.pdf' `
  --output-json app/src/debug/assets/conference.local.json `
  --check-only
```

确认结果后，去掉 `--check-only` 生成手机可导入 JSON。第一版校验 40 场报告和 131 张海报；完整版校验 39 场报告和 137 张海报。两种版型都会检查唯一编号、报告时间不重叠、字段完整、作者单位编号有效，以及不残留原型占位条目。

同一个生成结果也可以直接传到手机，在 App 首页右上角进入“管理 → 导入或更新会议 → 选择会议 JSON”。导入成功后会议列表立即刷新，后续新增会议不需要重新打包或安装 APK。当前导入器支持 `schemaVersion` 1–2，单个 JSON 上限为 10 MB。

手机报告包写入用户授权的 Synology Drive 本地同步目录，再由 Drive 单向上传群晖。群晖原始资料由 A426 通过 `W:\` 只读；转写、OCR 和易读结果写入 `DAILY_NOTE_DATA_ROOT/meetings/`，不得写入代码仓库，也不得把处理结果写回 `W:\`。

真实采集包结构：

```text
ConferenceRecorder/<conference-id>/talks/<item-id>/packages/package-<timestamp>/
  audio/segment-001.m4a
  images/image-001.jpg
  notes/field-note.md
  transcript/transcript.txt
  transcript/transcription.json
  manifest.json
  READY
```

只有全部文件成功写入后才创建 `READY`。录音和照片在导出前保留于 Android App 私有外部目录；卸载 App 会清除此暂存区，因此完成测试后应及时导出。

Android 系统转写是厂商能力检测型功能；V2359A 真机已确认没有向本 App 暴露可用的 `RecognitionService`。因此 0.9.0 增加可下载的 Vosk 小型英文模型作为离线主兜底：模型约 40 MB，运行时预计占用约 300 MB 内存，安装前要求至少 150 MB 可用存储。无论使用系统还是 Vosk，字幕失败都只改变字幕状态，不应影响 M4A。

## 英文实时字幕真机验收

1. 安装 debug APK，进入报告页。如果显示 vivo 不提供系统识别服务，先点击“下载离线英文模型（约 40 MB）”，等待安装完成。
2. 打开一场报告并开始录音；已安装离线模型时会直接在手机本地生成字幕，系统识别可能联网时仍会明确询问。
3. 先播放 10 分钟英文科研报告，确认页面持续出现英文、暂停/继续有效、结束后 M4A 和逐字稿均存在。
4. 再连续运行 45–60 分钟，期间锁屏、回到 App、打开系统相机拍照，并观察字幕恢复、手机发热和电量。
5. 安装模型后关闭 VPN、Wi-Fi 和移动数据再测试；离线字幕应继续工作，原始 M4A 不得中断或变成空文件。

## 本地构建

已在 A426 上复用以下环境验证：

- JDK 17：`C:\Users\Administrator\AppData\Local\Android\devtools\jdk\jdk-17.0.20+8`
- Gradle 8.10.2：`C:\Users\Administrator\AppData\Local\Android\devtools\gradle\gradle-8.10.2`
- Android SDK 35：`C:\Users\Administrator\AppData\Local\Android\Sdk`

```powershell
$env:JAVA_HOME = 'C:\Users\Administrator\AppData\Local\Android\devtools\jdk\jdk-17.0.20+8'
$env:ANDROID_SDK_ROOT = 'C:\Users\Administrator\AppData\Local\Android\Sdk'
& 'C:\Users\Administrator\AppData\Local\Android\devtools\gradle\gradle-8.10.2\bin\gradle.bat' --no-daemon assembleDebug lintDebug
```

APK 输出：

```text
app/build/outputs/apk/debug/app-debug.apk
```

## 这轮原型应重点判断

1. 现场能否在 1–2 次点击内选到正确报告；
2. 报告包页面里的采集入口、状态和逻辑目录是否符合使用习惯；
3. Poster 是否应放在日期页、会议首页，还是两处都保留入口。
