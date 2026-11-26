# Mechanical Video Next

本项目为「君哥拆机器」制作可以直接发布的机械拆解与原理科普视频。以实际成片作为交付。新片使用 [制作契约](docs/production-contract.md)。恢复已有账本任务时，查阅其已固定的 [历史制作契约](docs/history/production-contract-20261124.md)。

围绕用户指定的对象核实具体型号，把通俗旁白、镜头和机械动作一起设计。优先复用合格资产，按需使用 CAD 和 Blender。用 Neil、Remotion 和 FFmpeg 完成 1080p 横屏成片。当前会话负责从选题到交付，只有独立工作确有生产价值时才分工。

选题时同时看日常识别度、隐藏机构的可见知识收益和系列潜力。从有依据的原理、设计原因、结构比较、生活实用知识和隐藏发现中选择内容。沿用 Director 和 `opening-analysis`，用低成本动稿检查第一眼、前五秒的首次知识、前十秒的知识和系列价值，以及最早自然引发讨论的画面。后段用新知识推进，给出可复述的总结。将取舍落实到旁白、画面和切点，复用未变的镜头。各时间点用于比较，前两秒修改建议单独保留。用已核实的双平台复盘更新下一题的创作假设。

在实际成片上检查科学与机械正确性、原创与许可、字幕和音画质量。具备视听能力时完整观看和听审。缺少实际观察时说明覆盖范围，并将技术合格的成片交给用户确认。已生成的视频、模型、资产和用户修改须保留。只清理确认可再生的本次中间文件。

Python 使用 `uv run`，CAD 使用 `uv run --extra cad`，Blender 使用嵌入式 Python。Blender 通过已有 `work/production.lock` 串行运行。用 `mechanical_video_next.qa_images` 提取适合检查的压缩画面。

## CodeGraph

结构问题优先使用已配置的 CodeGraph，字面文本使用 rg。索引缺失时按工作区的 CodeGraph 操作说明处理。

## ego-browser

先阅读其 Skill。运行 `/Users/lmj/.local/bin/ego-browser`，JavaScript 使用 `nodejs -e`。浏览器命令保持现有沙箱配置，直接运行对应程序。
