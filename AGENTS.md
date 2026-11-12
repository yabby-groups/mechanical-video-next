# Mechanical Video Next

## 三路线默认制作（2026-11-11 最新用户要求）

新制作默认同时交付 2D、2.5D、3D，用户只输入机械名称；不要先让用户选路线，不在第一版完成后停止。当前 Codex 主会话是唯一 Producer，复用原生子代理和现有 CLI，不开发常驻 Worker／服务器。共享机械事实、原创旁白、实测音频时间轴、1920×1080/30fps 输出；默认目标60～120秒（省略时90秒）。用户随后再次明确音色采用既有默认 **Neil（阿闻）**，不得切换 Kai。

参考研究用于学习表达，三路线新任务采用原创脚本和镜头顺序，不直接复用受保护台词、序列与独创表达；下文历史单路线复刻规则不改变本条新政策。真实观看、低粉爆款核验缺失必须记录，不能伪造已完成。CAD 自主生成，2D 为真正平面运动，2.5D 有分层深度／投影／剖示，3D 使用 CAD 装配与 Blender。三版各自具备开场、结尾、配音和字幕。先低成本运动验证与独立 QA，再制作高清候选；候选生成不授予正式验收。

入口为 `uv run python -m mechanical_video_next produce --topic 指甲刀 --routes all`；当前已验证的指甲刀适配计划通过 `route-run <task>` 执行，产物位于 `output/nail-clipper/`。其他机械名由当前 Producer 自主研究、准备其真实资产／计划，不把已有指甲刀适配器冒称任意名称生成器。每阶段保存路径、哈希、状态、问题和下一步；`produce --resume <task>` 恢复，不能另起 Producer。

Blender 串行使用全局锁与分块编码；只删除本次已编码、完整解码确认的临时帧。分路线缓存绑定实际源内容，音频只合成一次。每路线独立 QA，并生成带标签的竖屏三格同步对比。相同策略连续两次无改善就诊断并更换策略，不无限重复生成。技术通过与连续观看、听审、科学判断分开；UNKNOWN 不得标 COMPLETED。人工介入、Token、成本等无计量填 null。用户选中版本后的修改只作用于该版本。不得发布、上传或保存平台草稿。

每条视频都研究参考，爆款热度只是优先参考，不是准入条件。普通实物演示、图片、结构图和结构文档都可作为主参考。缺少爆款或原视频不得停止制作；Producer 自动选 3D CAD、2D 或 2.5D。视频逐镜头映射 reference_time_range，静态资料映射 reference_region（对应部位／结构特征），均记录 adaptation。没有视频不填写虚假的完整观看证据。

图片路线已接入 scripts/layered.py 与 scripts/produce.py：layered 镜头直接生成视频并复用配音、字幕和合成。Producer 在资产／蓝图交接前执行 `uv run python -m mechanical_video_next select-route <task> --route 2.5d --reason "结构图适合分层演示"`；无需用户选择。asset-plan 提供 render_route、source_files 的 path/sha256 和 qualified=true。历史报告仅反映当时快照，以本规则为准。

## 时长与节奏（2026-11-12 用户更新）

后续新视频三路线均为60～120秒，默认目标90秒。开头直接呈现关键动作、反常识现象或明确悬念；每个镜头推进新的事实或因果步骤，讲解与动作同步。通过有依据的原理解释、拆解、特写、剖面和对比增加内容深度，禁止靠降速、重复片段、无效停留或强行加快配音凑时长。结尾回扣开场疑问。蓝图和角色交接必须落实这些要求；独立 QA 检查精确媒体的实际时长、开场、信息推进、动作讲解对应及冗余，缺少连续观看或听审时保留 UNKNOWN，不宣称已证明观众留存。现有历史任务和38.2秒指甲刀产物不自动拉长；恢复历史任务沿用其原请求，新建任务执行新范围。

## Autonomous production goal (2026-11-11 user correction)

任务是复刻合格原片。以原片的内容、镜头顺序、节奏、动作与讲解作为制作规格，不自行增加原片未展示的隐藏结构、机构创新或工业级研发目标。模型与动画服务于原片所展示的内容；必要的工程检查围绕实际复刻动作及所作陈述，不扩展为任意机构的完整制造验证。已有一条核验通过的可复刻主参考即可进入制作准备，B/C 类和多风格样本为补充，不作为凑数门槛。

用户输入机械名称后，由 Producer 自主研究参考、选择主参考、核验复刻可行性、研究、建模、制作、测试和修复，中间不要求用户逐步确认。用户不限制 Token 或循环测试/修复次数；不因固定两轮上限停止。无改善必须诊断并更换策略，保留同一持久缺陷的全部历史。外部权限、实际资源和真实能力缺失仍如实记录，不能伪造通过。


