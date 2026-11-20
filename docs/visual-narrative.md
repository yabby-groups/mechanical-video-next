# 视觉叙事制作策略

## 知识递进与可观察证据

新立项的策略 2 任务默认执行 `knowledge_progression_version=1`，标记随任务、Blueprint、执行配置和来源回放清单绑定。已定版任务沿用立项时的策略。不要根据镜头数或字幕改动评估视觉增量。

- 在 `progression.previous_ids` 列出上一镜解释的知识，在 `knowledge_ids` 声明本镜回答的问题。本镜应引入新事实，或用新的可观察证据加深原结论。把只复述已解释内容的画面合并或移除。
- 每项 `progression.observable` 给出 `knowledge_id`、`kind`、`proof`、局部 30 fps 半开 `frames` 和可观察的 `states`。结构可以用可见几何。变化、因果和对比至少要展示两个不同状态及中间运动，核心机构仍须使用实际 3D。流程标题依次出现只适合作索引。动态对照可用 `angular_comparison` 的半径和等弧长参数，或有来源的数据图。
- 编译检查全片的重复知识、重复状态、重复构图和没有绑定观察目标的帧。若必须复用构图来保持比较基准，在现有内容 QA 说明理由和对应增量。剪辑以动作所需观察时间为准。
- 信息图用固定高对比配色、86 px 主体字和 96 px 标题，在 1920 px 视频宽度等比缩放至 360 px 后约为 16.1 和 18 px。预检包含实际字体测宽。媒体 QA 抽查 360、390、430 px 的原成片帧，绑定各尺寸的压缩图及对应哈希。
- 在现有 animatic、preview 和 final QA 的 `visual_evidence[shot_id]` 中记录实际 `media_sha256` 和逐项 `observations`。每项须有相同 `knowledge_id`、成片绝对 `frames`、`method`、`status` 和 `observation`。动态图的观察只有完整连续观看可以记 PASS。信息图另填 `phone_readability`，提供三种宽度及可复查图像的路径和 SHA256。

## 策略版本

新建选题使用 `visual_policy_version=2`。任务账本、冻结 Blueprint、执行配置和成片来源清单必须一致。旧任务及显式 `--visual-policy 1` 保留整条时间线的 3D-only 约束。使用 `--resume` 继续原策略。两版均沿用原有 `3d` 制作入口、角色、锁、磁盘预算、Neil 与验收流程。

| 环节 | 策略 1 | 策略 2 |
| --- | --- | --- |
| 成片素材 | 全时间线为真实 3D | 核心动作真实 3D，补充镜头可用合规实拍或原创 Remotion 图 |
| 编译 | 现有 3D 模板、镜头与模型绑定 | 同一 Blueprint 规划知识、相机、场景、补充素材和证据 |
| 来源验证 | Blender 场景、证据、渲染和成片回放 | 核心 3D 保留原校验，增加实拍授权与实际取用区间、原创图配置和完整 Remotion 回放 |
| 独立 QA | 机构、连续视听、理解、文字、封面与增长 | 保留原检查，增加分镜计划和实际媒体的逐镜头视觉检查 |

```sh
uv run python -m mechanical_video_next produce --topic '修正带为什么能收紧？'
```

Producer 根据研究结果选择表达方式和已验证的素材。CLI 建账并写入现有 Producer 指令，由当前 Codex 会话执行研究和制作。机械技术史按有效契约绑定主题与档案，具体机构的结构和动作有各自的证据。

## 先确定观众会发现什么

「君哥拆机器」的新混合任务默认使用 `mechanical-story-v6`。根据真实使用、观众疑问、设计矛盾和可见发现登记创意顺序，再核实科学和制作条件。三维拆解、剖视和运动展示揭示关键设计，历史转折可以用档案或原创重建，设计取舍可以用同条件对比。写下选中的 `audience_decision`，先用完整动稿检查节奏和回报，再确认正式素材。Blueprint 用具体镜头绑定开场与视觉回报。连续三段以上的内部机构视图需要导演说明其因果连贯性的价值。动态预览以实际媒体和时间码评审。局部画面缺陷回到对应镜头，故事缺少观众问题或整条因果进展时回到选题。

v4 起，研究用 `story_exploration` 保存候选与取舍，并在 `science.facts` 绑定实际查阅位置、文件路径和 SHA256。较早版本的 `visual_research` 使用八个键 `use_context`、`common_misconception`、`science_question`、`causal_relationship`、`comparison`、`technical_background`、`structure_to_phenomenon`、`everyday_conclusion`。可用信息填 `SUPPORTED`、`finding`、`evidence`，其余写 `UNKNOWN` 或 `NOT_APPLICABLE` 及原因。确定要展示的知识、动作和画面任务后，再选用装配或开始 CAD。

最终在原 `creative-blueprint.shots` 保留 `shot_id`、`time_range`、`narration`、`subtitles`、`evidence_map` 的双向映射，并添加下列信息。

