## 素材优先混合策略 v1（未来新任务）

用户后续确认：原创科普内容优先、自有素材复用优先、外部素材辅助。每条正式视频独立研究与原创解说、知识结构、分镜和视觉编排；其他创作者默认 REFERENCE_ONLY。禁止通过裁切、翻转、变速、去水印、重新配音包装他人作品；不照搬独创脚本、完整镜头组织和特色表达。重要原理优先自主或具备使用权的可验证动画。现有独立 QA 分别做 copyright_review 与 original_expression_review，原创审查绑定本任务研究/脚本/Blueprint，不能按素材比例判定。合法缓存不提升为自有素材，不默认成立合理引用。

用户 2026-11-18 授权的 [素材优先混合策略](docs/asset-first-media.md) 使用显式 `media_policy_version=1` 与 `visual_policy_version=2`。此版本先逐镜头匹配合规现成素材，再生成无法复用的知识画面；核心动作需可核验原生 3D 或独立核实且获许可的真实机构视频。混合成片输出独立完整媒体来源清单与 QA，不冒用原 3D-only 验收。下文旧 3D-only 规则继续约束未启用此版本的任务；不迁移历史媒体、规则或缓存。保持原有 Agent 数量、模型路由、Producer、锁与资源门禁。

## 视觉叙事策略 2

新选题按 [视觉叙事制作策略](docs/visual-narrative.md) 规划研究、Blueprint 和媒体 QA。策略 2 的核心动作维持原生 3D，补充镜头可以使用许可明确的实拍及原创信息动画。旧任务按账本维持 3D-only。保留现有角色、装配和来源验证、交接、锁、资源门禁以及独立验收。

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

## 产品、参考观察与理解门禁

执行 `docs/product-comprehension-contract.md` 的现有门禁：在建模前确认可识别的真实产品、用途、操作和具体实施例；实际产品来源、CAD零件、连接、输入—传动—输出—回程及成片画面逐项对应。专利或CAD不能单独证明零售产品身份，外观照片不能证明隐藏传动。视频记录实际观看区间、关键时间码、方法、确认动作和未知项，图片/手册记录实际检查区域；不得用标题、搜索摘要、截图或仿真输出冒充连续观看。

蓝图首5秒呈现产品、真实动作、为什么及答案承诺，各镜头新增有来源的知识，最终回到产品功能。独立QA绑定确切MP4/音频SHA256、动作完整区间、听到的旁白和观察能力，分别检查产品识别、机械因果与观众理解；先盲看记录八个理解答案，再核对脚本。五目标（留存、点赞、收藏、评论、关注）分别绑定知识、来源、镜头、动作、旁白、时间码及实际媒体观察回执。不能靠无关讨论或扣留答案；没有真实观测为UNKNOWN，测试和技术检查不授予感知验收，不预测平台表现。只使用现有研究/蓝图/QA/增长报告和handoff，不另建系统。

## 2026-11-15 Reference-First：未来新任务最高优先级

新任务先查本地已验证参考库，再按缺口检索真实拆解/工作视频、制造商手册、可靠结构图、专利具体实施例及可信装配模型。热度只指导表达研究，不能证明机械真实性。采用 `reference_policy_version=1`；历史任务不迁移，不重制回力车，不改已有成片或历史 CAD，不自动恢复失败任务。

资产优先顺序：经检查、可信且许可匹配的现成 3D 装配 → 依据可靠结构资料的 build123d/Open CASCADE 教学模型。只有外观照片不得猜测内部机构；证据不足继续研究或缩小讲解范围，不能用反复建模替代研究。具体型号与实施例必须统一，参考有冲突先解决机构定义。许可未知的内容可作研究线索，不可直接进入成片。复用媒体仍须符合锁定视觉，不能为复用覆盖原有风格。

蓝图必须有主要机械结论到来源位置、零件、动作、素材、镜头及验证方法的 `evidence_map`。先确定核心问题、已核实知识点、可见动作和章节新增信息，再按实测 Neil 音频确定120～300秒；内容不足时保留研究并记录选题与时长不匹配，禁止重复、降速或虚构凑时长。独立 QA 在昂贵正式3D渲染前核对可靠来源、具体机构、模型、动作、证据映射、时长和可执行镜头，重要缺口/UNKNOWN 阻止制作。

