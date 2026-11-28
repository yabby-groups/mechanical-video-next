# Mechanical Video Next

「君哥拆机器」的机械拆解与工作原理科普视频生产工具。

从选题出发，查清具体型号的结构与动作，联合编写旁白、分镜和动画，再完成配音、字幕、剪辑和混音。新片以原创三维机械画面为主，按知识表达需要使用二维和分层动画。 [制作契约](docs/production-contract.md)

## 生产一集

安装已锁定的 Python 和 Remotion 依赖。机器需要 Blender、FFmpeg、FFprobe 和现有 Remotion 渲染器使用的 Chrome。Neil 配音读取环境变量或通过 `--env-file` 指定本地凭据文件，格式见 `.env.example`。

```sh
uv sync --locked
npm ci --prefix remotion --no-audit --no-fund
uv run python -m mechanical_video_next produce --episode productions/mx-blue-switch --work-dir work/mx-blue-switch
```

青轴示例从白色滑块突跳切入，继续追声源、触点、回位、红轴对比及触发行程。用剪辑 JSON 的 `timeline` 引入联合时间轴。画面切点、逐句 Neil 配音、机械动作源及拟音各用自己的区间。`creative` 存放选题、研究、运营证据与创意取舍，`pacing` 记录镜头给观众的新发现。历史剪辑仍可将旁白按空行分镜、每行一条字幕。 [示例时间轴](productions/mx-blue-switch/timeline.json)

正式入口在渲染前检查实测时间轴，导出后复核画面流。默认至少 60 秒，常规参考 120–180 秒，知识丰富的复杂题材参考 180–300 秒。动稿可短于 60 秒，用户明确要求超短成片时使用 `--allow-short`。

成片和字幕输出至 `output/<本集目录名>/`。可用 `--work-dir` 指定逐镜头缓存来复用渲染结果，有 `creative` 的新片默认将预演和缓存保存在 `work/<本集目录名>/episode/`，历史剪辑未指定时用临时工作目录。模型、已完成视频与生产缓存按 [配置边界](config/README.md) 保存。CAD 工具可用 `uv sync --extra cad --locked` 安装。

首轮生成全长动态预演及其手机预览。Producer 查看实际视频和音轨，在工作目录的 `preview/audience-review.json` 记录同一个 MP4 哈希、前 2 秒、前 5 秒、全片推进及问题复查。按实际覆盖写观察，连续视听缺证时记 UNKNOWN。修复后复查受影响区间和连接，再跑相同命令进入高清。 [动稿记录样例](productions/mx-blue-switch/preview-review.json)

## 发布后运营复盘

使用 `uv run --locked python -m mechanical_video_next.feedback --input observations.json --output cohorts.json --cohorts` 汇总真实记录。输入为 JSON 列表，每条代表一个作品在一个平台及一个时刻的快照。使用 `platform`、`account_id`、`video_id`、带时区的 `published_at` 和 `observed_at` 匹配，给 `selection_domain` 写领域和依据。累计快照和同龄窗口分别输出，缺失指标保留空值及样本量。历史记录可只附实际现存的运营证据。本机私有数据保存在仓库外或忽略目录。Producer 从相关复盘选择证据，将其定位、影响和发布验证方式记入本集 `creative.operations`。

## 比较动稿并局部换镜

从已核实的机械现象选第一帧。复用原场景和缓存，在低成本动稿里比较可见的机械关系、最早能看懂的答案，以及什么时候能看出本集和系列的价值。根据实际表达选择要预演的镜头数。

```sh
uv run python -m mechanical_video_next produce --episode productions/drawer-slide --edit growth-edit.json --work-dir work/drawer-slide/episode --preview-shots 1
uv run python -m mechanical_video_next opening-analysis "开场动稿.mp4" --clips work/opening --through 12 --phone-preview work/opening --output work/opening/analysis.json
```

备选剪辑 JSON 可指定 `narration`。逐镜可用 `scene` 换 Blender 脚本、`scene_shot` 选用源脚本的镜号、`scene_inputs` 声明影响画面的相对路径依赖。场景接收 `--preview` 时按固定间隔输出低分辨率帧，默认每 5 帧采样，必要时用 `preview_step` 与场景约定匹配。相同工作目录优先复用已有高清镜头，预演的剪辑文件单独写入 `preview/`。新片省略 `--preview-shots` 时进入全片预演及复查流程。旧剪辑可按原方式省略该参数渲染成片。

