# Mechanical Video Next

Codex 主线程直接编排 `.agents/skills/` 中的三个 Skills。先读 README.md、视频配置和资产来源；禁止迁移旧项目架构、多 Agent 平台、通用 CAD 或几何求解器、AI 审核评分模型。

先验证资产、关键帧和当前片段，再做低清全片与正式输出。优先 `scripts/produce.py` 和已固定版本的 EAS，不为每条视频另写场景脚本。工作原理镜头必须有数学或素材依据，简化齿廓始终标注“原理示意”。技术检查通过不代表科学、听感或视觉完整验收。

缓存依据内容与配置，不依据文件名猜测；配音字幕不进入 3D 缓存键。work 预算 2 GiB，空闲盘小于 3 GiB 停止生成。只删除本次生成且已编码验证的 PNG；其他清理由 `scripts/clean.py` 明确执行。assets 与 output 不得自动删除。

失败即停，不自发重试。按证据修复时，每问题最多两种不同策略、每策略最多两次；没有可测改善即停。每次运行保存耗时、缓存命中和临时空间采样，人工介入与工程开发修改分别统计。

## CodeGraph

若当前会话暴露 `codegraph_*`，结构问题优先 `codegraph_context`，再一次 `codegraph_explore`；符号定义用 `codegraph_search`，调用、影响、文件结构分别用相应图工具。不重复 grep 已由图确认的结构。字面文本用 rg。服务器返回 not initialized 时，询问用户是否运行 `codegraph init -i`。当前创建会话未提供该 MCP 的调用工具，不假装已检索或初始化。

## ego-browser execution

使用 ego-browser 前阅读其 Skill；执行路径 `/Users/lmj/.local/bin/ego-browser`，JavaScript 使用 `nodejs -e`。不使用 heredoc、herestring、bash -lc 或 zsh -lc 包装，不改 Codex 沙箱配置。现有 ExecPolicy 已允许时不额外请求提权。