沿用现有 Producer 和角色，不增加 Agent 或第二套系统。结构失败先区分资料/模型/装配/动画原因，修正错误依据，保留实质修复历史；已验证结构的普通镜头改动不得触发 CAD 重建。原创解说与视觉编排，不复制未经授权的完整视频、配乐或独创表达。

保留浅灰摄影棚、金属语言、Neil、1920×1080/30fps、真实3D、单行大字号字幕、手机核查、3:4/4:3封面、增长报告、压缩图片证据和安全缓存清理。最终报告绑定实际媒体及版本，记录参考/素材来源、实际复用比例及口径、有依据知识点数、教学近似、未验证结论、增加的有效知识、删除的重复镜头、错误结构重复建模和人工干预次数；无计量填 null，不虚构节省时间或Token。详细契约见 [Reference-First契约](docs/reference-first-contract.md)。

## 2026-11-13 原有视觉风格锁定与手机文字

用户实际截图是正式风格基准：`assets/style-reference/approved-original.png`，来源及保护参数见 `style-lock.json`。增长、参考研究和效率优化不得覆盖已确认的浅灰摄影棚、蓝灰/金属材质、柔和照明、原相机和运动。只调整文字字号、单行、布局及安全边距；不得生成相似图冒充原截图。

新后期文字采用 `config/text-style.json` 与 `mechanical_video_next.text_layout`；字幕必须单行、实测宽度合格且不重叠。超宽句缺可信音频对齐时阻止，不按字数分配时长、不缩字号、不重做已正确TTS/CAD/机械动画。原字体不可用不得静默换字体。历史烧录文字和冻结媒体不自动重制。

风格保护使用 `mechanical_video_next.style_lock`，同时间码/姿态比较非文字区域，禁止用缩放或大面积遮罩隐瞒变化。手机核查使用360/390/430px等比预览。所有Agent常规视觉读取只使用 `qa_images` 返回的压缩路径；每轮最多四关键帧、一联系图；无连续观看/听审能力仍为UNKNOWN。实测范围及未解决事项见 `docs/qa/text-readability-style-lock-20261113.md`。

<!-- mechanical-direction-confirmed-20261113 -->
## 2026-11-13 用户确认：继续机械拆解方向

继续机械拆解与机械原理选题，讲清身边机械怎样工作；打印机与日常机械均可选。不因抖音成长任务8/18计数退回只做打印机，效果以实际留存、收藏与关注分别评价。手摇打蛋器、门锁斜舌、订书机等沿现有任务和候选计划推进，先核对交付，不重复立项或批量开工。落实答案前移、关键动作可见、中段新增知识及结尾兑现。完整用户决定与证据边界见[方向确认](docs/plans/mechanical-direction-confirmed-20261113.md)。现行制作配置和QA契约继续适用，发布由用户执行。


## 2026-11-12 长视频与增长契约（覆盖旧时长和照搬参考序列规则）
新建 protocol-v2 任务 content_policy_version=1：120～300秒，省略时长为 null，Producer 根据可靠知识、原创脚本和 Neil 实测音频确定；指定范围内时长优先。历史任务无此标志，保持原时长、缓存和媒体，不自动重制。
参考用于原创叙事，不复制完整台词或独创镜头序列。研究需覆盖首个答案、中段逐层新增知识、核心机械画面顿悟和结尾兑现；观察不足如实记录。
制作前执行 docs/longform-contract.md 的增长契约和镜头检查。现有角色承担研究、脚本、CAD、动画、剪辑和独立 QA，不新增 Agent。共享事实、原创旁白、实测时轴和增长目标；仅3D画面表达经核实的同一知识。
正式渲染前完整动态分镜必须有运动、旁白、字幕、标注及章节时轴；静态 blueprint animatic 仅占位诊断，不能通过动态或增长 QA。
保留按镜头内容缓存、Blender 串行锁、分块编码和磁盘门禁；字幕改动只重合成，配音调整按实测时轴处理受影响镜头。3D 正式渲染前核查 work 2 GiB 与剩余盘3 GiB门禁及实际资源预算，不在鸡蛋搅拌器切换引擎。
增长检查验证内容与实际媒体，不预测完播、点赞或关注。UNKNOWN阻止验收；不得上传、发布或保存平台草稿。

