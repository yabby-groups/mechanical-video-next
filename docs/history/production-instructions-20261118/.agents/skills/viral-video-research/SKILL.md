---
name: viral-video-research
description: 每条机械视频制作前研究可核验的低粉高互动作品，分析实际媒体与可迁移表达，交接有证据映射的原创蓝图；不预测爆款，不改渲染代码。
---

## 素材优先混合策略 v1

原创科普内容优先、自有素材复用优先、外部素材辅助。每条正式视频独立研究、原创解说、知识结构、分镜与视觉编排。其他创作者默认只供研究；不通过裁切、翻转、变速、去水印或重新配音包装原创，不照搬独创脚本、完整镜头组织和特色表达。现有独立 QA 分别做版权与原创表达审查，绑定本任务研究/脚本/Blueprint 和精确媒体；不按素材比例判原创。

新任务显式启用 `media_policy_version=1` 时执行 [素材优先契约](../../../docs/asset-first-media.md)。先按知识目标逐镜头匹配合规素材，再生成缺口；REFERENCE_ONLY 不可剪入。核心动作须原生可验证 3D 或独立核实且获许可的真实机构视频；混合成片使用独立来源清单与 QA。下文全片 3D-only 限制仍约束未启用该版本的历史任务，保留所有角色、模型路由、锁和验收门禁。


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



# Viral video research

未来新任务先读 docs/reference-first-contract.md：先查本地参考，核验实际观察范围，机械真实性由 MechanicalResearch 独立确认，热度不能作真实性证明。蓝图主要结论必须有 evidence_map；内容不足120秒时保留研究并阻止虚构制作。当前新任务以 docs/longform-contract.md 为准：120～300秒，Producer按可靠知识与实测Neil旁白决定。growth_goals绑定镜头、机械动作、旁白、可观察证据和检查方法。研究首个答案、中段逐层新知识、机械画面顿悟和结尾兑现。参考用于原创脚本与原创镜头顺序，不复制完整台词或独创镜头序列；本条覆盖下文历史复刻规则。缺少完整观看据实记录。历史任务保持原时长和锁定资产。




先运行 `uv run python -m mechanical_video_next.reference_library search --query '<选题>'`，检索 references/themes、mechanisms、patterns、blueprints。保留缓存观察时间与失效边界，不自动视为当前数据。根据缺口再搜索网络。默认 A 同一机械主题 50%（原理与核心动作）、B 相似结构 30%（微距、剖切、分离、连续运动）、C 高质量科普叙事 20%（开场、悬念、信息推进、配音、字幕、结尾，粉丝不限）。每条记录 reference_class；B/C 明确 transfer_rationale，缺失类别如实记录。

Producer 启动该角色后、最终脚本和分镜冻结前执行。先读 README、选题知识目标、现有配置、模型来源和已知失败证据。只写分配的 research 目录，不修改渲染器。可与 MechanicalResearch 并行核对结构可行性；CAD 等待合格主参考，最终脚本和动画必须依赖 Producer 审核的蓝图。

运行 `uv run python -m mechanical_video_next.viral plan --topic '<选题>' --output <task>/research`，生成最近 90 天查询和缓存身份。使用 ego-browser 时先读其 Skill 并执行 `/Users/lmj/.local/bin/ego-browser skill`；执行用绝对路径和 `nodejs -e`，不使用 heredoc。整个任务仅一个 TaskSpace。优先抖音、小红书和可访问的公开视频、公开榜单。保存查询 URL、抓取时间与页面证据文件及 SHA256。官方允许接口优先；第三方接口必须先核查条款、价格和可信度，不自行购买。登录、验证码、访问限制即停止该渠道，不绕过。每批默认至多30个去重候选、10个深析样本；未找到合格主参考时 Producer 自主换查询/批次继续，复用已有证据，不要求用户确认。

爆款偏好（非制作门槛）：默认粉丝 <10000、赞 >1000、90 天内、直接相关且包含机械动作或解释；不足再分层扩展至 <50000 和 <100000，记录每层真实搜索结果。日期或粉丝未知不能当作通过。保留少量专业视觉标杆（粉丝不限）；标杆与低粉验证标签分开。观察普通作品的公开互动作为账号内比较，无法读取填 null。低粉高互动仅研究信号，不是高完播率证据。

每候选包含 id、url、title、author、published_at、observed_at、followers、likes、comments、saves、shares、views、duration_seconds、source、confidence、evidence、viewing、observations、hypotheses、scores。公开计数保留显示原文和平台舍入性质；不可把显示“1万”当精确计数。证据说明每个指标来自哪里。数据缺失一律 null。去重依据原始平台作品 ID / 规范链接，跨平台同片记录 duplicate_of，不重复计样本。

