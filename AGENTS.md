# Mechanical Video Next

视觉方向固定参照用户明确指定的**打印机系列 EP03**，来源与哈希见 `config/visual-reference.json`。当前配置使用全画面机械主体、灰色摄影棚空间、金属材质与柔和阴影、斜视及克制推进、少量标注和字幕。沿用现有 EAS 与 EEVEE 预设，不恢复右侧说明栏。视觉参考的选择不自动改变已选 Neil 配音或当前横屏画幅；新片仍需检查实际关键帧与媒体。

Codex 主线程作为唯一 Producer，使用真实 Codex 子代理协作并编排 `.agents/skills/` 中的三个 Skills。先读 README.md、视频配置和资产来源；禁止迁移旧项目复杂架构、通用 CAD 或几何求解器、AI 审核评分模型。

先验证资产、关键帧和当前片段，再做低清全片与正式输出。优先 `scripts/produce.py` 和已固定版本的 EAS，不为每条视频另写场景脚本。工作原理镜头必须有数学或素材依据，简化齿廓始终标注“原理示意”。技术检查通过不代表科学、听感或视觉完整验收。

缓存依据内容与配置，不依据文件名猜测；配音字幕不进入 3D 缓存键。work 预算 2 GiB，空闲盘小于 3 GiB 停止生成。只删除本次生成且已编码验证的 PNG；其他清理由 `scripts/clean.py` 明确执行。assets 与 output 不得自动删除。

失败即停，不自发重试。按证据修复时，每问题最多两种不同策略、每策略最多两次；没有可测改善即停。每次运行保存耗时、缓存命中和临时空间采样，人工介入与工程开发修改分别统计。

## Production protocol

收到制作请求时，由当前主会话作为 Producer，先用 `python3 -m mechanical_video_next produce` 创建任务。Python 仅执行确定性工具和校验，不创建伪 Agent。需要外部启动时显式 `--codex` 启动 Codex 入口；已在 Codex 会话内不要再启动第二个 Producer。

最多同时工作 3 个子代理。工具支持时默认 `fork_turns="none"`，只传角色指令路径、任务路径、输入版本与所需输出，不复制整个工程讨论或此前媒体。Research 与 Asset 并行；各自只读必要资料，写自己的 JSON。Research 固定事实和脚本后不重复研究。Asset 必须核查实际模型、独立零件、许可；不合格时 BLOCKED，不能生成虚构复杂结构。Animation 等待两者合格，使用 mechanical-animation；Editor 使用 mechanical-video，可先准备 TTS，最终合成必须等待镜头时间轴。QA 为独立子代理，只写报告，不改生产代码。

角色定义见 `.codex/agents/*.toml`；当前会话未热加载角色配置时，将对应角色指令直接传给原生 spawn 工具并记录此限制。不要以普通进程模拟子代理。所有交接使用 `handoff` 命令保存不可变版本、内容和依赖 SHA256；修改输出创建新版本，不覆盖其他角色产物。Producer 通过 `advance` 执行状态门禁，不能以退出码零替代质量验收。

Blender 重任务通过 `stage` 串行全局锁执行。QA 必须读取实际预览/成片证据，记录媒体 SHA256、取样时间、能力和覆盖范围。每项检查 PASS / FAIL / UNKNOWN；无听审能力不得以响度或 ASR 替代听审，无连续视频能力不得以截图代替完整观看。UNKNOWN 阻止 COMPLETED；保留技术通过但未完全验收的媒体。

每个缺陷必须包含 issue_id、severity、shot_id、time_range、evidence、responsible_agent、suggested_fix、verification_method。结构错误先换合格资产；拆解方向只改当前镜头；遮挡先用已有相机模板；字幕只合成；语音只改对应片段；运动错误回到约束校验。修复先记录基线，再登记策略和可测结果，每问题最多两策略各两轮，无改善停止。只有已有且有事实依据的 2.5D/2D 路线才可降级，不凭空宣称支持。

Token、花费、人工介入缺少运行时计量时填 null，不能填零冒充观测。保留原生子代理 ID 和启动/完成事件；不复制大图或完整历史进入每次上下文。单 Agent 回退保留 `scripts/produce.py`。不得上传、发布、保存平台草稿。

## CodeGraph

若当前会话暴露 `codegraph_*`，结构问题优先 `codegraph_context`，再一次 `codegraph_explore`；符号定义用 `codegraph_search`，调用、影响、文件结构分别用相应图工具。不重复 grep 已由图确认的结构。字面文本用 rg。服务器返回 not initialized 时，询问用户是否运行 `codegraph init -i`。当前创建会话未提供该 MCP 的调用工具，不假装已检索或初始化。

## ego-browser execution

使用 ego-browser 前阅读其 Skill；执行路径 `/Users/lmj/.local/bin/ego-browser`，JavaScript 使用 `nodejs -e`。不使用 heredoc、herestring、bash -lc 或 zsh -lc 包装，不改 Codex 沙箱配置。现有 ExecPolicy 已允许时不额外请求提权。