# Mechanical Video Next

## 当前制作范围与节奏

只制作一条真实 3D 影片，入口为 `uv run python -m mechanical_video_next produce --topic 机械名称 --routes 3d`。时长120～300秒，省略时为 null，由可靠知识和实测 Neil 音频确定；不重复、降速或虚构凑时长。先呈现产品的真实用途和关键动作，再拆解因果，结尾兑现开场。旧三路线、图片路线与60～120秒示例只保留在历史记录，不作为恢复生产授权。

## Autonomous production goal (2026-11-11 user correction)

任务是依据可信产品证据创作原创机械讲解。参考约束产品、结构和动作真实性，并启发表达；不照搬完整原片或独创镜头序列，不发明未被证实的隐藏机构。验证围绕实际动作和结论，不扩展为工业研发。缺少低粉爆款不阻止研究，有一条足以支持核心结论的可信来源即可继续补齐证据。

用户输入机械名称后，由 Producer 自主研究参考、选择可靠参考、核验制作可行性、研究、建模、制作、测试和修复，中间不要求用户逐步确认。用户不限制 Token 或循环测试/修复次数；不因固定两轮上限停止。无改善必须诊断并更换策略，保留同一持久缺陷的全部历史。外部权限、实际资源和真实能力缺失仍如实记录，不能伪造通过。


新任务默认 autonomy_policy.repair_mode=until_pass、reference_first=true。接续已获授权的旧任务时，Producer 使用 `uv run python -m mechanical_video_next adopt-autonomy <task> --reason '用户已取消修复轮次上限，要求自主完成'` 登记新政策，保留旧停止记录与次数；无需再次问用户，但不能批量启动无关历史任务。视听暂不考虑的讨论不自动取消正式验收要求。本规则覆盖下文和旧记录中的固定轮次限制。

## Python execution

CAD 与项目共用 uv 管理的 Python 3.14.2：先执行 `uv sync --extra cad --locked`，建模使用 `uv run --extra cad cad run <model.py>`，诊断使用 `uv run --extra cad cad doctor --check`。CAD 依赖统一锁定在 `uv.lock`；`requirements-cad.txt` 仅保留旧入口兼容，不再作为默认依赖入口。Blender 内嵌 Python 是随软件分发的运行时例外。

所有由项目或 Agent 启动的 Python 命令统一使用 `uv run`，包括临时脚本、`-c`、模块、测试和校验；脚本内部启动 Python 子进程也必须通过 uv。常用入口为 `uv run python ...` / `uv run python -m ...`，项目 Python 3.14.2 与基础依赖由 `.python-version`、`pyproject.toml` 和 `uv.lock` 管理。CAD 使用 `uv run --extra cad python ...`；临时依赖使用 `uv run --with <package> python ...`，不再直接调用系统 Python 或借用旧项目解释器。Blender 的 bpy 脚本由 Blender 内嵌解释器执行，仍使用现有 Blender 入口。沙箱无法写默认 uv 缓存时，设置 `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache`。

## Autonomous CAD asset policy (2026-11-11 user correction)

MechanicalResearch 先核实真实产品、结构与动作，Asset 优先检查可信且许可匹配的现成 3D 装配；不合格时才由 CAD 根据可靠资料用 build123d / Open CASCADE 建模。现成视频可作研究或有来源的补充，但不能替代核心可检查的3D几何与渲染来源链。不因模型网站登录失败反复猜测建模；继续研究或缩小结论。复用现有 CAD 方法，不开发通用几何求解器。

职责为 ViralResearch（创意参考）、MechanicalResearch（结构/约束/尺寸/未知）、CAD（源码/参数/STEP/GLB/装配/验证）、Animation、Editor、独立 QA，当前主会话是唯一 Producer。历史 Asset 和 Research 角色仅兼容既有任务。