观看证据区分完整连续观看、片段、截图、页面元数据。没有完整媒体读取即 VIDEO_NOT_VIEWED，局部可写带时间的局部观察，禁止补写全片镜头数、均长、确定节奏或听感。音频未读取则 audio.status=UNKNOWN，数值响度/ASR 不等于听审。每条深析记录：前 3 秒、问题、首次核心动作时间、答案时间、悬念、逐段新增知识和结尾；比例、镜头数与平均长度、特写比例、爆炸/透明/剖面、箭头字幕、运动呈现、材质背景、转场；声音类型、语速停顿、同步音效、音乐和强调。每结论关联实际时间范围、证据路径和能力覆盖，推测另列。

运行 `uv run python -m mechanical_video_next.viral analyze --input <candidates.json> --output <task>/research`。输入顶层含 topic、observed_at、candidates。0–100 的五项 scores 需分别附 scores_evidence；相关性 .25、低粉互动 .20、开场 .20、机械清晰 .20、可实现性 .15。只有真实指标支持互动分；未观看不能评分开场/清晰度。工具报告覆盖率并按可用项归一化；低覆盖高分不压过充分观察样本。启发式筛选不是平台算法。需要补充参考时按 A/B/C 的 5/3/2 目标组织深析，不凑数；主参考不合格或观看不足时继续搜索，缺 B/C 补充不阻塞合格主参考。

每条研究结论映射 requirement_id、shot_id、production_requirement、expected_observable_effect、verification_method、minimal_repair，并记录 decision_basis 与 implementation_cost（无实测金额/时间填 null，可列低/中/高相对成本及依据）。科学知识目标、原始问题、相机、部件、模型、配音字幕与结尾都要明确。使用 `uv run python -m mechanical_video_next.blueprint compile` 将镜头、时长、相机、旁白字幕写入真实生产 JSON；`animatic` 生成实际时间轴 MP4。PROVISIONAL 的占位分镜只用于发现缺陷，不能通过正式门禁。缓存通过 reference_library ingest，未验证蓝图不得进入已验证蓝图库。

输出 viral-analysis.json、reference-videos.md、creative-blueprint.json。蓝图需要核心问题、0–3秒原创开场设计、首次运动时间、拆解顺序、特写、标注位置、解说结构、音效、结尾因果解释、每镜头现有资产/模板映射，以及参考原则的原始证据。观察不足时只给 PROVISIONAL 蓝图，不能冻结。为新任务创作原创旁白及视觉编排；参考只约束事实并启发表达，不复制受保护的完整台词、配乐或独创镜头序列。合法匹配的现成3D装配可经资产检查复用，保留具体来源及许可范围。保留来源与使用范围记录。

Producer 对 observation_basis、mechanics、model_motion、tool_support、unsupported_effects 逐项 PASS / FAIL / UNKNOWN，核对实际模型哈希和验证报告；只有全部 PASS 才交接 feasibility 并冻结蓝图。3D简化必须保留关键机构并有事实依据，明确教学近似；禁止降级为图片或其他路线。冻结后先连续10–15秒真实3D产品—操作—输出—内部对应—核心运动预览，经独立QA通过再做完整低成本动态分镜；静态模型截图和3–5秒局部动作仅作诊断；独立 QA 比较知识目标、提取原则、冻结蓝图与实际媒体。UNKNOWN 阻止高清制作与 COMPLETED。QA 保存真实 MP4 哈希、连续/抽样/听审能力与覆盖。修复不设总轮次上限；未改善更换策略，保留证据并持续独立复验。

记录研究耗时、搜索预算、缓存来源、制作工具耗时、工程修改、原生线程 ID 与事件；人工干预、Token、费用若无运行时计量则 null。减少返工需同口径前后基线，单例不能证明效果。不发布或保存平台草稿。

静态候选 source_kind=image/diagram/structure；image/diagram 的 viewing.status=IMAGE_INSPECTED，structure 为 STRUCTURE_READ。记录 viewing.evidence、observations、source_files（path/sha256）或来源 URL。不得编造视频 duration 或观看证据。静态来源用于结构核实和辅助标注，不能替代核心3D机制。


## 产品与理解门禁

执行 docs/product-comprehension-contract.md：建模前确认可识别真实产品、用途、操作和具体实施例；把实物来源、CAD零件/连接、输入—传动—输出—回程及成片逐项对应。专利/CAD不能单独证明产品身份，外观照片不能证明隐藏传动。视频记录实际观看区间、关键时间码、观看方法、确认动作和未知项；静态资料记录检查区域，截图不冒充连续观看。

首5秒呈现产品、动作、为什么及答案承诺，镜头新增有依据知识，结尾回到产品功能。独立QA绑定精确MP4/音频SHA256、完整动作区间、听到的旁白与能力；先盲看记录八个理解答案，再核对脚本，分别检查产品识别、机械因果与观众理解。留存/点赞/收藏/评论/关注各自绑定来源、知识、镜头、动作、旁白、时间码及实际媒体回执。无真实观察为UNKNOWN，不以技术测试代替感知验收或预测增长。沿用现有研究、蓝图、QA、增长报告与handoff。

## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
