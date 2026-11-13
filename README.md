
## 2026-11-12 长视频与增长契约（覆盖旧时长和照搬参考序列规则）
新建 protocol-v2 任务 content_policy_version=1：120～300秒，省略时长为 null，Producer 根据可靠知识、原创脚本和 Neil 实测音频确定；指定范围内时长优先。历史任务无此标志，保持原时长、缓存和媒体，不自动重制。
参考用于原创叙事，不复制完整台词或独创镜头序列。研究需覆盖首个答案、中段逐层新增知识、核心机械画面顿悟和结尾兑现；观察不足如实记录。
制作前执行 docs/longform-contract.md 的增长契约和镜头检查。现有角色承担研究、脚本、CAD、动画、剪辑和独立 QA，不新增 Agent。共享事实、原创旁白、实测时轴和增长目标；三路线用不同的机械画面表达同一知识。
正式渲染前完整动态分镜必须有运动、旁白、字幕、标注及章节时轴；静态 blueprint animatic 仅占位诊断，不能通过动态或增长 QA。
保留按镜头内容缓存、Blender 串行锁、分块编码和磁盘门禁；字幕改动只重合成，配音调整按实测时轴处理受影响镜头。3D 正式渲染前核查 work 2 GiB 与剩余盘3 GiB门禁及实际资源预算，不在鸡蛋搅拌器切换引擎。
增长检查验证内容与实际媒体，不预测完播、点赞或关注。UNKNOWN阻止验收；不得上传、发布或保存平台草稿。

<!-- Repository boundary: see config/README.md. -->

<!-- operations-growth-20261113 -->
> 2026-11-13现行运营交接：[制作优化执行要求](docs/plans/operations-growth-optimization-20261113.md)。首2秒呈现动作/问题，5秒内开始因果解释，中段逐镜头新增知识；按实际媒体时间码做独立QA。新任务遵循长视频契约120—300秒，未指定duration=null，由知识与Neil实测音频确定；旧60—120秒/90秒运营建议已被覆盖。历史媒体不自动重制。同期复盘与9份原始证据已同步，仅更新制作要求。


> 仓库只跟踪公共工具、共享音色和视觉配置。单片 CAD、素材、制作配置与报告保留本地；下文历史制作命令需要相应本地输入，新检出不包含旧视频工程。详见 [配置边界](config/README.md)。

# Mechanical Video Next

当前默认是**同题三路线制作**：一个机械名称，共享原创脚本、默认 Neil 配音和实测时间轴，生成 2D、2.5D、3D 三个完整版本后再供选择。当前真实端到端验证题目为指甲刀；其他题目仍由当前 Codex Producer 自主准备研究、CAD 和适配计划，不把本题适配器宣传为任意机械的现成生成器。入口和恢复命令见文末“三路线”说明。下文单路线自动选择与复刻说明保留历史兼容，新的三路线原创要求优先。

指甲刀三版的 [EP03 风格修订](docs/productions/nail-clipper-ep03-style-20261112.md) 使用共享视觉配置、全幅 3D 合成与原生局部机位，保留 Neil 配音和既有机械运动。进度与精确媒体验收位于 `output/nail-clipper/shared/style-optimization-state.json` 和版本化 `qa-style-*.json`；旧成片保存在 `shared/style-baseline-v1/`。风格修订不自动取得连续视听或科学验收。

每条视频都研究参考，爆款热度只是优先参考，不是准入条件。普通实物演示、图片、结构图和结构文档都可作为主参考。缺少爆款或原视频不得停止制作；Producer 自动选 3D CAD、2D 或 2.5D。视频逐镜头映射 reference_time_range，静态资料映射 reference_region（对应部位／结构特征），均记录 adaptation。没有视频不填写虚假的完整观看证据。

图片路线已接入 scripts/layered.py 与 scripts/produce.py：layered 镜头直接生成视频并复用配音、字幕和合成。Producer 在资产／蓝图交接前执行 `uv run python -m mechanical_video_next select-route <task> --route 2.5d --reason "结构图适合分层演示"`；无需用户选择。asset-plan 提供 render_route、source_files 的 path/sha256 和 qualified=true。历史报告仅反映当时快照，以本规则为准。

当前流程与进度见[视频复刻流程报告 v3](docs/plans/project-flow-status-20261111-v3.md)（2026-11-11 22:05 快照）。


**当前自主执行目标：输入名称，自主完成。** 根据实际资料自动选择 CAD、2D 或 2.5D 路线并制作。新任务不设 Token 或修复轮次上限，无改善更换策略并保留历史，中间不要求用户逐步确认。旧任务通过 `adopt-autonomy` 登记新政策后继续，历史失败证据保留。这是已落实的执行政策与门禁，尚无任意名称输入后自动交付合格全片的端到端验证。