| 字段 | 内容 |
| --- | --- |
| `knowledge_goal`、`knowledge_ids` | 要懂的事实及其现有证据映射 ID |
| `visual_type`、`render_engine` | 见下表 |
| `visual_focus`、`visual_action` | 指明观众看哪里，以及画面中什么真的发生 |
| `camera` | `scale` 用 wide、medium、close、macro 或 diagram，`angle` 描述实际方向，Blender 另填 `preset` 和可选 `settings` |
| `transition` | `kind` 用 cut、match_cut 或 chapter，`link` 写前后知识关联，chapter 另填 `text` |
| `assets`、`evidence` | 生产素材名称与具体事实位置，执行输入单独绑定哈希 |
| `mechanical_role` | `core` 或 `support`。输入、传动、输出、回程以及需要真实空间关系证明的动作登记为 core |
| `duration`、`progression` | 30 fps 网格上的镜头秒数，进展用 new、develop 或 recap，附具体理由 |

| `visual_type` | 可用制作方式 |
| --- | --- |
| `real_use` | 许可实拍 |
| `product_exterior` | Blender、许可实拍 |
| `exploded_view` | Blender |
| `mechanical_cutaway` | Blender |
| `micro_principle`、`abstract_phenomenon` | Blender、Remotion |
| `parameter_chart` | Remotion |
| `design_comparison`、`state_change`、`everyday_return` | Blender、Remotion、许可实拍 |
| `technical_history` | Remotion、许可实拍 |
| `annotated_detail` | Blender |

实拍不可用时用 `material_limit` 记录限制，按同一事实另选表达。实拍只支持已验证的实际使用、对比、回归等补充信息。原创知识图可以在核心动作前建立问题或随后解释已出现的现象。

## 执行与验收

Blender 行沿用 `existing_shot` 与 `science.basis`。establish 用全景及稳定机位，closeup 和 macro 用目标包围盒，follow 用原有 `camera_follow` 模板及目标部件，reveal 和 match_cut 用显式 `science.camera_path`，cutaway 用真实剖切面，isolate 用 `visible_parts`。匹配剪辑在相邻镜头显式维持同一对象位置、方向或运动对应关系，借独立 QA 检查。基础装配、关节控制和经检查的材质保持原有依据。灯光在已批准的摄影棚预设内调节。

补充行用 `template: editorial`。实拍 `footage` 写 `path`、`sha256`、`source_url`、片内 `credit`、取用起点 `start_frame`，并绑定 `license` 的权利人、许可名称、`status: VERIFIED`、`editing_and_distribution: true` 和带定位信息的本地 `proof`。Remotion 的 `graphic` 用 diagram、comparison、chart 或 timeline，提供标题与每项文字，数值图另附单位和非负数值，可选公式。Comparison 使用两个并列信息区。真实 3D 行继续支持逐帧投影标签、读数、放大窗、现有 Blender 立体箭头和原有字幕；chapter 按镜头时钟显示章节提示。数字及几何图的结论由 `evidence` 及现有证据映射覆盖。

自动检查重复焦点、景别与角度，以及把复用的事实反复申报为新知识。复用须体现解释、对比、递进或有用回顾。内容 QA 在现有 `content-qa.visual_checks[shot_id]` 审核计划，实际预览和成片的独立 QA 使用同一组检查项并引用实际时间码。十项是 `shot_scale`、`camera_angle`、`shot_value`、`knowledge_progression`、`narration_alignment`、`mechanism_size`、`motion_visibility`、`whole_detail_link`、`cause_comparison_change`、`material_relevance`。每项写 `status` 与 `observation`。缺少连续视听时记 UNKNOWN，正式验收仍须满足既有来源、机构、理解、媒体、封面及增长报告。

## 同知识目标演示

使用本地既有修正带专利机构预览 v6，保留转印、回收和摩擦环相对于轮缘滑动三段原生 Blender、原旁白与字幕。复用公开专利的文字及图示作为研究依据，流程图使用原创绘制。已有输入与输出均留在本地。

```sh
uv run python scripts/visual_narrative_demo.py output/tasks/production-1794969915231117000/preview-v6/render-config.json
uv run python -m mechanical_video_next.provenance output/correction-tape-visual-narrative-demo-v2.3d-provenance.json
```

| 同目标对照 | 既有预览 v6 | 视觉叙事演示 |
| --- | --- | --- |
| 画面场景 | 3 段 | 4 段，增加 8–11 秒底膜路径图 |
| 景别 | 使用画面、开壳整体、摩擦环特写 | 保留三档 3D 景别，增加正视流程图 |
| 表达形式 | 3D 操作、开壳和局部运动 | 保留上述形式，增加逐步高亮的路径图 |
| 标注功能 | 初始半径虚线和摩擦部件颜色标识 | 沿用标注，路径图补充涂层与底膜各自的去向 |
| 片内重复 | 完整源段哈希重复为 0/3 | 完整源段哈希重复为 0/4。事实回顾占 3/18 秒 |
| 因果理解 | 未测量受众理解 | 新图提供转印与回收的位置对应，受众理解待测试 |
| 本次成本 | 参考历史指标 | 复用全部三段 3D 原片，新增 Blender 动画渲染 0 秒。合成与技术验证约 55 秒。使用一个独立 QA Agent，账单无计量 |

新版全长 540 帧，完整解码和来源回放通过。逐帧 PSNR 最低 48.93 dB，解码音轨一致，三个 3D 场景的九个见证帧最大 RGB MAE 约 2.00。独立 QA 检查两版的采样帧，确认路径图呈现底膜和涂层的去向。它没有增加卷径与打滑之间的解释，后者仍由原有 3D 特写和旁白承担。本次样片使用 3D 与原创动态图，实拍走来源校验测试。连续视听、观众因果理解以及完整正式制作未在本样片验收。
