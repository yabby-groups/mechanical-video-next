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

## 比较动稿并局部换镜

从已核实的机械现象选第一帧。复用原场景和缓存，在低成本动稿里比较可见的机械关系、最早能看懂的答案，以及什么时候能看出本集和系列的价值。根据实际表达选择要预演的镜头数。

```sh
uv run python -m mechanical_video_next produce --episode productions/drawer-slide --edit growth-edit.json --work-dir work/drawer-slide/episode --preview-shots 1
uv run python -m mechanical_video_next opening-analysis "开场动稿.mp4" --clips work/opening --through 12 --output work/opening/analysis.json
```

备选剪辑 JSON 可指定 `narration`。逐镜可用 `scene` 换 Blender 脚本、`scene_shot` 选用源脚本的镜号、`scene_inputs` 声明影响画面的相对路径依赖。场景接收 `--preview` 时按固定间隔输出低分辨率帧，默认每 5 帧采样，必要时用 `preview_step` 与场景约定匹配。相同工作目录优先复用已有高清镜头，预演的剪辑文件单独写入 `preview/`。选定后省略 `--preview-shots` 渲染完整成片。

`opening-analysis` 绑定 MP4 SHA-256，定位默认音轨和字幕流，导出 2、5、10 秒及 `--through` 指定区间。用 `--sha256` 核对版本，用 `--review` 导入同一 MP4 的带时码观察。手动 `audience-review` 从前两秒检查到首个潜在点赞和关注点，再核对后段知识推进。旧账本的 `python -m mechanical_video_next.growth_report` 可引用与该版本绑定的 `opening-review*.json`。 [滑轨和滚轮回归](docs/productions/audience-growth-regression.md) · [水龙头开场回归](docs/productions/faucet-opening-retention-regression.md)

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
