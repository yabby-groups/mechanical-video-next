# 开源导演 Skill 与本地制作审计

上游均按下列提交查阅。审计使用 GitHub 文件树和实际源码，重点读导演入口、决策参考、示例、核心执行代码、资源归属和依赖声明。上游能力来自静态核查，执行验证使用适配后的本地项目。五个项目的安装和构建脚本执行次数为零。

## 上游取舍

| 上游与固定版本 | 实际能力和依赖 | 许可与采用范围 |
| --- | --- | --- |
| cinematic-skills · `0e5b3fe575740cd022d9ffdec7b7568684c885a5` | `shot-director/SKILL.md` 和 `foundations`、`time-and-space`、`moves`、`instructions`、`templates`、`review` 提供以站位和画面任务为先的六层分镜、起止画面、运镜、停留和逐镜复查。该部分是文档方法。相邻 `still-to-film` 包含 `depthshot.js` 的 WebGL 景深视差、Blender 示例及 FFmpeg 收尾工具，涉及 HyperFrames、GSAP、Python 图像库与另行许可的深度、超分模型。仓库配图以 HOME 教学为例。 | AustinZ21 的 MIT 文档作为主要方法改写为机械导演工作。随 Skill 保留原 [MIT 文本](../.agents/skills/director/references/LICENSE-cinematic-skills.txt) 和 [NOTICE](../.agents/skills/director/references/NOTICE-cinematic-skills.md)，包括 Adrian Punk 的先行方法归属。只接入分镜、时空和评审方法。 [源码树](https://github.com/AustinZ21/cinematic-skills/tree/0e5b3fe575740cd022d9ffdec7b7568684c885a5) |
| codex-skills / storyboard-director · `62e6610b0cdade49fcca95ca76ce10dcba145046` | `SKILL.md`、`director_decision_framework`、`object_state_control`、`action_timing_validation`、`critique_correct_verify` 关注调度、物体可见状态和修订。JSON schema、story bible 与分镜样例配合标准库 Python 的规范化、验证、评分和提示词输出，处理计划字段和文本启发式。实际机械渲染和画面判断依赖下游。 | 固定版本的仓库和目录均未找到可授权复制的 LICENSE 或许可声明。仅用通用方法独立编写机构起止状态和复查方法，保留来源指引。 [Skill 与子目录](https://github.com/wjq616919/codex-skills/tree/62e6610b0cdade49fcca95ca76ce10dcba145046/storyboard-director) |
| media-production-skills · `6ba42845c9d355776fb10091e47ee32e035509fc` | `video-director` 有创意和审查模板、Remotion 工程、镜头截取、接触表、封面检查、画面运动技术检查及平台导出脚本。模板需 Node/Remotion/React，部分脚本用 FFmpeg、Pillow 和 NumPy。`media_judge` 经 `httpx` 调用 OpenRouter，旁白套件另含 ElevenLabs 路线。 | Salomón Muriel 的 MIT 项目。用于比较本项目已有的动稿和审查覆盖，复用本地对应能力。 [源码树](https://github.com/salomonMuriel/media-production-skills/tree/6ba42845c9d355776fb10091e47ee32e035509fc/skills/video-director) |
| agentic-video-skills · `204cefd08bbb87fd4681f1f2b0dccbc444a978c1` | Claude 插件集合。导演包有连续性文档、镜头和关键帧模板、生成提示词及 QC 表，目标是 Runway、Veo、Kling、Luma、Seedance 等生成端。目录内 eval 样例与仓库结构测试提供文本检查。 | `NOTICE` 说明导演来自 DirectorSKILL，带 wangzhang-wu 的 MIT 文件及风格参考归属约束。另一个 `ai-video-storyboard` 插件明确缺上游许可。该项目留作参考。 [插件、许可和 NOTICE](https://github.com/cajias/agentic-video-skills/tree/204cefd08bbb87fd4681f1f2b0dccbc444a978c1) |
| video-shotcraft · `075b548c2405a07b77129eb448b0b504fc60dea3` | `SKILL.md` 指向案例库。实际 `PullBackIsolation.tsx` 用 cubic ease-out 和定格收尾，`SlowPushIn.tsx` 从缓慢变焦接硬切，`FocusHandoffTransition.tsx` 通过两层 CSS 失焦交接。配套案例审查揭示小字号、纯整体缩放和切点缺少对位等限制。模板依赖 Remotion/React。Workbench 另需 Vite、Three 和 Zustand，音频素材另列 Mixkit、Freesound 等授权。 | Apache-2.0 的 `PullBackIsolation` 时间曲线适配为 Blender 原生摄影机的推进减速并停留，参数、方向、画面与声音由本项目设定。保留 [Apache-2.0 全文](../.agents/skills/director/references/LICENSE-video-shotcraft.txt)，并在 [配方](../.agents/skills/director/references/shot-recipes.md) 及代码内标记修改来源。采用范围限相机曲线和镜头安排。 [案例源码](https://github.com/Vincentwei1021/video-shotcraft/blob/075b548c2405a07b77129eb448b0b504fc60dea3/demos/camera/tension-camera-moves/PullBackIsolation.tsx) |

## 本项目的执行能力

| 组件 | 代码核查与接入 |
| --- | --- |
| Director | `director.validate` 验 treatment、镜头字段和带实测语音的编辑点。`apply_strategy` 将表现参数送进原 Blender 或 Remotion 适配器，比对机械程序摘要。Skill 为 Producer 提供选择、审看和复修方法。 |
| Visual Planner | `director.select_route` 用科学准确性、可用性和核心镜头路线筛选候选，随后比较匹配、表达、风格与成本。`visual_narrative` 核查视角、表达媒体和知识递进。等带长角位移图复用既有验证和组件，也可由普通混合片入口渲染。 |
| Blueprint | `blueprint.compile_config` 复用现有 shot 模板、科学来源与轨迹，把分镜和 `joint_timeline` 编成执行配置。现有测长、局部渲染、缓存和来源绑定用于本次案例。 |
| Animatic | `blueprint.animatic` 是 FFmpeg 的 15 fps 静态占位诊断。实际 30 fps 移动动稿走 Blender、Remotion 和 `director.preview_evidence`，技术回执区分全流解码、帧变化和连续看听。 |
| audience-review | 现有手动只读 Skill 以实际 MP4 的完播、点赞、吸粉机会为评估目标，独立于导演修改与正式 QA。复修用导演记录中的旧帧、目标变化和新帧。 |

默认创意导演任务的原有 `producer_prompt` 引用项目级 `$director`。沿用现有 Producer、Blueprint、阶段和依赖。该接入无额外 Agent、无新依赖、无第三方付费云调用。本地试片使用已经测长的 Neil 声音。
