# Mechanical Video Next

制作「生活中的知识与科学原理」原创横屏科普。当前 Codex 主会话作为唯一
Producer，从生活现象和科学问题出发，按题材选用真实影像、原创动画、
信息图或三维制作，沿用独立 QA。

**有效规则从 [生产契约](docs/production-contract.md) 开始。** 新建 topic-only
任务默认使用 `science-story-v3`、媒体策略 1、视觉策略 2。
逐镜头规划真实因果、原创科学/信息动画和合法补充素材；核心机械证据须为
可核验原生 3D 或独立核实且获许可的真实机构影像。混合成片使用完整媒体
来源清单，原生 3D 段保留自己的来源链。历史 3D-only 任务不自动升级。

本仓库提供可恢复的确定性工具和原生 Agent 指令。名称入口建立任务，由
当前 Producer 继续推理和执行；它不是后台智能服务。任意选题都能自动
交付合格全片尚未获得验证，实际三级验收结果见
[本次生产报告](docs/productions/workflow-upgrade-20261118.md)。

```sh
uv sync --locked
npm ci --prefix remotion --cache work/npm-cache --no-audit --no-fund
uv run python -m mechanical_video_next produce --topic '某个现象为什么会这样？' --routes 3d
uv run python -m mechanical_video_next produce --resume output/tasks/TASK
uv run python -m mechanical_video_next continue output/tasks/TASK
```

影片长度由完整的视听故事决定。正式交付使用 1920×1080/30fps、H.264/AAC、
单行字幕、3:4/4:3 封面及来源、QA 和生产报告。独立创意评审通过后才进入
正式渲染。没有视听能力时保留 UNKNOWN 和可复查的动态样片。不得注水、加速塞词、
以静态卡替代动作、复制其他作者的独创脚本或完整镜头安排。禁止自动发布。

`task.json` 是任务、版本、状态和交付的账本；研究保存精简 `science.facts`，
Blueprint 保存原创叙事与逐镜头 `direction`、知识和素材决策。编译配置是
有哈希绑定的派生数据；Handoff 保存不可变版本和依赖。没有第二个调度系统。

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