**Python 统一通过 uv 运行。** 使用 `uv run python ...`，首次自动建立项目 `.venv`；Python 3.14.2 与基础/开发依赖由 `pyproject.toml`、`.python-version` 和 `uv.lock` 管理。CAD 命令使用 `uv run --extra cad python scripts/cad_generate.py ...`，按需加载已固定版本的 CAD 依赖。临时校验依赖用 `uv run --with <package> python ...`。Blender 内嵌 Python 保持由 Blender 执行。受限沙箱可设置 `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache`。

**每条视频必须研究爆款并采用主参考复刻。** 每次制作先筛选、核验并分析参考视频，选定一条主参考，再复刻其开场、内容结构、镜头顺序、节奏和关键演示，以自主 CAD、动画及 Neil 配音重新制作，沿用打印机 EP03 视觉。缓存可复用，但每条须有自己的研究结论和逐镜头对应表。新任务默认 `production_method=reference-recreation`；研究 `task_id/topic` 不匹配、缺主参考或镜头映射时拒绝冻结蓝图，并在生产配置门禁再次核对。未完成研究不能直接开始完整制作。

**后续运营计划已更新（2026-11-11）：**详见[当前执行计划](docs/plans/operations-next-plan-20261111.md)。近期按指甲刀→手摇打蛋器→门锁斜舌→订书机（条件候选）做预检，只锁定下一条制作并准备两条合格储备；拉链重制阻塞不挡其他题预检。沿用自主CAD；修复上限按下述当前自主执行政策更新，低清阶段检查小红书/抖音手机显示；本次仅计划更新，不启动制作。

**资产策略已改为自主参数化 CAD。** 新 CLI 任务默认 `asset_strategy=autonomous-cad`：MechanicalResearch → build123d/Open CASCADE CAD → 独立机械 QA → 动态分镜 QA → 高清制作。网络资料只作结构和创意依据，默认不下载成品模型。当前拉链验证任务为 `output/tasks/zipper-cad-20261111`，源码、STEP/GLB、独立链牙、装配及短动作验证先于全片；历史工作片与旧缺陷记录保留。角色入口新增 `mechanical_research.toml` 与 `cad.toml`；旧 Asset/Research 接口保留历史兼容。每个缺陷自动修复不设总轮次上限，未知不视为通过。

本次[自主 CAD 实际交付与验证结果](docs/productions/zipper-cad-20261111.md)：28 个独立实体、STEP/GLB、连续简化布带、装配/爆炸/剖切图与 8 秒啮合分离诊断已生成。拉片铰接两轮修复后仍有实体干涉，独立 QA 为 FAIL，任务 BLOCKED；没有高清或完整新成片。125 项工程测试通过不代表机械验收通过。

拉链正在按用户要求[重制原生1080P与真实结构](docs/productions/zipper-real1080-20261111.md)：已有原生3D诊断片，有限帧运动无测得穿插，但旧教学模型真实感未通过；正在替换更合适的实体模型，尚无符合新要求的最终片。

拉链已按用户反馈制作[EP03方向风格优化版](docs/productions/zipper-style-ep03-20261111.md)：保留已认可的内容、31.5秒时轴和原配音，调整蓝灰空间、铜青配色、主体大小及标注；独立媒体检查与二维源限制随片记录。

已制作[31.5秒拉链完整有声工作片](docs/productions/zipper-explainer-20261111.md)，含Neil原速旁白、中文字幕与素材署名。采用许可明确的既有原理动画，960×540，技术检测通过；这是可观看的完整animatic，尚未通过正式视听验收。

参考驱动流程现使用 protocol v2：先查本地 references，按 A 同题50% / B 相似结构30% / C 科普叙事20%研究（最多30候选、默认10深析），再将原创蓝图编译为实际镜头配置。配置、蓝图、动态分镜和独立 QA 都绑定不可变哈希；变更输入会使旧批准失效。新增 `.codex/agents/viral_research.toml` 与 `.agents/skills/viral-video-research/SKILL.md`，原有三个机械 Skills 继续复用。

```sh
uv run python -m mechanical_video_next.reference_library search --query '拉链'
uv run python -m mechanical_video_next.viral plan --topic '拉链为什么一拉就能合上？' --output output/tasks/zipper-viral-20261111/research
# 合法浏览器/接口取得真实候选后执行确定性筛选，工具本身不伪装已观看
uv run python -m mechanical_video_next.viral analyze --input output/tasks/zipper-viral-20261111/research/candidates.json --output output/tasks/zipper-viral-20261111/research
uv run python -m mechanical_video_next.blueprint compile --blueprint output/tasks/zipper-viral-20261111/research/creative-blueprint.json --base config/zipper-new.json --output output/tasks/zipper-viral-20261111/blueprint-config.json --draft
uv run python -m mechanical_video_next.blueprint animatic --blueprint output/tasks/zipper-viral-20261111/research/creative-blueprint.json --output output/tasks/zipper-viral-20261111/animatic-v1
```

