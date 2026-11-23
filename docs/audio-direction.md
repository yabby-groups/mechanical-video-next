# 自动配乐与机械声音

新建 Producer 正式任务在 `task.json` 固定 `music_direction_version: 1`、`music_mix_mode: constant_bed` 和 `default_bgm: junge-theme-v4`。同一设置进入 Blueprint、编译配置和媒体清单。历史任务沿用各自记录。旧收据仍可直接验收，缺省 `music_mix_mode` 的任务保留旧自适应混音，缺省 `default_bgm` 的任务保留既有编排。

## 从 Treatment 到实际音轨

1. Producer 按 Treatment 确定需要留白的位置，常规段落使用整片同一 V4 音乐主题。Joint Timeline 已有画面和动作时，可在测量 Neil 前运行 `uv run python -m mechanical_video_next.director_audio plan BLUEPRINT --output audio_intent.json`。正式语音入口也生成预案。
2. 导演可在 Blueprint 的 `music_direction.asset_id` 显式指定一首已登记并获准的替代音乐，或用 `music_direction.gain_adjustment_db` 调整整片的 BGM 初始目标。局部留白使用 `music_direction.shots.<镜头ID>` 的 `mode: silence` 和具体 `reason`。音乐按全片时钟推进，留白后从对应的音乐位置淡入。镜头切换、Neil 和拟音沿用同一基础增益。
3. 编译精确查找配置的 ID，在 `audio-direction/<内容哈希>/audio_direction.json` 记录素材、来源授权、淡化包络、循环证据和响度。素材缺失、变更、退役或版权待审时记录 `BLOCKED`。新任务只有显式覆盖才会选择其他曲目。
4. Editor 使用现有 `sound_events`。每条拟音指定 `action_id`、`offset_frames`、`duration_frames`、`source`、`gain_db`、`purpose` 和现有媒体权利。`trigger_evidence` 需绑定核过的动作帧 `frame`、可定位的 `position` 和证据文件 SHA-256。使用已核实的接触、释放、复位和其他实际动作。连续的真实机械动作可用稀疏音乐和现场拟音，缺少可验证触发点时保留画面的节奏。
5. 故事需要整片音乐留白时写 `music_direction: {"mode":"silence","reason":"具体的故事或观察理由"}`。局部留白使用镜头覆盖。已核实的机械拟音仍可进入有意留白段。授权或音源缺失记录 `BLOCKED` 和缺失段落，编译产物可供预演检查，正式阶段拒绝该方案。

以下曲风匹配供未固定 `default_bgm` 的历史任务使用。

| 模式 | 使用场景 | 声音 |
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
- V4 原 WAV 保存在项目的本地媒体目录。版权待审时保持 `RIGHTS_REVIEW_REQUIRED`。退役表按素材 ID 和原始音源哈希排除当前选曲及登记，历史收据仍可读取此前绑定的原始目录项。 [V4 素材](../assets/audio/metadata/junge-theme-v4.json) · [授权核验](junge-theme-v4-rights.md) · [退役表](../assets/audio/catalog-retirements.json)

## 混音、增量与审查

- Constant Bed 测量 Neil 母带和实际混音使用的 48 kHz 单声道音乐响度。V4 取左右声道平均，给相位一致的成分保留峰值余量。默认从低于 Neil 实际响度约 12 LU 的目标算出一个初始 BGM 增益。固定主题保留 Neil 和拟音增益，混音总线保持 0 dB。
- 一次分析全片活动语音窗，按现有 100 ms / 10 dB 掩蔽规则核算分轨和实际叠加能量。必要时对整条配乐施加同一笔固定衰减。自动校准下限取 −44 LUFS 和低于 Neil 实测 28 LU 两者的较高值。所需衰减低于可用下限时报告冲突时码及所需响度。拟音单独超出语音预算或 AAC 真峰值超限时报告失败。
- 默认片头淡入 0.4 秒，片尾淡出 1.0 秒。V4 在长于 80 秒的片中从源音轨 0 秒播放，在 68.000–68.120 秒与源轨 20.000–20.120 秒做相位匹配的 120 ms 线性交叉淡化。此后每 48 秒重复接缝。验收重算拍点、宽带及低频波形相关性、交叠电平差。80 秒以内按影片时钟裁剪，留白或极短片段的淡化受区间长度约束。
- `audio_direction.json` 绑定固定增益的响度测量、掩蔽限制窗、源文件及样本包络。验收从源音乐、Neil 和机械音效复算，并用最终 AAC 核对 PCM、时序、响度和真峰值。历史 V2 保留原有 200 ms 提前量、320 ms Hold、600 ms Release、短窗自动避让和机械动作避让。
- `assets/audio/mixes/` 按音源、帧长及混音模式与参数缓存。字幕变化复用原选曲和混音键。若修订 BGM，重新编译并按已有不可变交接登记，符合相同画面、字幕和质量的现有合成可直接复用。旧成片可用带所选模式的 Blueprint 副本生成独立音频修订。

```sh
uv run python -m mechanical_video_next.director_audio postprocess BLUEPRINT.json \
  --picture EXISTING.mp4 --output output/REVISION.mp4
```

后期命令需要原影片对应的 Joint Timeline、实测 Neil 收据和原始 PCM。它通过 FFmpeg 复制 H.264 画面码流，校验帧数、时间轴、最终 AAC 和真峰值，并写 `REVISION.audio-post.json`。历史任务和原文件的交付记录仍可用于核对原版。新版本须以其精确 MP4 重新审查。

最终技术检查绑定混音、逐段版权证据、实际 AAC、语音样本和字幕时序。Speech Intelligibility 测量活动语音窗的人声与背景电平差。BGM Continuity 在源音乐有能量的旁白窗检查混音后是否持续掉到极低电平，并记录样本范围。源音乐本身较弱或静音的窗口单独记录。削波、语音完整性、逐窗掩蔽与真峰值验收照常执行。

独立 QA 在 `final-qa` 写 `music_listening_review`，包含 `media_sha256`、`method`、实际听审的 `time_range`、各项 `status` 和观察。使用 `story_fit`、`neil_clarity`、`mechanical_sync`、`opening`、`reveal`、`transitions`、`ending`。Constant Bed 与 V2 均需检查 `bgm_continuity`。实际听完全片时记录 `full_audio_listened` 和现有逐镜音画观察。没有实听时感知为 `UNKNOWN`。正式交付要求技术和独立听审同时通过。
