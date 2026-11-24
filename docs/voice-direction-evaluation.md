# 门把手导演式配音评测

**IndexTTS 2.5 已退出支持。** 用户完成原版人工试听后，选定 CosyVoice 3.0 作为导演式引擎。Audiogen Neil 继续作为正式默认和整轨回退。下面先记录本轮样片，再保留原三路评测。

## CosyVoice 收敛后的样片

新版时长 27.767 秒。833 帧解码画面与原调整版逐字节一致。先复用全部八句调整时间轴，再只重配 `mount-1`。重配首轮超出镜头槽，第二轮用“平稳连贯地讲解，句号处稍停”生成 2.740 秒的有效音频，其余七句保持原 WAV 哈希。重复请求命中封存缓存，输出 MP4 和重配版一致。随后复用新版八句，把 `mount-2` 提前 12 帧。 [新版 MP4](../output/voice-director-door-handle/cosyvoice-consolidation/final/audition.mp4) · [字幕](../output/voice-director-door-handle/cosyvoice-consolidation/final/narration.srt) · [实测时间轴](../output/voice-director-door-handle/cosyvoice-consolidation/final/timeline.json) · [哈希和采样校验](../output/voice-director-door-handle/cosyvoice-consolidation/media-verification.json)

新版 MP4 SHA-256 为 `3a74ef32620345b1ce472a7c901e89d4ee3a1850ef14b6bab33fd5c018c230f9`。WAV 和 AAC 各有 1,332,800 个有效样本，通过采样对齐、响度与真峰值检查。AAC 为 −16.41 LUFS、−1.59 dBTP，WAV 为 −16.40 LUFS、−1.58 dBTP。

| 位置 | 实测变化 |
| --- | --- |
| 3.55 秒，第二句开始 | 两句开场之间的空隙由 57 ms 调到 237 ms |
| 6.13 秒，指出根部 | 上一句结束后的空隙由 900 ms 调到 587 ms |
| 12.83 秒，切到门板 | 上一句结束后的空隙由 1.578 秒缩至 1.345 秒，仍有留白复核提示 |
| 12.83 秒，“先看门板” | 原句有至少 500 ms 的句内低电平提示，新取样未触发此提示 |
| 16.27 秒，壳体对比 | 提前 400 ms，前后句隙各约 693 ms |

“松开”相对第 51 帧的 SenseVoice 估计仍为提前 110 ms，落在 450 ms 配置容差内。“压簧”仍转写成“压黄”，定位在 8.33 秒起的剖口句。新取样的参考声纹余弦为 0.784，八句范围为 0.665–0.872。新版没有人工复听，语气自然度、情绪和重音、实际术语发音、声线连贯性与视听配合均为 `UNKNOWN`。该样片使用原有 macOS 合成参考，限本机比较。 [新版 SenseVoice QA](../output/voice-director-door-handle/cosyvoice-consolidation/final/quality-sensevoice.json)

## 退出支持与回归验证

- 删除 IndexTTS 模型检查、加载与推理、MPS 特殊路径、情绪向量和拼音注释、运行配置、Schema 选项及自动比较候选。项目依赖、锁文件、安装入口与生产工作流无独立 IndexTTS 依赖。支持的语音引擎为 `cosyvoice3` 和 `neil`。旧引擎配置报错，历史回执与试听保留。
- 清理 `.voice-data/models/indextts25` 的 15 个专属文件、`.voice-data/runtime/index-source` 的上游快照及 `.voice-data/runtime/index-runtime` 的独立环境。核对了保留组件的配置和链接。模型目录原占用 7,128,166,400 字节，三处合计占用 8,699,232,256 字节，清理时卷可用空间实测增加 7,249,920,000 字节。参考音频、试听片、句级缓存及诊断保留。五个与安装回执哈希不一致的小文件另存于历史证据目录。 [清理明细](../output/voice-director-door-handle/cosyvoice-consolidation/index-cleanup.json)
- 使用缺失的 CosyVoice 模型路径触发整轨回退，门把手八句均命中 Neil 缓存，整轨响度 −16.85 LUFS、真峰值 −1.42 dBTP，均通过。模拟第二句推理失败时，第一句也重新走 Neil。另用独立缓存触发一次真实 Neil 网络合成，成功生成 156,374 个有效样本，回执记录了失败原因及缓存未命中。该单句测试的 WAV 真峰值为 −1.71 dBTP，响度为 −17.19 LUFS，超出当前容差，质量状态保留 `NEEDS_REVIEW`。 [门把手回退回执](../output/voice-director-door-handle/cosyvoice-consolidation/fallback-recheck/timeline.json) · [无缓存单句回执](../output/voice-director-door-handle/cosyvoice-consolidation/neil-live-smoke/timeline.json)
- 全套发现 626 项测试，618 项通过，8 项跳过。623 项使用测试进程的 3 GiB 工作目录上限，3 项预算测试以默认配置运行。 [回归日志](../output/voice-director-door-handle/cosyvoice-consolidation/regression-final.log) · [默认预算测试](../output/voice-director-door-handle/cosyvoice-consolidation/render-budget.log)