上面拉链蓝图为 PROVISIONAL；静态分镜明确标记占位，不声称有合格机械运动。正式编译移除 `--draft`，要求完整 FROZEN 蓝图；Producer 将实际配置路径和 SHA256 绑定至新蓝图版本，再登记 feasibility、animatic-manifest 和独立 animatic-qa。QA 比较知识目标、研究原则、蓝图与实际 MP4；UNKNOWN/FAIL 阻止正式渲染。下文旧版直接 preview/final 示例需改用具备合格 v2 交接的 `stage` 或增加 `--task`；历史 v1 工作片须显式指定 `--legacy-workprint`，不能作为新制作验收。

本轮拉链实查、原始链接、蓝图、实际时间板与独立 QA 位于 `output/tasks/zipper-viral-20261111/`，汇总见 `docs/plans/zipper-reference-driven-20261111.md`。没有连续观看/听审能力时不会伪造“对标研究已通过”；原链牙穿插与修复耗尽证据保留。

用户已要求先找爆款再复刻拉链，现有实查结果见[拉链爆款参考候选](docs/plans/zipper-breakout-shortlist-20261111.md)：列出原片链接、当前粉丝、作品表现、普通帖对比、实际画面与制作条件。目前完成候选整理，尚未选定合格的3D低粉主参考。

拉链已按用户“全新的”要求建立[独立新制作任务](docs/plans/zipper-new-20261111.md)，没有复用旧拉链模型、脚本或媒体。当前真实链牙穿插未通过验收，已按两策略各两轮上限停止，尚无合格新成片。

旧项目接续选题见[剩余视频计划（2026-11-11）](docs/plans/remaining-video-plan-20261111.md)：卷尺、拉链已有工作片待验收，另有26个具体候选与2个弹性位；棘轮、按动笔和打印机历史片的剩余验收单列。计划记录不自动启动制作，旧项目版本指针差异与来源快照一并保留。

当前视觉参考已明确为**打印机系列 EP03**：机械主体全画面、灰色空间、金属材质、柔和阴影、斜视与克制的镜头推进，少量标注及底部字幕。`config/planetary-01.json` / `planetary-02.json` 已采用该预设，配音保持 Neil。旧左右分栏配置保留为 `*-panel.json`，既有成片保留。`config/planetary-fullframe-style.json` 是只改版式的中间版本；实际材质灯光预览使用 `config/planetary-printer-ep03-style.json`、现有 EEVEE 渲染器及 `blender/studio_style.py` 小型预设，不复制旧架构。参考风格不等于科学或完整视听验收。

```sh
uv run python scripts/style_preview.py config/planetary-printer-ep03-style.json --phase keys
uv run python scripts/style_preview.py config/planetary-printer-ep03-style.json --phase preview
uv run python scripts/produce.py config/planetary-printer-ep03-style.json --phase preview
```

本地、素材优先的机械科普生产项目。三个 Skills 保留；Codex 主会话作为 Producer，五个窄职责子代理负责研究、资产、动画、剪辑、独立 QA。Blender/EAS 制作镜头，Remotion 合成，FFmpeg 检测。视频号统一默认旁白为 Qwen3-TTS / Neil，与卷尺同款。首期是有独立零件的简化行星齿轮教学装配，不是工业 CAD 或接触仿真。


CAD 与项目共用 uv 管理的 Python 3.14.2：先执行 `uv sync --extra cad --locked`，建模使用 `uv run --extra cad cad run <model.py>`，诊断使用 `uv run --extra cad cad doctor --check`。CAD 依赖统一锁定在 `uv.lock`；`requirements-cad.txt` 仅保留旧入口兼容，不再作为默认依赖入口。Blender 内嵌 Python 是随软件分发的运行时例外。

## 多 Agent 入口

项目级 `.codex/config.toml` 和 `.codex/agents/*.toml` 使用当前官方独立角色文件格式，最多三个子代理，无第二个 Producer，不修改全局配置。已在 Codex CLI 0.167.0 严格配置模式验证五个角色加载；官方依据：[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)。配置不会热加载进已存在的会话，本次协作使用当前会话的原生 collaboration 子代理工具并显式传入角色职责。

```sh
# 在当前 Codex 会话中创建制作任务，由该会话继续派发真实子代理
uv run python -m mechanical_video_next produce --topic "行星齿轮为什么能减速" --duration 90 --config config/planetary-01.json
# 从终端启动一个新的 Codex Producer，原生子代理由 Codex 调用
uv run python -m mechanical_video_next produce --topic "行星齿轮为什么能减速" --duration 90 --config config/planetary-01.json --codex
```

默认命令只创建 `output/tasks/<id>/task.json` 和 `producer-prompt.md`，不会凭 Python 自动拥有智能调度。`--codex` 调用真实 `codex exec --json`，保存原生日志 `codex.jsonl`；需要已登录、受信任的项目和可用的 Codex 服务。已在 Codex 内工作时不要嵌套启动 Producer。原有 `scripts/produce.py` 为单 Agent 回退。

