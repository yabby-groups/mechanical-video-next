# 导演式配音

Audiogen Neil 是正式制作默认引擎。新项目可显式启用 CosyVoice 3.0，交付实测 WAV、SRT、时间轴和可选试听 MP4。成片进入独立视听 QA。CosyVoice 运行环境独立于 Blender、Remotion 和项目 Python。

`voice_direction.py` 编译剧情控制，`voice_engines.py` 管理适配器与句级缓存，`voice_worker.py` 在独立进程调用模型。`directed_narration.py` 复用 `joint_timeline.py` 的 PCM 放置、字幕时钟与校验。`voice_quality.py` 调用现有响度与静音检查，可选加载 SenseVoice。Voice Director Skill 只需在故事意图、情绪曲线或重点发生变化时使用。 [Voice Director Skill](../.agents/skills/voice-director/SKILL.md)

## 从故事编排到实测时间轴

Voice Director Skill 读取故事、分镜、动作轨和讲解重点，按剧情段落编写 `beats`。一个段落可以覆盖多个句子。先明确观众要看见的动作和要理解的因果，再决定情绪、语气和关键词。缺少悬念或转折时，用 `script_feedback` 提交给脚本阶段。门把手示例从日常疑问进入剖口，再转到固定壳体和沿轴线拆解。

`plan` 复制获准文案，按知识点匹配角色配置中的词，与本句指定的强调词合并，检查声线和引擎一致性、时长、镜头和动作锚点。生成物遵循 `config/voice-direction.schema.json`。动作锚点以画面帧指定，绑定文本中的短语和出现次数。

```sh
uv run python -m mechanical_video_next.directed_narration \
  --profile local-voice-profile.json plan joint-plan.json beats.json voice_direction.json \
  --engine cosyvoice3
uv run python -m mechanical_video_next.directed_narration \
  --profile local-voice-profile.json render joint-plan.json voice_direction.json output/voice-audition \
  --picture picture.mp4
```

联合时间轴使用 30 fps、48 kHz 单声道 PCM。句首留白决定实际起始采样点，句尾留白从最迟结束点预留。FFmpeg 复用现有静音边界处理和响度规整。时长取实际 PCM 样本数，字幕随之更新。若越过硬边界，保留可复用的单句音频并结束本次组装，依据实测缩短文字或在镜头内调整旁白槽。MP4 复用输入画面流，验证画面帧数及 AAC 解码后的音频位置。

使用 `produce --episode` 的逐镜头工程时，可在 `edit.json` 设置 `"directed_timeline": "relative/path/timeline.json"`。实测回执须与工程的镜头顺序及 `narration.txt` 每镜一段的文案一致。入口核验合成 PCM 后按镜头切分 WAV，沿用实测字幕和镜头帧数交给 Remotion。制作账本继续使用 Neil 认证流程。

只重配一条时，复制导演配置并修改该句的语气、重音、留白，或增加 `"take": "take-2"` 生成不同抽样。指定原回执并输出到新目录。

```sh
uv run python -m mechanical_video_next.directed_narration \
  --profile local-voice-profile.json render joint-plan.json voice_direction-revised.json output/voice-take-2 \
  --segment hook-1 --prior output/voice-audition/timeline.json --picture picture.mp4
```

只改留白或旁白槽时，使用 `--prior` 并省略 `--segment`。画面、机械动作及句子顺序须匹配原回执。回放实测音频会核验 WAV 哈希和整轨 PCM。单句重配要求同一引擎和声音角色。CosyVoice 校验模型、参考音频、上游源码、依赖及处理配置，Neil 校验原声音配置。修改文案时先更新主脚本与时间轴，重新编译导演配置。

## 引擎和声音角色

复制 `config/voice-profile.json`，填写本机的 `runtime_python`、`source_dir`、`runtime_revision`、`device` 和参考音频的 `path`、`sha256`、`usage` 与 `evidence`。本地模型使用同一段已授权或有记录的合成参考音频。Neil 继续使用既有声音预设。

| 引擎 | 进入推理的控制 | 能力降级 |
| --- | --- | --- |
| Audiogen Neil | 既有项目请求和声音配置 | 记录情绪、词重音、独立语速和读音覆盖的降级 |
| CosyVoice 3.0 | `inference_instruct2` 的中文表演及重音指令、`speed`、参考音频 | 强度影响中文提示词。接口提供提示词引导的情绪和词重音；结构化拼音覆盖在回执中标为不支持 |