新任务默认 autonomy_policy.repair_mode=until_pass、reference_first=true。接续已获授权的旧任务时，Producer 使用 `uv run python -m mechanical_video_next adopt-autonomy <task> --reason '用户已取消修复轮次上限，要求自主完成'` 登记新政策，保留旧停止记录与次数；无需再次问用户，但不能批量启动无关历史任务。视听暂不考虑的讨论不自动取消正式验收要求。本规则覆盖下文和旧记录中的固定轮次限制。

## Python execution

所有由项目或 Agent 启动的 Python 命令统一使用 `uv run`，包括临时脚本、`-c`、模块、测试和校验；脚本内部启动 Python 子进程也必须通过 uv。常用入口为 `uv run python ...` / `uv run python -m ...`，项目 Python 3.11 与基础依赖由 `.python-version`、`pyproject.toml` 和 `uv.lock` 管理。CAD 使用 `uv run --with-requirements requirements-cad.txt python ...`；临时依赖使用 `uv run --with <package> python ...`，不再直接调用系统 Python 或借用旧项目解释器。Blender 的 bpy 脚本由 Blender 内嵌解释器执行，仍使用现有 Blender 入口。沙箱无法写默认 uv 缓存时，设置 `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache`。

## Autonomous CAD asset policy (2026-11-11 user correction)

选择 3D 路线时由 MechanicalResearch 研究真实结构和尺寸依据，再由 CAD 使用 build123d / Open CASCADE 自主参数化生成独立实体与装配；网络图纸、专利、照片、视频只作研究依据。不得默认搜索或下载成品模型，不得因模型网站登录失败停止自主建模。复用旧项目 CAD Skill 的适用方法，不复制整个工程或开发通用几何求解器。

职责为 ViralResearch（创意参考）、MechanicalResearch（结构/约束/尺寸/未知）、CAD（源码/参数/STEP/GLB/装配/验证）、Animation、Editor、独立 QA，当前主会话是唯一 Producer。历史 Asset 和 Research 角色仅兼容既有任务。

先生成装配图、独立零件爆炸图、拉头内部剖切，以及各 3～5 秒啮合/分离测试。教学近似必须标“原理示意”，规定路径不是材料接触仿真。机械关卡核对零件、实体、装配、运动、干涉、横向锁合与机制可见性；未通过不启动高清动画。动态分镜通过独立视频关卡后才启动完整预览和正式渲染。每个持久缺陷保留完整历史，不设自动修复总轮次上限；无改善时诊断并更换策略，继续独立复验。旧轮次上限已被用户撤销，旧失败记录保留。

视觉方向固定参照用户明确指定的**打印机系列 EP03**，来源与哈希见 `config/visual-reference.json`。当前配置使用全画面机械主体、灰色摄影棚空间、金属材质与柔和阴影、斜视及克制推进、少量标注和字幕。沿用现有 EAS 与 EEVEE 预设，不恢复右侧说明栏。视觉参考的选择不自动改变已选 Neil 配音或当前横屏画幅；新片仍需检查实际关键帧与媒体。

Codex 主线程作为唯一 Producer，使用真实 Codex 子代理协作并编排 `.agents/skills/` 中的三个 Skills。先读 README.md、视频配置和资产来源；禁止迁移旧项目复杂架构、通用 CAD 或几何求解器、AI 审核评分模型。

先验证资产、关键帧和当前片段，再做低清全片与正式输出。优先 `scripts/produce.py` 和已固定版本的 EAS，不为每条视频另写场景脚本。工作原理镜头必须有数学或素材依据，简化齿廓始终标注“原理示意”。技术检查通过不代表科学、听感或视觉完整验收。

缓存依据内容与配置，不依据文件名猜测；配音字幕不进入 3D 缓存键。work 预算 2 GiB，空闲盘小于 3 GiB 停止生成。只删除本次生成且已编码验证的 PNG；其他清理由 `scripts/clean.py` 明确执行。assets 与 output 不得自动删除。

单次命令失败后保存证据，由 Producer 自主诊断、修复并恢复；不重复执行未改变的失败方案。不设总轮次上限，无改善则更换策略。每次运行保存耗时、缓存命中和临时空间采样，人工介入与工程开发修改分别统计。

## Production protocol

每做一条新视频都必须做本条爆款研究，并采用主参考复刻方式（2026-11-11 用户明确要求）。选题可以先确定，但在最终脚本与蓝图冻结前，ViralResearch 必须完成候选筛选、数据核验、实际媒体分析，选定一条主参考。复刻其开场、内容结构、镜头顺序、节奏与关键演示，使用本项目自主 CAD、动画和配音重新制作；打印机 EP03 视觉与 Neil 音色继续保留。其他参考用于补充，不能冲淡主参考的明确对应关系。此要求替代旧的“不得沿用镜头序列”限制。

缓存可复用已有观察，但每条任务须重新核对适用性和数据时效，形成自己的研究结论；不能以同系列、已有模型或曾经研究过为由跳过。研究输入/输出绑定当前 task_id 与 topic；蓝图包含 reference_recreation.primary_reference_id 与 shot_mapping，每镜头记录 shot_id、主参考 reference_time_range 和 adaptation（复刻内容及必要调整）。缺研究、主参考、完整映射或实际观察依据时不冻结蓝图、不进入完整制作；缺少爆款样本记录研究缺口，继续使用普通视频／图片／结构资料，不把专业标杆冒称低粉爆款。独立 QA 对照主参考与映射检查实际成片。历史任务的局部修复沿用已批准研究；新视频不得走历史兼容入口跳过此步骤。