`--voice` 是给 Producer 的明确音色要求，不能绕过现有语音批准与试听流程；默认保留已选 Neil。现有 3D 模板及 layered 图片模板可执行；2D/2.5D 已完成短片编码回归，任意名称到完整合格成片尚未完成端到端验证。Producer 根据选题资料自动选择可表达的路线。45 秒是可请求目标，首条回归基线为现有 36 秒；不能为凑时长加速声音。

Research 与 Asset 并行，Animation 等待其合格交接，Editor 等待镜头时间轴，QA 独立读取实际媒体。每个 JSON 经 `handoff` 保存独立版本、所有权和依赖哈希，变化后旧依赖失效。状态前进用 `advance`，不是根据退出码直接 COMPLETED。

```sh
uv run python -m mechanical_video_next handoff output/tasks/<id> --role Research --name research --input research.json
uv run python -m mechanical_video_next handoff output/tasks/<id> --role Research --name script --input script.json --depends research
uv run python -m mechanical_video_next advance output/tasks/<id> RESEARCHING
uv run python -m mechanical_video_next stage output/tasks/<id> keys --config config/planetary-01.json
uv run python -m mechanical_video_next status output/tasks/<id>
```

上述 stage 需要先登记合格资产并达到 ASSET_READY，完整依赖与命令见 CLI `--help` 和 AGENTS.md。门禁核对实际模型/媒体哈希、关键帧、技术报告及独立 QA；QA 的 UNKNOWN 阻止进入 EDITING/COMPLETED。`stage ... final --workprint` 只允许在 PREVIEW_CHECKING 且 QA 无 FAIL 时生成明确未验收工作样片，不推进状态。单纯 FFmpeg 扫描、截图抽样不能冒充连续观看、听审或原理完整验收。

全局 `work/production.lock` 串行制作与清理；重任务不随 Agent 数量并行。stage 前自动清理超过七天、已完成且未锁定/受保护/被任务引用的可再生缓存，保留 assets、output 和失败证据。直接运行原始单 Agent 脚本时不要并发启动重任务。

## 局部修复与验收

生产协议支持有证据的修复登记，新任务不设总轮次或策略数量上限，无改善时更换策略继续。确定性自动修复适配器当前只覆盖已绑定配置哈希和 cue 的字幕缺陷，其他类型由 Producer 选择现成模板、资产或逐句语音配置后重新交接；没有声称具备任意几何/相机/听感自动判断器。

```sh
uv run python -m mechanical_video_next.repairs output/tasks/<id> --config <video.json> --issue SUBTITLE-1 --shot s1 --cue 0 --text "修正字幕"
uv run python scripts/acceptance.py --run --scenario 1 2 3 4 5 7
uv run python -m unittest discover -s tests -v
```

修复适配器复用已有最终镜头，只重新合成，要求实际 QA 缺陷、精确媒体/配置哈希及 Editor 责任。修复结果仍需新的独立 QA，不直接关闭缺陷或标记成片合格。第六场景需要真实 QA 发现明确标记的受控故障、执行适配器和独立复验，回归脚本不会伪造该过程。第三场景仅修改旁白文本，复用已缓存 Neil 语句并刻意固定字幕作为隔离实验；该测试文件不能当可发布内容。

本次本地证据位于 `output/multi-agent-pilot/`：final.mp4、captions.srt、timeline.json、独立 QA、研究/资产/动画交接、失败证据、acceptance.json。`output/tasks/pilot-20261111/` 保存状态门禁、版本化交接和原生线程协作记录。媒体和本次任务数据未纳入 Git，仍保留在本机。成本统计区分生产工具耗时、Agent 耗时和工程修改；原生接口不暴露的 Token/人工介入计量填 null，不编造零成本。

本次另从本机原生会话 JSONL 提取了真实线程 UUID、完成时间与 Token 快照，见 `native-collaboration.json`；只导出元数据，不复制会话文本或密钥。它包含工程和制作多个回合，不能作为单条视频价格或节省比例。`scripts/codex_usage.py` 可对指定日期目录和 root thread 再提取；本地日志格式不是稳定公共 API，不存在时仍填 null。首轮开发使用了完整上下文继承，后续生产协议改为工具支持时使用新子代理上下文，仅传路径与交接哈希；尚无可比的 Token 降本结论。

## 运行

已验证设备：Apple M3 / 16 GB / macOS 27.3；Blender 5.2.3 LTS，FFmpeg 9.0.1，Python 3.9.6，Node 26.11.1。`BLENDER` 环境变量可覆盖默认应用路径。macOS 沙箱可能需要允许 Blender 后台应用启动；普通沙箱曾在进入 Python 前崩溃，完整本机运行通过。

