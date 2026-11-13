---
name: viral-video-research
description: 每条机械视频制作前研究可核验的低粉高互动作品，分析实际媒体、选定主参考并交接逐镜头复刻蓝图；不预测爆款，不改渲染代码。
---

# Viral video research

当前新任务以 docs/longform-contract.md 为准：120～300秒，Producer按可靠知识与实测Neil旁白决定。growth_goals绑定镜头、机械动作、旁白、可观察证据和检查方法。研究首个答案、中段逐层新知识、机械画面顿悟和结尾兑现。参考用于原创脚本与原创镜头顺序，不复制完整台词或独创镜头序列；本条覆盖下文历史复刻规则。缺少完整观看据实记录。历史任务保持原时长和锁定资产。




先运行 `uv run python -m mechanical_video_next.reference_library search --query '<选题>'`，检索 references/themes、mechanisms、patterns、blueprints。保留缓存观察时间与失效边界，不自动视为当前数据。根据缺口再搜索网络。默认 A 同一机械主题 50%（原理与核心动作）、B 相似结构 30%（微距、剖切、分离、连续运动）、C 高质量科普叙事 20%（开场、悬念、信息推进、配音、字幕、结尾，粉丝不限）。每条记录 reference_class；B/C 明确 transfer_rationale，缺失类别如实记录。

Producer 启动该角色后、最终脚本和分镜冻结前执行。先读 README、选题知识目标、现有配置、模型来源和已知失败证据。只写分配的 research 目录，不修改渲染器。可与 MechanicalResearch 并行核对结构可行性；CAD 等待合格主参考，最终脚本和动画必须依赖 Producer 审核的蓝图。

运行 `uv run python -m mechanical_video_next.viral plan --topic '<选题>' --output <task>/research`，生成最近 90 天查询和缓存身份。使用 ego-browser 时先读其 Skill 并执行 `/Users/lmj/.local/bin/ego-browser skill`；执行用绝对路径和 `nodejs -e`，不使用 heredoc。整个任务仅一个 TaskSpace。优先抖音、小红书和可访问的公开视频、公开榜单。保存查询 URL、抓取时间与页面证据文件及 SHA256。官方允许接口优先；第三方接口必须先核查条款、价格和可信度，不自行购买。登录、验证码、访问限制即停止该渠道，不绕过。每批默认至多30个去重候选、10个深析样本；未找到合格主参考时 Producer 自主换查询/批次继续，复用已有证据，不要求用户确认。

爆款偏好（非制作门槛）：默认粉丝 <10000、赞 >1000、90 天内、直接相关且包含机械动作或解释；不足再分层扩展至 <50000 和 <100000，记录每层真实搜索结果。日期或粉丝未知不能当作通过。保留少量专业视觉标杆（粉丝不限）；标杆与低粉验证标签分开。观察普通作品的公开互动作为账号内比较，无法读取填 null。低粉高互动仅研究信号，不是高完播率证据。

每候选包含 id、url、title、author、published_at、observed_at、followers、likes、comments、saves、shares、views、duration_seconds、source、confidence、evidence、viewing、observations、hypotheses、scores。公开计数保留显示原文和平台舍入性质；不可把显示“1万”当精确计数。证据说明每个指标来自哪里。数据缺失一律 null。去重依据原始平台作品 ID / 规范链接，跨平台同片记录 duplicate_of，不重复计样本。

观看证据区分完整连续观看、片段、截图、页面元数据。没有完整媒体读取即 VIDEO_NOT_VIEWED，局部可写带时间的局部观察，禁止补写全片镜头数、均长、确定节奏或听感。音频未读取则 audio.status=UNKNOWN，数值响度/ASR 不等于听审。每条深析记录：前 3 秒、问题、首次核心动作时间、答案时间、悬念、逐段新增知识和结尾；比例、镜头数与平均长度、特写比例、爆炸/透明/剖面、箭头字幕、运动呈现、材质背景、转场；声音类型、语速停顿、同步音效、音乐和强调。每结论关联实际时间范围、证据路径和能力覆盖，推测另列。

运行 `uv run python -m mechanical_video_next.viral analyze --input <candidates.json> --output <task>/research`。输入顶层含 topic、observed_at、candidates。0–100 的五项 scores 需分别附 scores_evidence；相关性 .25、低粉互动 .20、开场 .20、机械清晰 .20、可实现性 .15。只有真实指标支持互动分；未观看不能评分开场/清晰度。工具报告覆盖率并按可用项归一化；低覆盖高分不压过充分观察样本。启发式筛选不是平台算法。需要补充参考时按 A/B/C 的 5/3/2 目标组织深析，不凑数；主参考不合格或观看不足时继续搜索，缺 B/C 补充不阻塞合格主参考。

每条研究结论映射 requirement_id、shot_id、production_requirement、expected_observable_effect、verification_method、minimal_repair，并记录 decision_basis 与 implementation_cost（无实测金额/时间填 null，可列低/中/高相对成本及依据）。科学知识目标、原始问题、相机、部件、模型、配音字幕与结尾都要明确。使用 `uv run python -m mechanical_video_next.blueprint compile` 将镜头、时长、相机、旁白字幕写入真实生产 JSON；`animatic` 生成实际时间轴 MP4。PROVISIONAL 的占位分镜只用于发现缺陷，不能通过正式门禁。缓存通过 reference_library ingest，未验证蓝图不得进入已验证蓝图库。

输出 viral-analysis.json、reference-videos.md、creative-blueprint.json。蓝图需要核心问题、0–3 秒复刻开场设计、首次运动时间、拆解顺序、特写、标注位置、解说结构、音效、结尾因果解释、每镜头现有资产/模板映射，以及参考原则的原始证据。观察不足时只给 PROVISIONAL 蓝图，不能冻结。按主参考复刻镜头组织和表达方法，旁白结合本题事实重新撰写，媒体由本项目重新制作；其他参考补充主参考的表达。保留来源与使用范围记录。

Producer 对 observation_basis、mechanics、model_motion、tool_support、unsupported_effects 逐项 PASS / FAIL / UNKNOWN，核对实际模型哈希和验证报告；只有全部 PASS 才交接 feasibility 并冻结蓝图。简化 3D/2.5D/2D 仅在已有实现且有事实依据时使用，不自行假设降级可行。冻结后先低成本 animatic（模型截图/现有预览/临时旁白/字幕/切换）和 3–5 秒关键动作；独立 QA 比较知识目标、提取原则、冻结蓝图与实际媒体。UNKNOWN 阻止高清制作与 COMPLETED。QA 保存真实 MP4 哈希、连续/抽样/听审能力与覆盖。修复不设总轮次上限；未改善更换策略，保留证据并持续独立复验。

记录研究耗时、搜索预算、缓存来源、制作工具耗时、工程修改、原生线程 ID 与事件；人工干预、Token、费用若无运行时计量则 null。减少返工需同口径前后基线，单例不能证明效果。不发布或保存平台草稿。

静态候选 source_kind=image/diagram/structure；image/diagram 的 viewing.status=IMAGE_INSPECTED，structure 为 STRUCTURE_READ。记录 viewing.evidence、observations、source_files（path/sha256）或来源 URL。不得编造视频 duration 或观看证据。2D/2.5D 使用 layered 实际渲染，结构文本可据其绘制示意图层并注明依据。
