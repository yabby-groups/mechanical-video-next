# Skill-Driven Creative Production 试点

本文记录原 Skill-driven 试点和失败基线。《门合上以后》是技术可解码的 40 秒诊断动稿，
用户判定其叙事未达目标。当时的规则和重新制作的门锁动稿见
[历史制作契约](history/production-contract-20261124.md)及[门锁验证报告](productions/story-development-door-lock.md)。
原试点任务按各自固定版本恢复。

## 旧流程中限制创作的地方

| 组件 | 旧职责与实际限制 | 试点的职责及承接 Skill |
| --- | --- | --- |
| `workflow.py` | 默认先调取站外参考，创作 Blueprint 依赖专用参考交接；默认提示词强调拆解和三种处理方式 | 保留交接、恢复、证据和状态管理。Producer 按需选择 mechanical-research、viral-video-research、mechanical-video 或 director。站外参考可作为自选输入。 |
| `production_contract.py` | 要求固定观众决定字段及开场、发现、揭示、解释、结果和兑现的节点和顺序 | mechanical-video 探索故事，director 指导节奏和视觉线索。代码核对故事观察点与知识、镜头、语句或动作的映射。 |
| `creative_selection.py` | v6 历史工作流规定候选状态、优先级、字段和重选条件 | 历史路径继续用原校验。试点由 Producer 对实质不同的方向征求独立编辑意见。QA 评估核心问题、证据、表达和结局。 |
| `director.py` | 三种指定 treatment、逐镜视觉候选评分、策略目录和大量导演字段限制可选组合 | director Skill 选择处理方式和镜头。试点直接把决定写进渲染映射，技术动作校验仍用原工具。 |
| `blueprint.py`、`visual_narrative.py` | 镜头语义枚举、固定转场或推进字段、镜头知识标记容易促成统一分镜 | Blueprint 保存任意命名的可观察点、可选章节及自定视觉表达。编译仍检查现有引擎可执行的媒体输入、时长、装配和视角。 |
| `reference_policy.py`、`media_policy.py` | 资产类别优先级和五级搜索约束选材，章节之间不能重复知识，重复来源窗口被视为填时长 | mechanical-asset 比较与所选场景的匹配。代码验证所选资产、来源、权利和执行。导演可安排有意的回看、重演、纯视觉过场及跨章呼应。 |
| 现有制作工具和主题配置 | Blender 内置摄影棚、模板相机和单装配映射适合快速做拆解。Remotion 原生图表和媒体适配器有可执行输入范围 | mechanical-animation 根据观察任务选工具，必要时从原创场景或合规影片预渲染后交接。Blender、图表、素材工具均可服务同一影片。它们的技术输入要求继续适用。 |

旧工作流便于用既有 CAD、固定镜头模板和解说迅速完成技术可测的片子。即使提示词提到发明和设计取舍，最便宜的可执行路径通常仍是演示零件。试点把题材、场景和媒体选择放在已有制作能力之前，允许不同题材各自决定工作顺序。研究、候选和分镜可以迭代。正式动作或事实的依赖仍决定何时能进入正式渲染。

## 保留的确定性验证

- 研究事实的本地哈希、来源位置、科学范围和未知项。锁定动作的源帧、成片帧、约束和实现对应。原有 CAD、Blender、机械约束与模型独立审查。
- 资产的许可、证明、署名、来源匹配、可用范围。真实机构实拍的核心动作需要既有的独立观察证据。
- Joint Timeline 的帧覆盖和 1:1 动作时钟、原速 Neil 测时、字幕与声画绑定。Remotion、FFmpeg、缓存、串行锁及磁盘保护继续由既有工具执行。
- 正式 Preview 与 Final 的独立 Video Review、整片观察、媒体哈希、版权和可重现证据。诊断动稿的审查单独绑定同一份 MP4。

## 门锁对照

旧版在 2.6 秒以把手近景开场，11 秒拆开装配，40.7 秒切到俯看斜舌，52.2 秒回到门边。已出具机械失败审计，后续 97.67 秒修订也有机械缺陷。两版保留原文件与判定。 [旧片](../output/tasks/door-handle-return-20261121/complete-door-cycle/门把手回正-完整门锁循环.mp4) · [机械审计](productions/door-handle-mechanical-audit-20261121.md)

预演用抱纸袋的生活情境提出问题。11–32 秒在同一个俯视坐标中比较斜面让位、直面受挡和压把手释放，32–40 秒回同一人物开门。Yale 发明故事和插闩对照均比较过。选定主题使用当代厂商手册约束斜舌方向，画面标示运动原理示意。 [40 秒预演](../output/tasks/door-latch-skill-pilot-media/revised/door-latch-story-preview.mp4) · [三方向](../examples/skill-driven-door-latch/directions.md) · [研究](../examples/skill-driven-door-latch/research.md)

复核在首版发现把手底板随柄转动，已修复，独立评审在修订版抽帧中未复现。实际 MP4 校验了 1,200 帧和 AAC 与 Neil PCM 的时序。独立连续视听、三维接触、手部遮挡下的动作可读性仍待验证。此案例止于授权的低成本动稿，作为诊断动稿进入试点台账。正式 Blueprint 编译与原生动作绑定由回归用例验证。 [独立审查](../examples/skill-driven-door-latch/media-review.md) · [技术验证](../output/tasks/door-latch-skill-pilot-media/revised/technical-review.json)