共享配置启用 `"fallback_engine": "neil"`。CosyVoice 初始化或推理失败时，整条音轨回退 Neil，并在时间轴的 `selected_engine`、`actual_engine` 和 `fallback_reason` 中记录。自定义配置也可通过 `--fallback-neil` 请求同一规则。使用 `--prior` 复用原音轨时保持原引擎，单句重配失败会保留原回执。复用 Neil 缓存时使用缓存录制时的 API 地址，缓存缺失时通过原有凭据合成。

IndexTTS 2.5 已退出支持。使用旧配置时，从共享配置重新复制一份并迁移声音设置，`selected_tts` 使用 `cosyvoice3` 或 `neil`。历史试听与回执仍可核对。 [门把手配音评测](voice-direction-evaluation.md)

### 模型准备

默认模型目录 `.voice-data/models`，缓存目录 `.voice-data/cache`，可用 `--models`、`--cache` 或 `MECHANICAL_VOICE_MODELS`、`MECHANICAL_VOICE_CACHE` 分别放到外置 SSD。按需准备单个模型。渲染前检查本地文件，worker 为 Hugging Face 和 Transformers 设置离线模式。CosyVoice 上游的可选 WeText 前端仍尝试访问 ModelScope，本机收到 403 后走上游基础文本规整路径并完成合成。事务结束时关闭模型进程并清理临时 PCM，失败保留回执和 worker 日志。

- **CosyVoice 3.0** 使用 CosyVoice `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` 及 Matcha-TTS `dd9105b34bf2be2230f4aa1e4769fb586a3c824e`。在独立 Python 3.11 环境安装 macOS ARM64 依赖。实测环境的核心版本为 PyTorch 和 Torchaudio 2.3.1、ONNX Runtime 1.18.0、NumPy 1.26.4、Transformers 4.51.3。从官方模型仓库取 `Fun-CosyVoice3-0.5B-2512`，放在 `cosyvoice3/`，包含 `CosyVoice-BlankEN/`。上游入口自动选择 CPU 或 CUDA，本机采用 CPU。 [上游及模型说明](https://github.com/FunAudioLLM/CosyVoice/tree/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc) · [模型卡](https://modelscope.cn/models/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)

缓存记录语句、推理控制、角色、参考音频和模型文件哈希、程序与依赖版本。每句成功写入音频和测量回执后才完成缓存封存。修改停顿或画面时间戳可以复用合成，修改推理参数或 `take` 会使该句重新合成。

## 门把手对比

```sh
uv run python -m mechanical_video_next.directed_narration \
  --profile local-voice-profile.json \
  compare examples/door-handle-return/voice-comparison.json \
  output/voice-director-door-handle/compare-neil-cosyvoice \
  --engine neil --engine cosyvoice3 --repeat-segment hook-1
```

比较命令需要现有门把手联合时间轴和已完成画面，逐路运行显式指定的引擎。Neil 提取存档音轨并逐句检查 PCM。CosyVoice 用同一文案和对应的画面帧，句长基于实测 PCM。每路输出 WAV、MP4、时间轴、导演配置、SRT 和 QA。任一路失败会在 `comparison.json` 中保留原因。

实测报告记录媒体哈希、性能、SenseVoice 观测、单句重配和回退证据。 [门把手配音评测](voice-direction-evaluation.md)

## 质量检查

```sh
uv run python -m mechanical_video_next.directed_narration qa \
  output/voice-audition/timeline.json output/voice-audition/quality.json
```

技术检查测量 WAV 和 MP4 内 AAC 的响度与真峰值、句内异常低电平、句间空隙和实际时长。CosyVoice 声纹参考余弦值用于定位需要复核的句子。

`--sensevoice ASR_CONFIG.json` 可使用离线 SenseVoiceSmall INT8，配置包含 `runtime_python` 和 `model_dir`。将 `model.int8.onnx` 和 `tokens.txt` 放进模型目录，在独立 Python 环境安装 `sherpa-onnx==2.0.3` 与 NumPy。可用 `"backend": "funasr"` 选择已安装的 FunASR 环境。 [SenseVoice INT8 版本](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/tree/2365baeacb507f821a0c8120fcee3d484dba7a07)

也可通过 `--observations` 读入已核对音频哈希的外部观测。观测以句子 ID 为键，每项有 `audio_sha256`、`text` 和可选的 `phrases`，短语项含 `phrase` 与相对句首的 `offset_ms`。文本差异用于定位核听。识别短语的估计时间与动作帧的毫秒差值供最终听审核对。听感、发音、情绪贴合和声线一致性在实际回看和听审前为 `UNKNOWN`。
