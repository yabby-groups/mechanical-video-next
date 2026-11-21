# Producer 创意导演与视觉规划

新建的默认 Producer-directed 混合任务固定 `creative_direction_version=1`。现有实验和历史任务按创建时的版本继续。原生 Producer 负责创意取舍，原有角色按实际需要提供证据、资产、动画、剪辑和独立审查。没有新增调度器。

使用项目级 [`$director`](../.agents/skills/director/SKILL.md) 设计镜头并复核实际动稿，执行字段沿用下列 Blueprint 和时间轴结构。

## 从取舍到执行

1. 在研究 handoff 的 `director.treatments` 写 `mystery`、`failure_inference`、`direct_experiment` 三种本片构思。每个方案提供 `question`、`watch_reason`、`hook`、`tension`、`reveal`、`explanation`、`payoff`、`dropoff_risk`、`rhythm` 和 `evaluation`。作者在 `selected` 和 `selection_reason` 说明取舍。无真实故障来源时只用明确标注的反事实条件。
2. 将导演决策带到冻结 Blueprint。每镜的 `director` 说明对象、新信息、构图、光线、动作、转场、辅助声音和科学资产。时长仍由 Blueprint 和 30 fps 画面区间统一保存。证据、相机配置和媒体授权仍使用原有字段。
3. 每镜 `candidates` 记录制作路线、选择依据、0–4 的准确性、表现力、意图匹配、可用性与风格，以及估算时间和费用。Visual Planner 先剔除不可用或科学不合格路线，再比较准确性、呈现分和制作代价。获选制作路线要匹配已绑定的 Blender、合规影像或 Remotion 配置。没有查到可用资产时在依据中注明。CAD 是制造可检验 3D 输入的上游步骤。
4. `edits` 绑定到画面时间轴。动作匹配共用原步骤的动作时钟。J/L-cut 至少有一段实测的 Neil 音频跨过画面切点。声音预告由实际跨过该时点的音效驱动。停顿留给观察。时间压缩走原生镜头的同步 `time_map`，声明受影响时间。音效在 `sound_events` 选择动作或镜头 ID、帧偏移、提前量、时长、声源样本起点、增益和授权。合成保留原 Neil 音轨，用现有混音验证逐窗口检查遮蔽。
5. 原流程从冻结 Blueprint 编译、制作低清整片、在 `animation-manifest` 绑定实际 MP4，再由 QA 写 `preview-qa`。现在另检查整片解码、分辨率、共同帧数和核心画面变化。已记录的创意失败先修正。连续观看和听审有相应证据才能记为 PASS。保存预演后再启动正式高清。
6. 参考库可存 `shot_analysis`，逐镜保存 `time_range`、`composition`、`subject_motion`、`camera_motion`、`reveal`、`edit`、`style`，只有观察到的声音才写 `sound` 和关联的 `listening_evidence`。可迁移的 `techniques` 通过源镜头 ID 和时间码回溯，并通过既有 `reference_principles` 和 `reference_effects` 绑定到制作及对应视频。

## 表达策略

策略读取已绑定的几何、轨迹、机械约束和证据。参数写入 `director.presentation` 或沿用已实现的基础镜头字段。编译对新设置做限制，机械驱动、结构轨迹、约束和依据由基础镜头提供。颜色、镜头、透明、相对时间与说明层可单独调整。示意性策略填写 `schematic_scope`。

| 策略 | 适用条件、参数和科学边界 | 既有执行器和低成本预演 |
| --- | --- | --- |
| `macro_reveal` | 有可定位的物理细节。指定 `camera_path`、锚点和观察区。关键接触出画时修订构图。例为修正带的轮缘与环带。 | Blender 原生运动与锁定尺度构图，半分辨率预演。 |
| `transparent_cutaway` | 内部几何有来源。降低外壳 `opacity_tracks`，或指定 `section_plane`。只用作显示，避免把视觉开口解释为实际开口。例为透壳看供带轴。 | Blender 显隐或剖面，低采样预演。 |
| `exploded_view` | 装配和部件关系可信。使用 `exploded_view` 教学轨迹说清空间位置。禁止把拆解过程解释为运行行程。例为展示卷和轴的同轴套装。 | Blender 已有概念装配镜头，低清预演。 |
| `motion_tracking` | 有命名的运动部件。使用 `camera_path_follow` 或已配置的 `camera_follow` 和 camera rig。相机跟随需要保留判断位移的空间基准。例为跟压头进入纸面。 | Blender 运动跟随，低清输出并核对锚点。 |
| `force_visualization` | 力方向有证据。使用 `graphic`，量值需要来源，定性示意需要标注。例为手压方向和反力。 | Remotion 既有科学矢量或数据动画，半分辨率合成。 |
| `energy_flow` | 有证据证明输入、传递和输出。支持流程图式 `graphic`，禁止把图标速度当作能量变化。例为手推至收带。 | Remotion 科学图形和数据动画。 |
| `motion_comparison` | 两个状态使用明确且可比较的基准。数据图在同一时间或标注各自条件。例为等带长、不同半径对应不同角位移。 | Remotion 现有角位移或卷尺转速比较。 |
| `mechanism_isolation` | 已掌握部件和相邻传动关系。通过 `visible_parts` 或透明度聚焦，不隐去观众判断接触所需的基准。例为单独显示供带轴和环带。 | Blender 局部 3D 与预演。 |
| `failure_vs_success` | 有真实失败证据，或明确是理想比较。用 `graphic` 指出哪个条件改变。例为固定传动与可滑移条件。 | Remotion 支持变化数据预演。 |
| `hidden_mechanism_reveal` | 遮挡部件在同一已验证装配内。用视角揭示、透明或剖切逐步引导。例为先看到机构位置，再靠近轮缘。 | Blender 共享原生场景的镜头或显隐。 |
| `slow_motion_detail` | 需要观察的源动作完整且动画有足够采样。使用单调的屏幕至源时间映射，不把变速用于推断实际角速度。例为延长接触窗口。 | Blender `time_map` 保持同一源轨迹，低清测节奏。 |
| `scale_transition` | 大小视角可共享空间锚点。通过相机路径或锚点构图保持方位。例为从辨识轮辐推进到轮缘接触。 | Blender 相机及剪辑时间轴，半分辨率预演。 |

当前修正带验证片直接使用相机适配器、原生素材复用、实测 Neil 和拟音，以及同一个 Remotion 渲染器。另有 Remotion 等带长对照和 2.5D 辅助片段。2.5D 使用 `uv run python scripts/layered.py PROGRAM OUTPUT` 预渲染带有 `mechanical_role: support` 的 `render_route: 2.5d` 图层程序，以 `layered_animation` 候选进入已有的授权视频适配器。它绑定 `layered_receipt`、原始图层、视频、渲染检查和许可，在 Blueprint 说明示意边界。外部实拍和其他选题的完整制作尚需实际验证。修正带对照使用复用脚本交付，另一次实际预演走常规 Blueprint 编译与合成。默认立项、handoff 和 stage 的衔接由回归测试验证。
