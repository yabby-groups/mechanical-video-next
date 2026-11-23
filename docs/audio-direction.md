# 自动配乐与机械声音

「科学不神秘」的配乐随问题、拆解、动作和揭晓变化。新建 Producer 正式任务固定 `music_direction_version: 1`，Blueprint 带同一版本。历史任务沿用其原有音频政策。

## 从 Treatment 到实际音轨

1. Producer 以同一 Treatment 导演整片。`story-treatment` 自动记录逐场 `audio_intent`，可用每场 `music_mode` 指定意图。
2. Joint Timeline 已有画面和动作时，可在测量 Neil 前运行 `uv run python -m mechanical_video_next.director_audio plan BLUEPRINT --output audio_intent.json`。正式语音入口也会生成这个预案。音频模式依据已有 `narrative.moments`、镜头内容和动作选择，相邻同模式合并，共享连续动作的相邻镜头保持同一段。
3. Blueprint `music_direction.shots` 可按镜头 ID 覆盖 `mode` 和 `reason`，可选 `suggested_assets` 与 `gain_adjustment_db`。正式编译从注册库匹配音乐，随后按实测 Neil 和动作音效编排，在配置旁的 `audio-direction/<内容哈希>/audio_direction.json` 记录时码、镜头与剧情节点、听感目标、选曲及评分、来源与授权、包络、避让和缺失原因。
4. Editor 使用现有 `sound_events`。每条拟音指定 `action_id`、`offset_frames`、`duration_frames`、`source`、`gain_db`、`purpose` 和现有媒体权利。`trigger_evidence` 需绑定核过的动作帧 `frame`、可定位的 `position` 和证据文件 SHA-256。使用已核实的接触、释放、复位和其他实际动作。连续的真实机械动作可用稀疏音乐和现场拟音，缺少可验证触发点时保留画面的节奏。
5. 故事需要整片音乐留白时写 `music_direction: {"mode":"silence","reason":"具体的故事或观察理由"}`。局部留白使用镜头覆盖。已核实的机械拟音仍可进入有意留白段。授权或音源缺失记录 `BLOCKED` 和缺失段落，编译产物可供预演检查，正式阶段拒绝该方案。

| 模式 | 使用场景 | 默认声音 |
| --- | --- | --- |
| `curiosity` | 问题、异常、隐藏结构 | 轻电子脉冲与期待感 |
| `technology` | 拆解、零件和装配关系 | 清晰稳定的极简电子节奏 |
| `mechanical_asmr` | 啮合、锁止、滑动、复位 | 稀疏低能量底层，强调动作声 |
| `discovery` | 原理和因果揭晓、结尾兑现 | 明亮声部与适度释放 |

## 音乐库

`uv run python -m mechanical_video_next.audio_library` 显示 `assets/audio/metadata/` 中可用与被拒绝的记录。`--register METADATA.json` 校验并按文件 SHA-256 导入现有音源。样例及四个原始合成主题变奏见 [Quiet Link 权利声明](../assets/audio/bgm/starter/CC0.md) 和 [素材记录](../assets/audio/metadata/quiet-link-curiosity.json)。素材库接受 WAV、FLAC、MP3、M4A、Ogg 和 Opus，解码使用单声道 48 kHz。

- 记录 `id`、`title`、`theme`、`style`、`mood`、`energy`、`bpm`、`speech_fit`、`sfx_fit`、`loopable` 和可选 `loop_samples`。样本坐标使用解码后的 48 kHz 音轨。评分范围为 0 到 1。
- `tier` 可用 `local`、`registered`、`original`。依次考虑本地风格匹配、本地同主题、已登记合法库和原创备选。匹配考虑情绪、节奏、能量、时长、交接以及与听觉主线的兼容性。已登记外部库使用本地取证的音源和授权记录。公开歌曲只作为参考。
- `source` 和 `license.proof` 绑定实际文件 SHA-256，许可按 `media_policy` 记录授权人、许可名称、商业用途、编辑和传播、证据位置、署名和限制。只有可证明符合当前发布范围的资产业务记录才能进入正式配乐。许可条件需落实到使用及发布署名。

## 混音、增量与审查

- 默认使用 Adaptive Ducking V2。先按源音乐响度设定各段底乐，再以 100 ms PCM 窗测量 Neil、BGM 和拟音。常规旁白避让约 4–8 dB，短时语音与音乐 RMS 差以约 15 dB 为目标。音乐在 200 ms 内提前降低，Hold 为 320 ms，Release 为 600 ms。短停顿共享同一包络。若较弱的实际语音窗仍有掩蔽风险，按已绑定的音乐和拟音能量进一步降低 BGM。继续使用原有逐窗 10 dB 技术门禁。拟音窗另留 6 dB 空间。
- `audio_direction.json` 绑定 Ducking 版本、参数和以样本位置为单位的增益曲线。常规避让保持正增益，段落、循环和结尾仍按设计淡化。验收从原始音源及 Neil PCM 复算包络和最终混音。试编码 AAC 用于确定同一混音的峰值余量。旧收据仍按 V1 固定避让校验。
- `assets/audio/mixes/` 按音源、帧长、Ducking 版本和完整参数缓存结果。`scripts/clean.py` 围绕现有引用和清理锁移除过期可再生混音。解码 WAV 与试编码 AAC 随混音清理。字幕变化复用原选曲和混音键。若正在修订 BGM，编译新配置并按已有不可变交接登记，可复用同质量、同轨道、字幕和画面内容的已有合成。现有 Blender 镜头键与音频字段无关。对旧成片也可另外生成一个独立版本。

```sh
uv run python -m mechanical_video_next.director_audio postprocess BLUEPRINT.json \
  --picture EXISTING.mp4 --output output/REVISION.mp4
```

后期命令需要原影片对应的 Joint Timeline、实测 Neil 收据和原始 PCM。它通过 FFmpeg 复制 H.264 画面码流，校验帧数、时间轴、最终 AAC 和真峰值，并写 `REVISION.audio-post.json`。历史任务和原文件的交付记录仍可用于核对原版。新版本须以其精确 MP4 重新审查。

最终技术检查绑定混音、逐段版权证据、实际 AAC、语音样本和字幕时序。Speech Intelligibility 测量活动语音窗的人声与背景电平差。BGM Continuity 在源音乐有能量的旁白窗检查混音后是否持续掉到极低电平，并记录样本范围。源音乐本身较弱或静音的窗口单独记录。削波、语音完整性、逐窗掩蔽与真峰值验收照常执行。

独立 QA 在 `final-qa` 写 `music_listening_review`，包含 `media_sha256`、`method`、实际听审的 `time_range`、各项 `status` 和观察。使用 `story_fit`、`neil_clarity`、`mechanical_sync`、`opening`、`reveal`、`transitions`、`ending`。V2 新增 `bgm_continuity`，同时通过 `neil_clarity` 检查 Speech Intelligibility。实际听完全片时记录 `full_audio_listened` 和现有逐镜音画观察。没有实听时感知为 `UNKNOWN`。正式交付要求技术和独立听审同时通过。