```sh
npm ci --prefix remotion --cache work/npm-cache --no-audit --no-fund
uv run python scripts/environment.py
uv run python scripts/produce.py config/planetary-01.json --phase keys
uv run python scripts/produce.py config/planetary-01.json --phase preview
uv run python scripts/produce.py config/planetary-01.json --phase final
uv run python scripts/produce.py config/planetary-02.json --phase all
uv run python -m unittest discover -s tests -v
npm run --prefix remotion typecheck
```

依赖已锁定在 package-lock.json。使用已安装 Chrome，不额外下载 Chromium。已交付的 Tingting 成片不需要 API 密钥；Neil 默认旁白通过现有兼容语音网关调用，需要 API 密钥，但不下载本地 TTS 模型。macOS say 分支需有可实际合成的 Tingting voice；仅列出 voice 不代表音频可生成。Neil 使用标准 HTTPS/Python/FFmpeg，但目前只在这台 Mac 做过真实运行验证。

## 统一中文旁白：卷尺同款 Neil（已启用默认）

`config/narration-default.json` 已按用户“和卷尺的音色一致”“设置为默认的音色”的明确指令启用 `config/narration-neil.json`：模型 `qwen3-tts-flash`，音色 `Neil`（阿闻），1.0 倍原速。实际核对了旧卷尺 EVERYDAY_EP03 的 speech-execution.json 和 timeline 记录，音色为 Neil、没有后期加速；只复用音色参数，没有迁移旧项目架构。

Neil 的系统音色偏清晰、沉稳的男声，延续纪录片式自然表达的目标。当前接口没有已验证的原生数值语速、风格或重音指令，使用分句、标点和叙述措辞引导表达，不把不支持的参数当成已生效。目标 1.0 时不使用 atempo；明确调速时只允许 0.95–1.05，并重测字幕时轴，禁止为卡镜头自动加速。

```sh
uv run python scripts/narration.py audition --env-file /path/to/existing.env
# 完成缓存后，无密钥也可复用当前默认音色的试听
uv run python scripts/narration.py audition
uv run python scripts/produce.py config/planetary-01.json --phase all --env-file /path/to/existing.env
```

新试听位于 `output/narration-audition/neil-documentary-audition-v1/`，保留完整 WAV、三个镜头 WAV、SRT 和实测数据。Kai 文件与 `config/narration-audition-kai.json` 只保留为历史对比，不是默认音色。既有 MP4 不重配，新制作由 profile 选择 Neil。

原始、逐句和逐镜头 WAV 缓存于 `assets/audio/narration/`，不会被 work 清理删除。原始请求按模型、音色、文本、端点哈希，处理音频按 profile/代码哈希；换音色不会误用旧声音，修改字幕或处理代码不重复提交原始合成。请求提交写 submitted.json，不确定完成状态不得自动重复付费请求。

FFmpeg 使用双遍 loudnorm，目标 -16 LUFS / -1.5 dBTP，验收容差 ±1 LU、峰值 +0.2 dB。短句第一策略允许一次至多 2 dB 的峰值受限修正；仍不合格时仅一次 2:1 峰值预压缩后按实测响度静态增益与限制器的第二策略，再失败就停。FFmpeg 静音边界保留开头 60 ms、结尾 100 ms 余量，结合处理后 WAV 的 FFprobe 实测时长与混音偏移作逐句字幕，不声称字级或音素强制对齐。超时写 overrun.json 并停止。

批准记录绑定不可变的精确音频与 profile 哈希。当前批准依据是 **explicit_reference_voice_selection**（用户明确选择卷尺同款作为默认），没有声称用户已听审新文案。未来用户明确选择某个既有参考音色并要求设为默认，可用 `activate --receipt <audition.json> --confirmed-selection`；确实试听确认后则用 --confirmed-listened。未经授权改变 profile 不可沿用旧批准。只对 `channel: 视频号` 自动套用默认，显式 narration_profile 也必须指向已批准的 profile。

密钥仅从环境变量、被忽略的 .env.local 或 --env-file 读取，.env.example 只有空值模板。

## 配置与缓存

Git 保存源码、配置、资产来源与部件清单。生成的 Blend、音频缓存和 output 交付留在本地；唯一纳入 Git 的媒体是默认 Neil 音色批准记录绑定的试听 WAV，与不可变批准 JSON 一起保留，以便新检出核验默认音色。新检出尚未生成的 MP4 和运动证据测试会跳过，需按上述制作命令重新生成。

每条视频只编辑一个 `config/planetary-0*.json`。其中指定资产 ID、固定模板、拆解距离、镜头长度、顺序、屏幕说明、解说、配音和编码规格；资产清单与运动参数保存在该 ID 的 `config/assembly.json`。六段分镜复用五个模板；两个原理段引用同一个运动短片。

`components`、`motion_template`、`explosion_sequence` 显式声明本期已验证的部件和轴向拆解预设；当前只接受这套预设序列，不能自动规划任意零件的安全拆解路径。分镜顺序与距离/时间可以改；`subtitles` 可单独修订文字，不重生成配音或 3D。字幕条数需与逐句配音一致。

