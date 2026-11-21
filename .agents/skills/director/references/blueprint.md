# 导演决策如何进入现有制作

| 导演要交付的决定 | 现有字段与执行 |
| --- | --- |
| 观众最先看见什么，为什么看下去，发现和兑现在哪里 | 研究 handoff 的 `audience_decision` 和任务已固定的 `director.treatments`。用 `core_question`、`knowledge_ids`、`narrative.moments` 指向实际镜头与画面帧区间。 |
| 对象动作、取景、可见起止状态和光线 | `shots[].director` 的 `narrative_purpose`、`new_information`、`framing`、`camera_position`、`camera_movement`、`object_movement`、`reveal_strategy`、`lighting_style`。用 `visual_focus`、`visual_action`、`evidence` 及适用的 `progression.observable` 明示实际状态和对应知识。 |
| 运镜及核心证据窗口 | 从 Blender 基础镜头的模型、驱动和约束出发。`camera` 描述视角，`director.presentation` 传入 `camera_path`、`camera_framing`、`anchors`、`observation_window` 等既有参数。用 render checks 检查锚点与约束，在实际画面核对遮挡。 |
| 选择 3D、补充实拍或信息图 | `director.candidates` 由现有 Visual Planner 判断证据和执行可行性。`render_engine`、`mechanical_role`、`matching` 和 `license` 记录选择。`motion_comparison` 可将同条件的角位移示意编译成 Remotion 的 `angular_comparison`。 |
| 剪辑、声音和停留 | `timeline.shots` 使用 30 fps 半开帧区间和 `source_start_frame`，`director.edits` 记录切换理由。跨镜保持共同动作时钟，J/L-cut 对照实测 Neil；声音使用已有 `sound_events`，所有机械参与者用同一运动时钟。 |
| 动稿到修订 | 静态 Animatic 适合排查顺序、时长和文字占位。动作、运镜和声画在低清移动工作片上检查；将发现写入现有 `preview-qa` 的对应时间段和镜头，正式版看实际导出文件并走独立 QA。 |

用 `uv run python -m mechanical_video_next.blueprint compile --blueprint BLUEPRINT --base BASE --output CONFIG` 编译。操作前可运行同入口的 `--help` 核对命令。未冻结的实验件使用 `--draft`。编译结果使用现有 3D/编辑阶段、Blender 镜头渲染缓存和 Remotion 合成。FFmpeg 负责媒体检查、剪辑对照和编码。机械 motion tracks、动作驱动和具体实施依据留在原有绑定中，运镜修订只触及所需的摄影配置。对比版本优先复用原旁白和音效声轨。
