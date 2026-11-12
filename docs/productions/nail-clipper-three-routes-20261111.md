# 指甲刀三路线实测

本次已实际生成 `output/nail-clipper/2d/final.mp4`、`2_5d/final.mp4`、`3d/final.mp4`，每条38.2秒、1920×1080、30fps、1146帧，含原创开场、结尾、默认Neil旁白与字幕。三路解码后的旁白PCM哈希一致。`compare.mp4` 为1080×1920、30fps、有声三格同步对比，另有 `preview.jpg` 与 `report.json`。

2D是动态正投影机构图解；2.5D包含挤出分层、深度投影、阴影、剖示和轻微相机变化；3D使用自主build123d/OpenCASCADE四实体装配、EAS与EEVEE，包含刀体弯曲、压柄/凸轮/销传力、拆解回装与Boolean纵剖。尺寸和变形为明确标记的教学近似，不是制造设计或材料接触仿真。

CAD保留v3/v4失败，v5的17姿态原生实体采样未测得体积交集。实际Blender播放曾出现shape-key叠加：错误最大约12.846mm；修复浮点关键帧与插值后，有限帧逐顶点误差约2.328e-10m，检查已接入。所有历史报告和失败候选在shared中保留。

四个MP4均通过完整错误中止解码。独立QA实际取样复验了三路及对比片，8项取样缺陷有修复证据；连续观看、听审、精确音画同步、完整科学接受和低粉爆款核验仍未完成，因此状态为 `TECHNICAL_PASS_UNACCEPTED_COMPARISON`，不是COMPLETED。参考研究检查了10个真实页面及部分画面，没有冒称完整观看10条。

原生1080p的六个3D镜头工具阶段共1122.273秒；总历时包含研究、开发、等待及修复，见report实时记录。整次修复次数、人工介入、Token和费用无完整计量，保持null；已观测事件、缓存复用与已修缺陷另列。159项工程测试通过；后续状态/哈希补丁的14项定向测试通过。技术检查不代替感官或科学验收。

当前会话的恢复验证使用既有真实CAD和配音缓存：

```sh
UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python -m mechanical_video_next route-run output/tasks/nail-clipper-three-routes-20261111 --plan output/nail-clipper/shared/resume-render-plan.json
```

实测重跑5个制作步骤全部命中，无CAD、TTS或Blender重生成。新的指甲刀任务使用已跟踪的 `config/nail-clipper-three-routes-plan.json`；先由当前Producer完成真实研究，再运行计划。其他机械题目需要Producer准备自己的研究、CAD与计划，不能把本题适配器当作任意名称现成生成器。没有启动第二个Producer或常驻服务，没有上传或发布。