解释镜头可在 `shots[]` 写入 `graphic`，使用现有 Remotion 的 `diagram`、`comparison`、`chart`、`timeline` 或 `data_animation`。动态图的关键帧时间以本镜秒数为基准。联合剪辑按预定的画面区间渲染图解，连续旁白可跨越图解切点。图解按参数、镜长及 Remotion 源文件复用缓存，同时支持 Remotion 和 FFmpeg 剪辑。

联合时间轴以 30 fps 的半开帧区间编排画面和动作。画面 `source_start_frame` 选原速源区间，Blender 镜头用剪辑的 `source_frames` 保留完整动作源，`crop` 可按相同画幅提取局部。逐句 `start_frame` 和 `deadline_frame` 留出语音空间，实测语音采样位置决定字幕区间。跨切点的同一动作通过 `action_views` 保持动作时钟，换源相机时核对重叠源帧的共同机械通道。需要拟音时用 `sounds` 绑定动作、可见事件和独立求值的状态变化。将作用于完整源动作的核证规则放在 `source_events`，保留原来的事件顺序和保持时长。

局部剪辑可为单镜指定 `picture` 的 `path`、`sha256` 和可选 `start_frame`。路径相对本集目录，按原速截取 1080p30 源画面，可引用已有三维镜头、SVG 动画的导出视频或分层动画。用 `uv run python scripts/layered.py PROGRAM OUTPUT` 导出分层源，节目配置填写 `mechanical_role: "support"`。随本集保留了该镜头的 Blender 场景源时，可以用 `"fallback_to_scene": true` 在原速缓存缺失时重渲染。可选 `frames` 固定画面长度，保留足够的实测语音时长与尾部留白。`"composition": "ffmpeg"` 使用同一时间轴合成字幕、部件标注和实测配音。

`opening-analysis` 绑定 MP4 SHA-256，定位默认音轨和字幕流，导出 2、5、10 秒及 `--through` 指定区间。`--phone-preview` 另存全长 384 像素宽的原速 MP4，保留默认音轨和已有字幕，报告记录预览分辨率和文件哈希。高清制作前用它检查主体、接触、状态对照和字幕。用 `--sha256` 核对版本，用 `--review` 导入同一 MP4 的带时码观察。手动 `audience-review` 检查前段知识、首个潜在赞评关及整片兑现。旧账本的 `python -m mechanical_video_next.growth_report` 可引用与该版本绑定的 `opening-review*.json`。 [活动扳手与摆头削皮器的画面验证](docs/productions/visual-expression-validation-20261126.md)

在 `knowledge_progression.evidence` 记录原片时间区间和可见依据。`opportunities` 用 `kind`、证据下标 `evidence` 和 `reason` 记录潜在赞、评、藏、关。`takeaways` 沿用证据下标和理由，可记录获得感 `gain`、惊喜感 `surprise`、表达力 `expression`、感染力 `resonance`、后段发现 `later_discovery`、删减 `over_trimmed`、无效延长 `padding` 和正式时长 `formal_duration_fit`。原有知识、实用、丰富度、总结、系列和收藏字段仍可用，缺少依据时写 `UNKNOWN`。 [发布后复盘模板](docs/douyin-post-review.md) · [滑轨和滚轮回归](docs/productions/audience-growth-regression.md) · [水龙头开场回归](docs/productions/faucet-opening-retention-regression.md)

## 导演式配音

按剧情段落编排情绪、重音和留白，用联合时间轴放置逐句实测音频。CosyVoice 3.0 是显式启用的导演式引擎。Audiogen Neil 继续作为正式制作默认和整轨回退引擎。支持复用原句调整时间轴、重配单句及使用 SenseVoiceSmall 定位发音复核点。 [导演式配音](docs/voice-direction.md)

在使用 `timeline` 的剪辑中，可用 `voice_direction` 引用本集的逐句导演方案。镜头改切后按句子起点更新所属画面，配音缓存继续按语音内容和合成参数复用。

## 恢复已有账本任务

```sh
uv run python -m mechanical_video_next produce --resume output/tasks/TASK
uv run python -m mechanical_video_next status output/tasks/TASK
```

已有账本和本地材料按 [历史制作契约](docs/history/production-contract-20261124.md) 恢复。历史阶段及底层工具仍服务于这些任务。

## 许可证

本项目新 Python 和 TypeScript 为 GPL-3.0-or-later，原创教学内容为 CC0-1.0。上游及外部资产采用各自的许可证。EAS 来源见 `blender/vendor/SOURCES.json`，Remotion 许可见 `remotion/UPSTREAM-LICENSE.md`。
