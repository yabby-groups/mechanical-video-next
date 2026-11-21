# Mechanical Video Next

Mechanical Video Next 是「君哥拆机器」抖音账号的专属视频生产系统。

> 拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。

当前 Codex 主会话是唯一 Producer。从机器、工具、机械装置、结构和生活用品发掘
设计故事，追问它为何被发明、为何如此设计、有哪些取舍，以及怎样演变和改进。
科学原理通过具体机械设计、测量仪器或实际应用进入叙事。默认独立选题聚焦机械。

**有效规则从 [生产契约](docs/production-contract.md) 开始。** 新建 topic-only
混合任务默认由 Producer 负责研究和整片导演，沿用 v6 的技术能力。先决定有依据
的完整故事，再定实施例、画面、素材和旁白。三维拆解、剖视和运动是核心视觉能力。
实际使用、历史上下文和比较可用合规实拍或原创信息动画。核心机械证据使用可核验
原生 3D，或获许可且经独立连续观察的真实机构影像。混合成片保留完整媒体来源链，
历史任务继续适用其立项版本。

本仓库提供可恢复的确定性工具和原生 Agent 指令。主题入口建账并生成派工，
由当前 Producer 完成研究取舍和后续制作。实际三级验收结果见
[历史生产报告](docs/productions/workflow-upgrade-20261118.md)。

```sh
uv sync --locked
npm ci --prefix remotion --cache work/npm-cache --no-audit --no-fund
uv run python -m mechanical_video_next produce --topic '雨伞'
uv run python -m mechanical_video_next produce --resume output/tasks/TASK
uv run python -m mechanical_video_next continue output/tasks/TASK
```

影片长度由完整的视听故事决定。正式交付使用 1920×1080/30fps、H.264/AAC、
单行字幕、3:4/4:3 封面及来源、QA 和生产报告。Producer 用低清整片检查剪辑，
独立 QA 验证最终成片。没有视听能力时保留 UNKNOWN 和可复查的动态样片。不得注水、加速塞词、
以静态卡替代动作、复制其他作者的独创脚本或完整镜头安排。禁止自动发布。

`task.json` 是任务、版本、状态和交付的账本；研究保存精简 `science.facts`，
Blueprint 保存原创叙事、镜头、知识和素材决策。编译配置是
有哈希绑定的派生数据；Handoff 保存不可变版本和依赖。没有第二个调度系统。

默认 Producer-directed 任务的创意选案、逐镜视觉规划、动作和声音时点沿用同一
Blueprint 与时间轴。字段、视觉策略和预演检查见 [创意导演与视觉规划](docs/creative-direction.md)。

```sh
uv run python -m mechanical_video_next.reference_library search --query '选题'
uv run python -m mechanical_video_next.blueprint compile --blueprint BLUEPRINT --base BASE --output CONFIG
uv run python -m mechanical_video_next handoff output/tasks/TASK --role Research --name research --input RESEARCH
uv run python -m mechanical_video_next stage output/tasks/TASK keys --config CONFIG
uv run python -m mechanical_video_next status output/tasks/TASK
```

Stage 执行适用的研究、装配、机械、内容和动态分镜门禁；命令示例不授予
绕过依赖的权限。QA 独立检查真实 MP4/音频及完整关键动作，不能以测试、
截图、响度或 ASR 代替实际观看/听审。正式交付需所有实际文件和独立验收。

科学镜头支持同源相机与跟随、剖切、隔离、轨迹、概念场线、状态驱动、
共享时间映射、透明度和柔性带材轨道；不是通用物理求解器。
Remotion 支持图表、公式、数据关键帧、双素材分屏、跟随标签和同源放大，
来源、实际区间、许可证和合成输入均绑定哈希。镜头语言、色彩和材质服务本集的科学问题。

声称镜头改进的版本须比较实际 MP4 对应区间：

```sh
uv run python -m mechanical_video_next.media_revision BEFORE.mp4 AFTER.mp4 --changes changes.json --output revision.json
```

`changes.json` 为数组，每项包含 shot_id、defect_key、knowledge_target、
previous_range、current_range（秒）。工具逐帧比较解码画面，拒绝仅改名、
元数据或重编码造成的“升级”；像素变化仍需独立 QA 判断是否解决目标缺陷。

所有 Python 通过 `uv run`，项目固定 Python 3.14.2；CAD 用
`uv sync --extra cad --locked` / `uv run --extra cad cad run MODEL.py`。
沙箱缓存可设 `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache`。
Blender 保持全局串行锁、逐镜头内容缓存与 FFmpeg 分块编码。work ≤2 GiB，
空闲磁盘 ≥3 GiB；仅经现有 clean 工具清理验证过的可再生数据，不删资产、
历史成果或失败证据。配音/字幕修改不重建 CAD，标注/图表修改只重合成。

```sh
uv run python -m unittest discover -s tests -v
npm run --prefix remotion typecheck
uv run python scripts/clean.py --older-hours 168
```

详细接口：[科学镜头](docs/science-production.md)、[视觉分镜](docs/visual-narrative.md)、
[素材与版权](docs/asset-first-media.md)、[研究证据](docs/reference-first-contract.md)、
[理解 QA](docs/product-comprehension-contract.md)、[长片/音频](docs/longform-contract.md)、
[封面](docs/cover-delivery.md)、[模型路由](docs/agent-dispatch-efficiency.md)。
旧 README、AGENTS、Skill 和角色原文见 [规则归并前档案](docs/history/production-instructions-20261118/README.md)，
仅用于解释历史任务，不覆盖当前契约。单片源文件/配置/媒体和报告留本地，
公共仓库边界见 [config/README.md](config/README.md)。

本项目新 Python/TypeScript 为 GPL-3.0-or-later，原创教学内容为 CC0-1.0；
上游及外部资产保持其自身许可证。EAS 固定来源见 blender/vendor/SOURCES.json，
Remotion 许可见 remotion/UPSTREAM-LICENSE.md；使用资格需按实际组织核实。