新任务使用 protocol_version=2。制作前先读 references 本地缓存，再由 ViralResearch 按 A 同主题50% / B 相似结构30% / C 科普叙事20% 搜索，默认候选30、深析10；实际观看范围、数据来源与 UNKNOWN 明确保留。参考原则必须映射到镜头要求、可观察效果、实际媒体检查和最小修复。ViralResearch 使用 `.agents/skills/viral-video-research/SKILL.md`，只写研究与蓝图。

Producer 检查资产和工具可行性后冻结蓝图。`uv run python -m mechanical_video_next.blueprint compile` 生成真正的镜头/相机/时长/旁白字幕配置；冻结蓝图的 production_config 必须绑定该配置路径和 SHA256。先运行低成本 animatic 并由独立 QA 审核精确媒体，再允许 preview/final；旧任务兼容仅适用于明确的历史工作片，不用于新制作。PROVISIONAL 可生成明确标注的静态占位时间板以发现问题，不能据此通过核心运动或正式制作门禁。QA 缺陷含持久 defect_key；重命名、变更版本不清空修复预算。已知跨任务缺陷及历史次数须继承；继续旧任务时由 Producer 登记当前无限轮次政策，不清空历史，不把恢复修复视为通过。

收到制作请求时，由当前主会话作为 Producer，先用 `uv run python -m mechanical_video_next produce` 创建任务。Python 仅执行确定性工具和校验，不创建伪 Agent。需要外部启动时显式 `--codex` 启动 Codex 入口；已在 Codex 会话内不要再启动第二个 Producer。

最多同时工作 3 个子代理。工具支持时默认 `fork_turns="none"`，只传角色指令路径、任务路径、输入版本与所需输出，不复制整个工程讨论或此前媒体。Research 与 Asset 并行；各自只读必要资料，写自己的 JSON。Research 固定事实和脚本后不重复研究。Asset 必须核查实际模型、独立零件、许可；不合格时 BLOCKED，不能生成虚构复杂结构。Animation 等待两者合格，使用 mechanical-animation；Editor 使用 mechanical-video，可先准备 TTS，最终合成必须等待镜头时间轴。QA 为独立子代理，只写报告，不改生产代码。

角色定义见 `.codex/agents/*.toml`；当前会话未热加载角色配置时，将对应角色指令直接传给原生 spawn 工具并记录此限制。不要以普通进程模拟子代理。所有交接使用 `handoff` 命令保存不可变版本、内容和依赖 SHA256；修改输出创建新版本，不覆盖其他角色产物。Producer 通过 `advance` 执行状态门禁，不能以退出码零替代质量验收。

Blender 重任务通过 `stage` 串行全局锁执行。QA 必须读取实际预览/成片证据，记录媒体 SHA256、取样时间、能力和覆盖范围。每项检查 PASS / FAIL / UNKNOWN；无听审能力不得以响度或 ASR 替代听审，无连续视频能力不得以截图代替完整观看。UNKNOWN 阻止 COMPLETED；保留技术通过但未完全验收的媒体。

每个缺陷必须包含 issue_id、severity、shot_id、time_range、evidence、responsible_agent、suggested_fix、verification_method。结构错误先换合格资产；拆解方向只改当前镜头；遮挡先用已有相机模板；字幕只合成；语音只改对应片段；运动错误回到约束校验。修复先记录基线，再登记策略和可测结果；不设轮次上限，无改善更换策略并继续，独立 QA 决定是否通过。2D/2.5D 是正式制作路线，分层图片使用 layered 模板；机械结论以实际资料为依据。

Token、花费、人工介入缺少运行时计量时填 null，不能填零冒充观测。保留原生子代理 ID 和启动/完成事件；不复制大图或完整历史进入每次上下文。单 Agent 回退保留 `scripts/produce.py`。不得上传、发布、保存平台草稿。

## CodeGraph

若当前会话暴露 `codegraph_*`，结构问题优先 `codegraph_context`，再一次 `codegraph_explore`；符号定义用 `codegraph_search`，调用、影响、文件结构分别用相应图工具。不重复 grep 已由图确认的结构。字面文本用 rg。服务器返回 not initialized 时，询问用户是否运行 `codegraph init -i`。当前创建会话未提供该 MCP 的调用工具，不假装已检索或初始化。

## ego-browser execution

使用 ego-browser 前阅读其 Skill；执行路径 `/Users/lmj/.local/bin/ego-browser`，JavaScript 使用 `nodejs -e`。不使用 heredoc、herestring、bash -lc 或 zsh -lc 包装，不改 Codex 沙箱配置。现有 ExecPolicy 已允许时不额外请求提权。