`overall / explode / detail / motion / assemble` 分别实现整体、逐层拆解、特写、原理、回装。EAS 的组移动、保存位置和回装直接调用成熟插件。`exploded` 也支持静态爆炸图。自动取景覆盖采样姿态，随后对全部帧进行投影边界检查。色彩固定：太阳轮橙、行星轮蓝、齿圈银、行星架绿。

缓存层分别为装配、每镜头的关键帧/低清/正式、每段音频、最终合成；读取时核对 SHA-256。修改 narration 只影响音频与合成；修改屏幕说明、字幕样式只影响合成；修改单镜头仅影响对应镜头及合成。整体场景源或资产参数变化会保守地失效相关模型和镜头缓存。源码算法变化仍需更新相应缓存版本，不支持任意热修改后猜测等价。

当前默认输出为横屏 1920×1080/30fps/H.264/AAC，fullframe 3D 使用同一画幅，预览为 960×540。打印机 EP03 视觉预设使用现成 EEVEE 渲染器、PBR 材质及柔和区域灯；未启用 Cycles。历史 panel 配置保留 Workbench 和原先的独立机械面板。字幕时轴来自每句 TTS 音频实际起止，不是音素强制对齐。

## 资产与科学边界

`assets/assemblies/planetary-teaching-v1/` 保留已验证的模型、部件清单和来源；模型一次生成后缓存复用。几何使用 Blender 官方 `add_mesh_extra_objects` 的现有齿轮生成器及基本图元，不开发 CAD 内核。没有把单个整网格冒充装配体。齿数 18/18/54，三个等距行星，满足 `Zr=Zs+2Zp` 与 `(Zs+Zr)/3` 为整数。

固定齿圈的 Willis 关系为 `Zs(ωs−ωc)+Zr(ωr−ωc)=0`；`ωr=0`，因此 `ωc=ωs/4`。行星自转满足外啮合相对速度式，中心随行星架公转。`scripts/check_motion.py` 独立读取 241 帧实际 Blender 关键帧检查轨迹和速度约束。8 秒运动素材中太阳轮转 2 圈、行星架转半圈；片中“四圈一圈”是比例解释，未声称镜头拍到了四整圈。

齿廓来自简化生成器，未验证渐开线啮合、接触、强度、效率、碰撞和真实拆装路径；外壳是教学盖板。视频全程标注“原理示意”。投影检查不验证遮挡，音轨扫描不判断发音自然度。完整独立视听和科学审阅仍开放，状态只能是 `TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO`。

本地 GLB 或已打包 Blend 可登记、检查独立网格与来源：

```sh
uv run python scripts/import_asset.py model.glb --origin https://example.org/model --license CC-BY-4.0 --version v1
```

单网格、未知许可证会拒绝进入素材库；导入不证明部件语义或授权声明真实。新资产需部件映射与运动资料，当前全片模板只集成这一套行星装配。STEP 需要外部 FreeCAD 转换，本项目没有安装或实现该转换。

## 磁盘、生命周期与失败

work 预算 2 GiB，生成前保守估算未压缩帧上界；每 0.5 秒采样占用，另要求至少 3 GiB 空闲。临时 PNG 编码并完整解码后仅删除对应序列，关键帧保留。峰值为采样实测值，可能漏掉小于采样间隔的瞬时峰值。node_modules、Blender 应用和正式交付不计入 work 峰值，报告另列目录大小。

缓存默认保存 7 天，清理先 dry run，必须显式 `--apply` 才删除已完成且命名合法的缓存条目；资产与成片永远不在删除范围。不自动清除未知临时目录或失败证据；这些需明确检查后处理。

```sh
uv run python scripts/clean.py --older-hours 168
uv run python scripts/clean.py --older-hours 168 --apply
```

原始单 Agent 脚本异常即停，不自动重试。多 Agent 入口仅对有证据的明确缺陷作有限局部修复，策略与次数见上文。本期历史上发生一次媒体修复：低清 625 高度无法编码 H.264，给编码增加单像素 padding 后直接复用原帧通过。环境启动和 npm 缓存权限问题另计，不冒充零工程干预。

## 上游与许可

- EAS 1.14.0：GPL-2.0-or-later，最低 Blender 4.2；固定提交与上游源见 `blender/vendor/SOURCES.json`。原样保留插件及许可证；其真实后台测试通过 335 项。
- Blender 官方 gear generator：GPL-2.0-or-later，固定提交和作者头部已保留，简化齿形边界如上。
- Remotion 4.0.542：自定义许可证，个人、至多 3 员工的营利组织、非营利组织和非商业评估可免费；更大营利组织需要公司许可。全文见 `remotion/UPSTREAM-LICENSE.md`。本项目是本地可行性评估，未来商业使用需核实组织资格。
- Manim Community 0.22.1：MIT；仅查验上游，未安装，也没有进入制作链。
- FFmpeg 当前构建启用 GPL/version3 与 libx264，分发二进制需按其许可处理。
- macOS 系统语音仅已证明本地合成成功，声音再分发条款未做法律核验。