## 历史三路评测

三路使用门把手原工程的第 0 至 832 帧，1080p、30 fps，共 27.767 秒。统一使用八句文案，试听只混入旁白，以便直接比较。A 提取原 Audiogen Neil 存档 PCM，保留原来的句子位置。B 和 C 在镜头内部调整旁白槽以容纳实测句长，三路解码后的画面完全一致。两个本地引擎共用一段 macOS 合成普通话作参考，使用范围限于本次本机对比。 [样例配置](../examples/door-handle-return/voice-comparison.json) · [对比回执](../output/voice-director-door-handle/comparison.json)

| 版本 | 下载与证据 | 试听 MP4 SHA-256 |
| --- | --- | --- |
| A · Audiogen Neil | [MP4](../output/voice-director-door-handle/A-neil/audition.mp4) · [WAV](../output/voice-director-door-handle/A-neil/narration.wav) · [时间轴](../output/voice-director-door-handle/A-neil/timeline.json) · [SenseVoice QA](../output/voice-director-door-handle/A-neil/quality-sensevoice.json) | `7b743089dc8834df7f3df15d4408d7307da1b43baace1463e242f6af43a39ce1` |
| B · CosyVoice 3.0 | [MP4](../output/voice-director-door-handle/B-cosyvoice3/audition.mp4) · [WAV](../output/voice-director-door-handle/B-cosyvoice3/narration.wav) · [时间轴](../output/voice-director-door-handle/B-cosyvoice3/timeline.json) · [SenseVoice QA](../output/voice-director-door-handle/B-cosyvoice3/quality-sensevoice.json) | `836a7e9721dbb09919832742ae401ac80831a160a131ed32a6f55ebd2fbb3ffc` |
| C · IndexTTS 2.5（已退出） | [MP4](../output/voice-director-door-handle/C-indextts25/audition.mp4) · [WAV](../output/voice-director-door-handle/C-indextts25/narration.wav) · [时间轴](../output/voice-director-door-handle/C-indextts25/timeline.json) · [SenseVoice QA](../output/voice-director-door-handle/C-indextts25/quality-sensevoice.json) | `75adb228970a0c326cd6f1353cfee450070f61f7f74467bca9590feca5a1c87b` |

## 表演、发音与动作

| 评测维度 | 观测结果 |
| --- | --- |
| 中文自然程度 | 三路均为 `UNKNOWN`，待实际听审。B 的 `mount-1` 有句内低电平提示，句首距上一句结束约 1.03 秒。这两处可随画面一起核听。 |
| 情绪表现 | B 的中文表演指令和重音、C 的情绪向量均进入真实推理。样例由日常疑问过渡至内部展示、平稳解释、明确指出转轴。三路情绪贴合度均为 `UNKNOWN`。 |
| 机械术语正确性 | 三路识别均把“压簧”转写为“压黄”。SenseVoice 差异用于定位，实际读音均为 `UNKNOWN`。 |
| 声音角色一致性 | 各轨使用单一角色。B 各句与参考音频的声纹嵌入余弦相似度为 0.665–0.872，供定位复核。A 和 C 缺少对应声纹数据。三路听感一致性均为 `UNKNOWN`。 |
| 旁白与画面的配合 | 三路均通过 PCM 放置、画面帧数及 AAC 解码位置校验。回程从第 51 帧附近开始，SenseVoice 估计“松开”在 A 提前 353 ms、B 提前 460 ms、C 提前 280 ms。配置容差为 450 ms，B 超出 10 ms，需核听。实际配合感为 `UNKNOWN`。 |

初版技术检查查看了 A 在回程附近的四张采样图。1.433 秒时把手仍压下，1.700 秒时已开始抬回，2.167 秒时接近水平。表中的听感状态为初版技术检查记录。以上观测绑定表中的三份 MP4。 [画面与动作帧记录](../output/voice-director-door-handle/anchor-frames.json)

