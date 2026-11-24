# Mechanical Video Next

「君哥拆机器」的机械拆解与工作原理科普视频生产工具。

从选题出发，查清具体型号的结构与动作，联合编写旁白、分镜和三维动画，再完成配音、字幕、剪辑和混音。新片按 [制作契约](docs/production-contract.md) 制作及检查。

## 生产一集

安装已锁定的 Python 和 Remotion 依赖。机器需要 Blender、FFmpeg、FFprobe 和现有 Remotion 渲染器使用的 Chrome。Neil 配音读取环境变量或通过 `--env-file` 指定本地凭据文件，格式见 `.env.example`。

```sh
uv sync --locked
npm ci --prefix remotion --no-audit --no-fund
uv run python -m mechanical_video_next produce --episode productions/jotter
```

示例是派克乔特圆珠笔。按 [本集源文件](productions/jotter) 编排每集。将 `narration.txt` 以空行分镜、每行一条字幕。 `edit.json` 指定配乐、镜头留白、标注和拟音时点。 `scene.py` 使用 Blender，接收 `--timing` 帧数列表、`--shot` 镜头序号和 `--directory` 输出目录。也可以用现有 CAD 或 EAS 制作场景源。

成片和字幕输出至 `output/<本集目录名>/`。可用 `--work-dir` 指定逐镜头缓存来复用渲染结果，默认工作目录随运行清理。模型、已完成视频与生产缓存按 [配置边界](config/README.md) 保存。CAD 工具可用 `uv sync --extra cad --locked` 安装。

## 导演式配音

按剧情段落编排情绪、重音和留白，用联合时间轴放置逐句实测音频。CosyVoice 3.0 是显式启用的导演式引擎。Audiogen Neil 继续作为正式制作默认和整轨回退引擎。支持复用原句调整时间轴、重配单句及使用 SenseVoiceSmall 定位发音复核点。 [导演式配音](docs/voice-direction.md)

## 恢复已有账本任务

```sh
uv run python -m mechanical_video_next produce --resume output/tasks/TASK
uv run python -m mechanical_video_next status output/tasks/TASK
```

已有账本和本地材料按 [历史制作契约](docs/history/production-contract-20261124.md) 恢复。历史阶段及底层工具仍服务于这些任务。

## 许可证

本项目新 Python 和 TypeScript 为 GPL-3.0-or-later，原创教学内容为 CC0-1.0。上游及外部资产采用各自的许可证。EAS 来源见 `blender/vendor/SOURCES.json`，Remotion 许可见 `remotion/UPSTREAM-LICENSE.md`。