先生成装配图、独立零件爆炸图、与所讲机构匹配的内部剖切，以及连续10–15秒产品—操作—输出—内部对应—核心运动与回程预览。3～5秒局部测试仅作诊断，不替代该预览。教学近似必须标“原理示意”，规定路径不是材料接触仿真。机械关卡核对零件、实体、装配、运动、干涉、实际保持/释放关系与机制可见性；未通过不启动高清动画。动态分镜通过独立视频关卡后才启动完整预览和正式渲染。每个持久缺陷保留完整历史，不设自动修复总轮次上限；无改善时诊断并更换策略，继续独立复验。旧轮次上限已被用户撤销，旧失败记录保留。

视觉方向固定参照用户明确指定的**打印机系列 EP03**，来源与哈希见 `config/visual-reference.json`。当前配置使用全画面机械主体、灰色摄影棚空间、金属材质与柔和阴影、斜视及克制推进、少量标注和字幕。沿用现有 EAS 与 EEVEE 预设，不恢复右侧说明栏。视觉参考的选择不自动改变已选 Neil 配音或当前横屏画幅；新片仍需检查实际关键帧与媒体。

Codex 主线程作为唯一 Producer，使用真实 Codex 子代理协作并编排 `.agents/skills/` 中的三个 Skills。先读 README.md、视频配置和资产来源；禁止迁移旧项目复杂架构、通用 CAD 或几何求解器、AI 审核评分模型。

先验证资产、关键帧和当前片段，再做低清全片与正式输出。优先 `scripts/produce.py` 和已固定版本的 EAS，不为每条视频另写场景脚本。工作原理镜头必须有数学或素材依据，简化齿廓始终标注“原理示意”。技术检查通过不代表科学、听感或视觉完整验收。

缓存依据内容与配置，不依据文件名猜测；配音字幕不进入 3D 缓存键。work 预算 2 GiB，空闲盘小于 3 GiB 停止生成。只删除本次生成且已编码验证的 PNG；其他清理由 `scripts/clean.py` 明确执行。assets 与 output 不得自动删除。

单次命令失败后保存证据，由 Producer 自主诊断、修复并恢复；不重复执行未改变的失败方案。不设总轮次上限，无改善则更换策略。每次运行保存耗时、缓存命中和临时空间采样，人工介入与工程开发修改分别统计。

## Production protocol

每条新视频先查本地参考库，按证据缺口检索真实产品工作、拆解、制造商技术资料与匹配装配。ViralResearch 记录实际观察范围和可迁移表达，MechanicalResearch 确认真实性；热度不是真实性凭证或制作准入条件。采用原创旁白和原创视觉编排。研究绑定 task_id/topic，蓝图 evidence_map 将每项主要结论绑定来源位置、部件、动作、素材、镜头及验证方法。视频来源记录实际观看的时间范围和观察证据；静态资料记录实际检查区域，不伪造完整观看。历史 reference-recreation 任务只按其原合同读取，不借此跳过新任务门禁。

新任务使用 protocol_version=2。制作前先读 references 本地缓存，再由 ViralResearch 按 A 同主题50% / B 相似结构30% / C 科普叙事20% 搜索，默认候选30、深析10；实际观看范围、数据来源与 UNKNOWN 明确保留。参考原则必须映射到镜头要求、可观察效果、实际媒体检查和最小修复。ViralResearch 使用 `.agents/skills/viral-video-research/SKILL.md`，只写研究与蓝图。

Producer 检查资产和工具可行性后冻结蓝图。`uv run python -m mechanical_video_next.blueprint compile` 生成真正的镜头/相机/时长/旁白字幕配置；冻结蓝图的 production_config 必须绑定该配置路径和 SHA256。先运行低成本 animatic 并由独立 QA 审核精确媒体，再允许 preview/final；旧任务兼容仅适用于明确的历史工作片，不用于新制作。PROVISIONAL 可生成明确标注的静态占位时间板以发现问题，不能据此通过核心运动或正式制作门禁。QA 缺陷含持久 defect_key；重命名、变更版本不清空修复预算。已知跨任务缺陷及历史次数须继承；继续旧任务时由 Producer 登记当前无限轮次政策，不清空历史，不把恢复修复视为通过。

收到制作请求时，由当前主会话作为 Producer，先用 `uv run python -m mechanical_video_next produce` 创建任务。Python 仅执行确定性工具和校验，不创建伪 Agent。需要外部启动时显式 `--codex` 启动 Codex 入口；已在 Codex 会话内不要再启动第二个 Producer。