以 B 为基础，把 `hook-1` 的句首留白从 0 调到 350 ms。八句 WAV 哈希一致，其余七句起点和全部画面帧保持一致。“松开”的识别估计从提前 460 ms 收敛到提前 110 ms，进入配置容差。调整版的 WAV 和 AAC 均通过响度与真峰值检查，实际音画配合待听审。调整版 MP4 SHA-256 为 `8d83bfd883f13d75369e08cae6e5b02b3badbc1a545841eb4f5504fe37f94a75`。 [调整版 MP4](../output/voice-director-door-handle/retimed-cosyvoice/audition.mp4) · [实测时间轴](../output/voice-director-door-handle/retimed-cosyvoice/timeline.json) · [SenseVoice QA](../output/voice-director-door-handle/retimed-cosyvoice/quality-sensevoice.json)

## Apple M3、16 GB 实测

| 指标 | A · Neil 存档 | B · CosyVoice CPU | C · IndexTTS CPU |
| --- | ---: | ---: | ---: |
| 八句 PCM 时长 | 23.372 秒 | 22.717 秒 | 24.398 秒 |
| 八句推理耗时、实时系数 | 未取得 | 221.10 秒、9.73× | 389.82 秒、15.98× |
| worker 峰值 RSS | 未取得 | 5.56 GB | 6.70 GB |
| 模型目录，包括依赖权重 | 未取得 | 5,427,049,295 字节 | 7,082,493,352 字节 |
| AAC 综合响度与真峰值 | −16.85 LUFS、−1.43 dBTP | −16.37 LUFS、−1.50 dBTP | −16.21 LUFS、−1.78 dBTP |
| 单次视频生产成本 | 存档调用账单未知 | 本次调用账单为零，电耗与完整视频总成本未测 | 本次调用账单为零，电耗与完整视频总成本未测 |
| 重复生成稳定性 | 使用存档，未重新请求服务 | 八句命中缓存。单独冷缓存重跑 `hook-1`，WAV 哈希与 137,280 样本均相同 | 八句命中缓存。单独冷缓存重跑 `hook-1`，WAV 哈希与 155,481 样本均相同 |

推理耗时来自首次生成的 worker 回执，包含 CosyVoice 的声纹测量，模型初始化单独计时。峰值 RSS 为进程观测值，设备总内存占用未测。三路 WAV 与 AAC 均通过现有响度与真峰值检查。 [CosyVoice 实测](../output/voice-director-door-handle/measurement.log) · [IndexTTS CPU 实测](../output/voice-director-door-handle/index-cpu-measurement.log)

CosyVoice 上游入口选择 CPU 或 CUDA。IndexTTS 在 MPS 实际完成 `hook-1`，初始化 105.86 秒，推理 204.92 秒，峰值 RSS 6.60 GB。CPU 首次推理同句用时 86.97 秒。MPS worker 后续以 −15 退出，原因未确认。三路交付里的 B 和 C 都使用 CPU，两个本地模型分开运行。 [IndexTTS MPS 实测](../output/voice-director-door-handle/index-measurement.log)

## 默认引擎、回退与单句重配

原评测中 CosyVoice 3.0 直接接收表演和重音指令。本样例的推理耗时、峰值 RSS 和权重目录小于 IndexTTS 2.5。试听使用本机合成参考。 [现行调用说明](voice-direction.md)

指向缺少 CosyVoice 权重的目录后，整轨回退 Neil，八句全部使用已有 Neil 缓存。同一次试听只使用一个引擎。单独重配 `reveal-2` 时，CosyVoice 实际重新合成该句，其余七句沿用原 WAV 哈希，联合时间轴随实测句长重新生成。 [回退时间轴](../output/voice-director-door-handle/fallback/timeline.json) · [单句重配时间轴](../output/voice-director-door-handle/single-replacement/timeline.json)

## 回归验证

全套发现 626 项测试，618 项通过，8 项跳过，包含全部 7 项新增配音测试。保留现有生产素材，使用测试进程的 3 GiB 工作目录上限运行 623 项，3 项渲染预算测试在默认 2 GiB 上限下运行。三路试听的 WAV、MP4、时间轴和 QA 文件哈希与对比回执一致。用联合时间轴逐句核验后，每路均有 833 帧对应的 1,332,800 个 PCM 样本。 [全套测试日志](../output/voice-director-door-handle/test-suite-final.log)