本项目新 Python/TypeScript 代码使用 GPL-3.0-or-later；新教学场景、分镜和解说使用 CC0-1.0。上游代码、系统语音、字体和依赖仍受各自许可约束。没有执行上传、保存平台草稿或发布。

## 横屏默认输出

`config/planetary-01.json` 和 `planetary-02.json` 默认 1920×1080、30 fps、H.264/AAC，使用已选定的 Neil 普通话旁白。视觉参照打印机系列 EP03，采用全画面机械主体、灰色空间、金属材质、柔和阴影及底部逐句字幕。Blender 按完整横屏画幅取景，渲染尺寸与视觉预设源码进入镜头缓存键。当前文件使用 `-fullframe` ID；旧 panel 配置、横屏及竖屏 MP4 保留。

```sh
uv run python scripts/produce.py config/planetary-01.json --phase keys
uv run python scripts/produce.py config/planetary-01.json --phase preview --env-file /path/to/local.env
uv run python scripts/produce.py config/planetary-01.json --phase final --env-file /path/to/local.env
```

支持保留 1080×1920 配置供历史版式复用；改变配音或字幕不会改变 3D 缓存键。横屏也必须先验证关键帧、低清全片，再输出正式成片。

## 三路线同题对比与恢复

```sh
uv run python -m mechanical_video_next.multiroute prepare --topic 指甲刀 --output output/tasks/nailclipper-three-routes
uv run python -m mechanical_video_next.multiroute finalize output/tasks/nailclipper-three-routes --route-2d /absolute/2d.mp4 --route-25d /absolute/25d.mp4 --route-3d /absolute/3d.mp4
# 已有确定性命令计划可一键顺序执行并恢复，智能研究和建模仍由当前 Codex 原生代理承担
uv run python -m mechanical_video_next.multiroute run output/tasks/nailclipper-three-routes --plan /absolute/plan.json
```

`plan.json` 包含 `steps: [{id, command: [argv...], inputs: [文件路径...], outputs: [文件路径...]}]` 和 `routes: {"2d": "...mp4", "2.5d": "...mp4", "3d": "...mp4"}`。命令与路径按项目根目录解释，Python 命令统一 `uv run`；输入须列出配置、代码和资产以正确失效缓存。步骤顺序执行，不并行启动 Blender，不创建服务器或模拟 Agent。名称入口仅建立任务，不能代表任意名称已具备自动 CAD 能力。

共享 `state.json` 保存路径、SHA256、步骤缓存、失败历史与下一步。`finalize` 生成 1080×1920 / 30fps 的 `compare.mp4`、`preview.jpg`、`report.json`，从上到下为带标签的 2D／2.5D／3D 三格16:9画面。输入必须同为30fps、起始时间一致、时长相差不超过一帧；不一致写 FAIL 报告，帧内差异补末帧至最长。三路解码音频哈希完全相同才复用第一路旁白；缺少或不同则保留阻塞问题，原路线有声视频保持独立。精确输入与实现哈希不变时复用已核验输出。状态为 `TECHNICAL_PASS_UNACCEPTED_COMPARISON`，连续视听、结构与参考复刻验收保留 UNKNOWN，独立 QA 不通过前不能宣称完整验收。

三路线现已接入原有 Producer 入口，默认 `--routes all`，也可明确请求单一路线；`render_route` 保留旧主路线兼容，不代表删掉其他 `requested_routes`。

```sh
uv run python -m mechanical_video_next produce --topic 指甲刀 --routes all --task-id nail-clipper-three-routes
# 同一个当前 Codex Producer 接续已有记录，不新建任务或启动第二个 Producer
uv run python -m mechanical_video_next produce --resume output/tasks/nail-clipper-three-routes
# Producer 完成研究/蓝图/分路线资产与关键帧检查后执行已有确定性渲染计划
uv run python -m mechanical_video_next route-run output/tasks/nail-clipper-three-routes --plan /absolute/nail-clipper-plan.json
```

新 `task.json` 有 `requested_routes`、`route_runs`、`shared_production` 的共享时间轴／旁白位置与内容哈希契约。真实三路线智能工作仍由当前 Producer 调用既有 Animation、Editor、QA 原生角色完成；`route-run` 仅串行执行已写好的命令计划与比较，不伪装研究或任意机械 CAD。当前指甲刀已知命令为 `uv run python scripts/nail_clipper_video.py audio`，随后分别 `render --route 2d --quality final` 与 `render --route 2.5d --quality final`；对应产物 `output/nail-clipper/2d/final.mp4` 与 `output/nail-clipper/2_5d/final.mp4`。3D使用已接入的 render-3d，完整计划见下文。

