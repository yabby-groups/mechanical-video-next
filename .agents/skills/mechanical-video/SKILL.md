---
name: mechanical-video
description: 用单一视频 JSON 编排分镜、普通话配音、字幕、Remotion 合成及 MP4 技术检测。
---

# mechanical-video

先读 README.md 与视频 JSON。Producer 主线程通过真实 Codex Research、Asset、Animation、Editor、QA 子代理编排三个 Skills；Python 只提供确定性运行与交接，不创建多 Agent 平台。沿用 produce.py 固定镜头、预览和缓存；修改旁白或字幕不重做 3D。结构化交接与状态门禁见 AGENTS.md 和 mechanical_video_next。

视频号统一默认旁白按用户最新选择为 config/narration-neil.json：qwen3-tts-flash / Neil（阿闻），与卷尺 EVERYDAY_EP03 的实际合成记录一致，目标 1.0 倍。Kai 只保留为历史试听。当前接口没有已验证的原生语速、风格或重音控制；不要把这些词拼进发音文本或发送被静默忽略的参数。使用口语分句、自然标点与叙述措辞引导停顿和重点；技术检查不能代替听感判断。

运行 `python3 scripts/narration.py audition --env-file <local-env>`，保留 output/narration-audition 下试听 WAV、各镜头 WAV、SRT 与实测记录。assets/audio/narration 分别缓存原始、逐句和逐镜头 WAV；FFmpeg 双遍 loudnorm 目标 -16 LUFS / -1.5 dBTP，短片第一策略允许一次不超过 2 dB 的增益与峰值限制修正；仍不合格时仅尝试一次 2:1 峰值压缩后按实测响度静态增益与限幅的第二策略，再失败即停。目标 1.0 不加 atempo；有明确需求时后期调速只允许 0.95–1.05 并重新测时。禁止为了塞进镜头而自动加速。

字幕依据 FFmpeg 静音边界（保留辅音余量）、FFprobe 的最终 WAV 时长与实际混音偏移；这是逐句对齐，不是语音识别或音素强制对齐。单独改 subtitles 不重生成音频。语句超时只缩短当前文案或延长当前镜头，记录 overrun.json。

TTS 不自动重试；submitted.json 表示请求已提交，状态不确定时不得重复付费请求。只通过环境变量、.env.local 或 --env-file 取密钥，不把密钥写入配置、日志、命令参数或 Git。

默认配置见 config/narration-default.json。用户已明确要求“和卷尺的音色一致”“设置为默认的音色”，这授权启用 Neil，无须再次索取试听确认。使用 `python3 scripts/narration.py activate --receipt <audition.json> --confirmed-selection` 记录按既有参考音色作出的明确选择，不声称用户已经试听新的文案。只有用户确实确认新试听听感时才用 --confirmed-listened。固定精确音频和 profile 哈希；未经授权改变音色/profile 不得静默沿用旧批准。既有成片保持原样，新视频号制作读取 Neil 默认配置。

完整 MP4 必须通过 ffprobe 规格、字幕区间、音轨和完整解码。技术通过只标 TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO；完整视听、遮挡、接触力学和发布权利不得冒充已验收。不得自动发布。

默认成片为横屏 1920×1080 / 30fps / H.264 + AAC。视觉参考已由用户明确为**打印机系列 EP03**，不是卷尺。采用 `presentation: mechanism-fullframe` 和 `render.framing: fullframe`：机械主体全画面、小标题与底部字幕，不恢复右侧说明栏、大标题卡或进度条。现有镜头用 `visual_profile: printer-ep03-studio-v1`、`camera_view: oblique`，经现有 EEVEE 渲染器呈现金属、灰色空间、柔和投影和克制推进；不复制旧项目架构。旁白保留已选择的 Neil，本次视觉参考不自动切换声音。旧左右分栏配置保留于 config/planetary-0*-panel.json，不覆盖旧成片。先验证关键帧和低清预览，再正式合成；不能仅凭全画面布局声称已匹配 EP03 全部质感或通过视听验收。
