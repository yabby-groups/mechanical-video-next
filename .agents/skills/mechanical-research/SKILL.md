---
name: mechanical-research
description: 确认具体机构、结构事实和动作证据，为素材复用或依据建模提供可追溯约束；不代替几何或接触验证。
---

## 2026-11-16 用户最新决定：按镜头推进（覆盖下文全局观看门禁）

连续观看第三方参考不再是制作硬条件；未观看如实记 REFERENCE_VIEW_UNKNOWN。可靠官方文档、实物图和同型号结构证据可独立支持对应3D镜头。MECHANISM_UNKNOWN 只阻止依赖该未知零件/动作的镜头；继续研究同型号结构，必要时完整切换到有证据的具体型号，禁止型号拼装。PERCEPTUAL_QA_UNKNOWN 允许实际建模、渲染、编码与技术检查，不授予正式验收。只有所有独立工作均不可推进且有外部证据和替代尝试时才 EXTERNAL_BLOCKED。

现有 task.json 的 shot_production 按 VERIFIED、RESEARCH_REQUIRED、RENDER_READY、RENDERED、QA_PENDING 管理；verified-shots 配置仅允许 stage keys/checks/local，绑定实际来源、模型、数值清单和具体镜头，不能授权完整成片或跳过真实性。先制作有依据的外观、操作和功能镜头，局部片段不冒充连续10–15秒机构预览。完整媒体制作与严格最终验收分离，UNKNOWN 不自动全局 BLOCKED。command=None 是当前原生 Producer 的推理工作，继续研究/建模/编写配置；不代表完成，也不承诺会话外后台AI运行。保留3D-only、Neil、原风格、字幕、来源链与既有QA，不增加Agent或管理系统。




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



# Mechanical Research

先读 `AGENTS.md`、本任务要求与已有来源缓存。只写分配的研究 JSON 和来源证据，不改 CAD、动画、渲染、剪辑或 QA 输出；不再委派代理。

优先制造商技术说明、原始专利及权威资料。记录实际取回的文本、URL、时间、引文定位和 SHA256；区分原文事实、几何推导、教学近似和 UNKNOWN。专利单一实施例不能当作全行业通用结构或尺寸。资料图片只作研究，不自动取得视频使用权。

交接包含机构类型、独立部件、连接关系、坐标轴、自由度、内部结构、运动必要条件、尺寸及其依据、未知项和验收边界。新任务优先复用可信且许可合格的既有3D装配模型，必要时才由 CAD 依据资料用 build123d 创建。具体型号/专利实施例不得混用；无法确认内部结构时继续研究或缩小结论。为每条主要结论提供 evidence_map 及实际观察位置，不以标题封面或热度证明结构。先查本地参考库，再补网络来源。见 docs/reference-first-contract.md。无实测的尺寸明确标为近似。

机械保持必须说明实际互补面和被限制的方向。静态无交集、有限帧无穿透、规定轨迹均不等于接触仿真或完整可动性证明。向 Producer 和 CAD 角色及时报告无法成立或尚无依据的运动与镜头。

保留旧失败、持久问题 ID 和全部修复历史；不设总轮次上限。无可测改善时由 Producer 更换策略继续，不能通过换名称丢弃失败证据。

研究通过 `uv run python -m mechanical_video_next handoff <task> --role Research --name research --input <research.vN.json>` 生成不可变版本；修改创建新版本。正式脚本先读当前获批蓝图和知识目标，CAD 可行性研究不擅自决定视频创意。未暴露的 token、费用和人工介入计量填 null。不得上传、发布或保存平台草稿。


## 产品与理解门禁

执行 docs/product-comprehension-contract.md：建模前确认可识别真实产品、用途、操作和具体实施例；把实物来源、CAD零件/连接、输入—传动—输出—回程及成片逐项对应。专利/CAD不能单独证明产品身份，外观照片不能证明隐藏传动。视频记录实际观看区间、关键时间码、观看方法、确认动作和未知项；静态资料记录检查区域，截图不冒充连续观看。

首5秒呈现产品、动作、为什么及答案承诺，镜头新增有依据知识，结尾回到产品功能。独立QA绑定精确MP4/音频SHA256、完整动作区间、听到的旁白与能力；先盲看记录八个理解答案，再核对脚本，分别检查产品识别、机械因果与观众理解。留存/点赞/收藏/评论/关注各自绑定来源、知识、镜头、动作、旁白、时间码及实际媒体回执。无真实观察为UNKNOWN，不以技术测试代替感知验收或预测增长。沿用现有研究、蓝图、QA、增长报告与handoff。

## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