最多同时工作 3 个子代理。工具支持时默认 `fork_turns="none"`，只传角色指令路径、任务路径、输入版本与所需输出，不复制整个工程讨论或此前媒体。Research 与 Asset 并行；各自只读必要资料，写自己的 JSON。Research 固定事实和脚本后不重复研究。Asset 必须核查实际模型、独立零件、许可；不合格时 BLOCKED，不能生成虚构复杂结构。Animation 等待两者合格，使用 mechanical-animation；Editor 使用 mechanical-video，可先准备 TTS，最终合成必须等待镜头时间轴。QA 为独立子代理，只写报告，不改生产代码。

角色定义见 `.codex/agents/*.toml`；当前会话未热加载角色配置时，将对应角色指令直接传给原生 spawn 工具并记录此限制。不要以普通进程模拟子代理。所有交接使用 `handoff` 命令保存不可变版本、内容和依赖 SHA256；修改输出创建新版本，不覆盖其他角色产物。Producer 通过 `advance` 执行状态门禁，不能以退出码零替代质量验收。

Blender 重任务通过 `stage` 串行全局锁执行。QA 必须读取实际预览/成片证据，记录媒体 SHA256、取样时间、能力和覆盖范围。每项检查 PASS / FAIL / UNKNOWN；无听审能力不得以响度或 ASR 替代听审，无连续视频能力不得以截图代替完整观看。UNKNOWN 阻止 COMPLETED；保留技术通过但未完全验收的媒体。

每个缺陷必须包含 issue_id、severity、shot_id、time_range、evidence、responsible_agent、suggested_fix、verification_method。结构错误先换合格资产；拆解方向只改当前镜头；遮挡先用已有相机模板；字幕只合成；语音只改对应片段；运动错误回到约束校验。修复先记录基线，再登记策略和可测结果；不设轮次上限，无改善更换策略并继续，独立 QA 决定是否通过。禁止以2D/2.5D或分层图片替代失败的3D镜头；机械结论以实际资料为依据。

Token、花费、人工介入缺少运行时计量时填 null，不能填零冒充观测。保留原生子代理 ID 和启动/完成事件；不复制大图或完整历史进入每次上下文。单 Agent 回退保留 `scripts/produce.py`。不得上传、发布、保存平台草稿。

## CodeGraph

若当前会话暴露 `codegraph_*`，结构问题优先 `codegraph_context`，再一次 `codegraph_explore`；符号定义用 `codegraph_search`，调用、影响、文件结构分别用相应图工具。不重复 grep 已由图确认的结构。字面文本用 rg。服务器返回 not initialized 时，询问用户是否运行 `codegraph init -i`。当前创建会话未提供该 MCP 的调用工具，不假装已检索或初始化。

## ego-browser execution

使用 ego-browser 前阅读其 Skill；执行路径 `/Users/lmj/.local/bin/ego-browser`，JavaScript 使用 `nodejs -e`。不使用 heredoc、herestring、bash -lc 或 zsh -lc 包装，不改 Codex 沙箱配置。现有 ExecPolicy 已允许时不额外请求提权。


## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.

## 2026-11-17 Three-model dispatch policy (overrides older concurrency/model defaults)

Follow [Agent dispatch efficiency](docs/agent-dispatch-efficiency.md) before every spawn. Producer uses gpt-6.1-sol/high; each existing role explicitly sets model and effort in its TOML. Only gpt-6.1-sol, gpt-6.1-terra and gpt-6-luna are authorized. Default two concurrent children; up to three only with demonstrated independent research/verification benefit and explicit session configuration override. Never silently fall back. Simple deterministic work uses Python/FFmpeg/Blender, not an Agent. Reuse unchanged topic/mechanism/source/hash/version-bound results across sessions. Luna collects and classifies only; Sol resolves hidden mechanics, core CAD and product correspondence. Terra handles bounded implementation and visual QA; persistent complex failures escalate with evidence and code diff to Sol. Pass compact paths/hashes/timecodes and scoped defects using fork_turns=none. Record observed runtime model/effort and available usage in existing agent_runs/events; absent billing remains null. Model incompatibility is scoped to the affected call, never a new global video gate. Preserve current production progress and all video capabilities.