计划可附 `evidence: ["output/nail-clipper/shared/production-statistics.json", "...qa.json"]`；或独立 finalize 重复传 `--evidence <json>`。报告保存来源路径／SHA256及明确写出的 visual_differences，不自动推断审美分数。制作耗时、修复次数、人工干预与缓存复用从实际计量导入，缺少计量为 null；比较编码耗时单独实测，不能替代完整制作耗时。

指甲刀适配器的历史完整计划仅在本地保留于 [config/nail-clipper-three-routes-plan.json](config/nail-clipper-three-routes-plan.json)。已有同题任务可直接 `uv run python -m mechanical_video_next route-run output/tasks/nail-clipper-three-routes`；默认顺序执行共享音频、自主 CAD／时间轴配置准备、2D、2.5D、3D 与竖屏对比。3D实际命令为 `uv run python scripts/nail_clipper_video.py render-3d --quality final`，使用现有 EAS／produce 缓存和共享旁白。首次语音需要有效凭据，可追加 `--env-file /absolute/credentials.env`，计划不保存密钥或任何私人凭据文件路径。已有素材／配置／参数／GLB／运动／时间轴依赖在各步骤执行前核对哈希，恢复不重跑未变步骤；缺少真实资产或凭据会保留失败与下一步，不能伪造通过。默认计划仅适配指甲刀，不承诺任意名称自动 CAD；QA由当前 Producer 派发真实独立代理，确定性 run 不冒称自动感官验收。已有 `output/nail-clipper/shared/production-statistics.json` 和 `output/nail-clipper/shared/qa*.json` 会通过计划 `evidence_globs` 自动作为哈希证据导入。

多路线 COMPLETED 还要求不可变 final-qa 的 `route_checks` 为每个 requested route 提供 `media: {path, sha256}` 与全部既有 QA 检查 PASS，且哈希匹配 route_runs 的实际产物。单路通过不能替其他路线批准，UNKNOWN 继续阻止完成。

新检出的一键计划需要 Producer 先完成并保存 `output/nail-clipper/shared/mechanical-research.json`；缺少该真实研究会在任何付费配音或渲染前停止，记录具体下一步。CAD 的 motion.json 是生成输出，不作为本步骤首次运行前置输入；生成后纳入2D／2.5D／3D缓存依赖。当前3D形变缺陷仍需修复与独立复验，计划执行完成不代表QA通过。

新 protocol 2 任务接受 `--duration 60` 至 `--duration 120`（含边界，省略时请求90秒）；历史 protocol 1 保留30–45秒限制和45秒默认值。三路线保持快节奏、高信息密度：开场直接展示关键动作或悬念，每镜头推进新信息，动作与讲解同步，结尾回扣开场。增加时长依靠有依据的解释和不同演示，不降速、重复、空停或强行加速配音。当前指甲刀适配器仍为已测约38.2秒，不能直接满足新请求；须重新编写内容与时间轴并验证实际媒体，不自动拉伸旧片。独立 QA 检查实际时长与节奏，缺少观看、听审能力保留 UNKNOWN。

报告的 `task_created_epoch` 与 `wall_elapsed_since_task_creation_seconds` 表示从任务建立到该报告快照的总历时，包含研究、等待与修复。`route_receipt_timings` 保存每路原始运行 receipt 的路径、哈希和耗时，不能冒充本次缓存恢复的渲染耗时；`comparison_seconds` 单独计量。缺失的主动制作耗时、具体阶段和人工干预仍为 null。

当前新三路线默认任务采用 `production_method=original-shared-script-three-routes`：研究参考用于核验结构与学习讲解方法，使用原创共享脚本和原创镜头顺序，不照搬原片序列；单路线与既有 `reference-recreation` 任务保留原复刻约束。仅复刻专属逐镜映射门禁随 production_method 区分，科学、资产、动态分镜、实际媒体与每路线独立 QA 不降低。

`route-run` 优先使用任务已登记的 `shared_production.comparison_directory` 存放 compare／preview／report，未登记时仍用 task/multiroute。结果同步 `multiroute_status` 与 `next_step`，不会据确定性命令成功改写原 workflow state 或跨过验收门禁。

### 正式交付封面（3:4 / 4:3）

三路线与对比视频完成后，Producer 在任务交付根目录填写 `cover-plan.json`，确定推荐版本、三路线候选适用性、关键动作时间点和短标题。运行 `uv run python -m mechanical_video_next.covers <task>` 生成 `cover/` 下两张标准 PNG、候选与封面报告；增长报告入口也会执行此步骤。封面独立 QA 的 FAIL / UNKNOWN / 缺失，以及来源版本或文案变化都会阻止新增长契约任务正式完成。只使用已有视频帧与排版，不触发视频重制。完整方案格式及独立 QA 契约见 [封面交付](docs/cover-delivery.md)。
