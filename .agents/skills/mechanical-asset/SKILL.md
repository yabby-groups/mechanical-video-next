---
name: mechanical-asset
description: 检索、导入和验证可独立拆解的机械装配资产，记录来源许可证并管理模型缓存。
---

## 跨视频资产接口

先查现有支持的资产。按 `docs/science-production.md` 的 `reuse` 版本 1 记录具体实施例、图层/零件层级、单位、材料、来源与许可、几何程序及适用范围；控制声明列出实际驱动、影响部件、自由度及约束。声明不是已验证求解器，换型号或修改几何须重新检查证据和运动，不得拼接不同实施例。

## 2026-11-16 单一主参考与方案淘汰（覆盖旧局部修复规则）

先查本地参考，再实际连续观看并选定一条合格主参考，确认可识别的真实产品、实际操作和同一具体机构。记录来源、产品/型号、观看方法、实际区间、关键动作时间码及未知项；未观看、只读标题/摘要或截图均不合格。补充手册、拆解或专利只用于核对该产品的同一机构，不拼接不同实施例。主参考不足以证明隐藏结构时继续研究，不先猜测建模。

先检查结构正确、零件可独立运动且许可匹配的现成3D装配；只有找不到合格资产且产品和机构证据充分时才自主CAD。产品身份错误、机构依据错误或无法对应真实操作属于根本错误：立即淘汰该方案，保留失败原因与历史，重新选择合格参考和资产；`until_pass`不授权对错误方案无限局部修补。已验证正确方案的字幕、遮挡、相机等局部问题才按责任修复。

完整制作前先交付连续10–15秒真实3D动作预览，依次看清“真实产品外形与用途—用户操作—旋转/功能输出—外部与内部零件对应—核心运动及回程”。不是独立零件空转、静态拼图或互不连贯的测试镜头。沿用现有研究、蓝图、handoff和独立QA报告，绑定精确媒体/音频SHA256、观看区间、实际观察与能力；独立QA确认产品识别、操作对应、机械因果及可理解性全部PASS后，才继续完整动态分镜和全片3D制作。没有连续观看/听审能力仍为UNKNOWN并阻止通过，不能用截图、数值测试或代码检查替代。

保留浅灰摄影棚、金属语言、Neil、1920×1080/30fps和单行大字号字幕。研究、代码修改、CAD及局部测试完成仅为子任务完成；完整3D影片、双比例封面、来源/来源链、机械与理解QA及五目标增长报告实际提供给用户才构成交付。只修订现有流程，不开发新的QA系统。


## 2026-11-16 3D-only production — highest priority

New production is permanently 3D-only: `requested_routes=["3d"]`, `render_route="3d"`.
Requests for `2d`, `2.5d`, `all`, illustrated or layered mechanical subjects fail explicitly.
Never downgrade a failed 3D shot or replace its action with images or text. Licensed,
verified 3D assemblies take priority; otherwise model from reliable product evidence.
Every core shot needs inspectable 3D geometry, camera, spatial motion, scene and render
provenance bound through the complete MP4 build in `3d-provenance.json`. A name, extension,
perspective screenshot or ffprobe result is insufficient. Subtitles and explanatory
overlays may accompany real 3D; they cannot replace the mechanism.
Deliver one 1920×1080/30fps 3D film with Neil, both 3:4 and 4:3 covers, references,
provenance, mechanical/comprehension QA and five-goal growth report. No comparison or
other route is required. Preserve historical media/data; historical route examples
below are read-only documentation, not authorization to produce them. Continue scoped
repair until actual delivery or a documented external evidence/tool/resource boundary;
never claim UNKNOWN as acceptance. Do not recreate the pull-back car.



# mechanical-asset

未来新任务优先检查可信、匹配且许可合格的现成3D装配；仅在没有合格现成内容且有可靠技术依据时自主建模。先查本地已验证参考与资产缓存，再补网络。记录候选、许可范围、未采用原因、具体机构与实际复用口径，不能把许可未知或外观猜测标为合格。遵循 docs/reference-first-contract.md；历史任务保留原策略与状态。

多 Agent 制作时由 Asset 子代理与 Research 并行准备，只输出自己的 asset-plan.json。记录 qualified、实际 model.path/model.sha256、independent_meshes、missing_required_parts、来源与许可、可复用镜头和制作路线。只有实际检查过的资产可合格；无合格资产时 BLOCKED，不生成虚构复杂结构。Producer 用版本化 handoff 交接，不覆盖其他角色产物。

先读 config/assembly.json 和 blender/vendor/SOURCES.json。本示例通过 Blender 官方齿轮生成器一次生成教学装配，不建立 CAD 求解器。运行 `uv run python scripts/produce.py config/planetary-01.json --phase keys`，检查缓存内 assembly.inventory.json 的部件数、required_parts 和独立网格。外部 GLB 用 `uv run python scripts/import_asset.py --help` 导入检查；只有一个整体网格必须拒绝。STEP 需已安装 FreeCAD 做格式转换，不把 STEP 文本当装配。未明确授权或许可证未知的素材只登记，不进入制作。素材证据放 assets/assemblies；可再生成缓存放 work/cache/assets。仅用 `scripts/clean.py` 清理已登记临时文件，原始资产与 output 不可自动删除。


## 产品与理解门禁

执行 docs/product-comprehension-contract.md：建模前确认可识别真实产品、用途、操作和具体实施例；把实物来源、CAD零件/连接、输入—传动—输出—回程及成片逐项对应。专利/CAD不能单独证明产品身份，外观照片不能证明隐藏传动。视频记录实际观看区间、关键时间码、观看方法、确认动作和未知项；静态资料记录检查区域，截图不冒充连续观看。

首5秒呈现产品、动作、为什么及答案承诺，镜头新增有依据知识，结尾回到产品功能。独立QA绑定精确MP4/音频SHA256、完整动作区间、听到的旁白与能力；先盲看记录八个理解答案，再核对脚本，分别检查产品识别、机械因果与观众理解。留存/点赞/收藏/评论/关注各自绑定来源、知识、镜头、动作、旁白、时间码及实际媒体回执。无真实观察为UNKNOWN，不以技术测试代替感知验收或预测增长。沿用现有研究、蓝图、QA、增长报告与handoff。

## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
