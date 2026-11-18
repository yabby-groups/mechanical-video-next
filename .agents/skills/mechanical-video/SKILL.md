---
name: mechanical-video
description: 用单一视频 JSON 编排分镜、普通话配音、字幕、Remotion 合成及 MP4 技术检测。
---

## 视觉叙事策略 2

读 [视觉叙事契约](../../../docs/visual-narrative.md)。补充实拍和原创动态图按 Blueprint 的事实及素材绑定进入同一水平成片，许可不明时换成证据支持的表达并记录限制。复用字幕、安全盒、跟踪标注、读数和放大。精确媒体独立 QA 及旧任务约束继续生效。

## 科学信息后期

参照 `docs/science-production.md` 在 storyboard 写相对镜头起点的 `information`：使用实际 Blender 逐帧投影跟随，同源 3D 放大框、绑定依据的数值和单行说明。视觉安全盒和浏览器测宽仍适用；复看整段排除遮挡与标注干扰。字幕与标注编辑只重合成，正式输出绑定 Remotion 构建到现有 3D provenance，不用技术通过代替听审或观看。

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



# mechanical-video

## Producer 续接与交付

子 Agent Completed 只表示 SUBTASK_COMPLETED。全局分别记录 RESEARCH_READY、MODEL_READY、PREVIEW_READY、FINAL_RENDERED、QA_ACCEPTED、DELIVERED；研究、CAD、配音、局部诊断片均不是交付。每次交接或阶段运行后由现有 ledger 自动刷新 continuation，Producer 必须执行其中可继续的工作，不要求用户逐阶段说“继续”。

`uv run python -m mechanical_video_next continue <task>` 核对真实媒体及不可变交接，返回下一责任人、具体动作、剩余工作与恢复命令。已编写本主题确定性计划时，`continue <task> --plan <plan.json>` 绑定路径/哈希，`continue <task> --execute` 通过原有门禁执行计划；不得借用其他题目的默认计划。需原生 Agent 的研究、修复、验收仍由当前唯一 Producer 派工，不模拟后台 Agent。

完整低成本动态分镜可在 RESEARCHING 用 `continue <task> --animatic-config <config> --preproduction-qa <qa> --execute` 续作，底层仅允许 `stage local --animatic-diagnostic`。独立 QA 必须绑定完整配置及外部依赖哈希，明确允许 raw 全片、禁止昂贵渲染和正式验收；实际预览限制960×540/15fps，保留原 state，完成后转有声合成与独立实际媒体检查。该入口不能借局部四秒诊断通过正式制作门禁。

所有规定章节、完整中文旁白、单行字幕、一条真实3D完整MP4、3:4/4:3封面、增长及参考模型报告均须实际存在并绑定哈希。独立 QA 接受后先向用户提供文件，再运行 `record-delivery <task> --file <path> ... --reason <说明>` 登记。完整渲染与 QA 接受仍不同于已经交付；会话退出码或子代理完成事件不得替代交付。运行环境无法持续时保留准确恢复命令并明确 `background_execution=false`，不承诺会自行继续。

先读 README.md 与视频 JSON。Producer 主线程通过真实 Codex Research、Asset、Animation、Editor、QA 子代理编排三个 Skills；Python 只提供确定性运行与交接，不创建多 Agent 平台。沿用 produce.py 固定镜头、预览和缓存；修改旁白或字幕不重做 3D。结构化交接与状态门禁见 AGENTS.md 和 mechanical_video_next。

视频号统一默认旁白按用户最新选择为 config/narration-neil.json：qwen3-tts-flash / Neil（阿闻），与卷尺 EVERYDAY_EP03 的实际合成记录一致，目标 1.0 倍。Kai 只保留为历史试听。当前接口没有已验证的原生语速、风格或重音控制；不要把这些词拼进发音文本或发送被静默忽略的参数。使用口语分句、自然标点与叙述措辞引导停顿和重点；技术检查不能代替听感判断。

运行 `uv run python scripts/narration.py audition --env-file <local-env>`，保留 output/narration-audition 下试听 WAV、各镜头 WAV、SRT 与实测记录。assets/audio/narration 分别缓存原始、逐句和逐镜头 WAV；FFmpeg 双遍 loudnorm 目标 -16 LUFS / -1.5 dBTP，短片第一策略允许一次不超过 2 dB 的增益与峰值限制修正；仍不合格时仅尝试一次 2:1 峰值压缩后按实测响度静态增益与限幅的第二策略，再失败即停。目标 1.0 不加 atempo；有明确需求时后期调速只允许 0.95–1.05 并重新测时。禁止为了塞进镜头而自动加速。

字幕依据 FFmpeg 静音边界（保留辅音余量）、FFprobe 的最终 WAV 时长与实际混音偏移；这是逐句对齐，不是语音识别或音素强制对齐。单独改 subtitles 不重生成音频。语句超时只缩短当前文案或延长当前镜头，记录 overrun.json。

TTS 不自动重试；submitted.json 表示请求已提交，状态不确定时不得重复付费请求。只通过环境变量、.env.local 或 --env-file 取密钥，不把密钥写入配置、日志、命令参数或 Git。

默认配置见 config/narration-default.json。用户已明确要求“和卷尺的音色一致”“设置为默认的音色”，这授权启用 Neil，无须再次索取试听确认。使用 `uv run python scripts/narration.py activate --receipt <audition.json> --confirmed-selection` 记录按既有参考音色作出的明确选择，不声称用户已经试听新的文案。只有用户确实确认新试听听感时才用 --confirmed-listened。固定精确音频和 profile 哈希；未经授权改变音色/profile 不得静默沿用旧批准。既有成片保持原样，新视频号制作读取 Neil 默认配置。

完整 MP4 必须通过 ffprobe 规格、字幕区间、音轨和完整解码。技术通过只标 TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO；完整视听、遮挡、接触力学和发布权利不得冒充已验收。不得自动发布。

默认成片为横屏 1920×1080 / 30fps / H.264 + AAC。视觉参考已由用户明确为**打印机系列 EP03**，不是卷尺。采用 `presentation: mechanism-fullframe` 和 `render.framing: fullframe`：机械主体全画面、小标题与底部字幕，不恢复右侧说明栏、大标题卡或进度条。现有镜头用 `visual_profile: printer-ep03-studio-v1`、`camera_view: oblique`，经现有 EEVEE 渲染器呈现金属、灰色空间、柔和投影和克制推进；不复制旧项目架构。旁白保留已选择的 Neil，本次视觉参考不自动切换声音。旧左右分栏配置保留于 config/planetary-0*-panel.json，不覆盖旧成片。先验证关键帧和低清预览，再正式合成；不能仅凭全画面布局声称已匹配 EP03 全部质感或通过视听验收。


## 产品与理解门禁

执行 docs/product-comprehension-contract.md：建模前确认可识别真实产品、用途、操作和具体实施例；把实物来源、CAD零件/连接、输入—传动—输出—回程及成片逐项对应。专利/CAD不能单独证明产品身份，外观照片不能证明隐藏传动。视频记录实际观看区间、关键时间码、观看方法、确认动作和未知项；静态资料记录检查区域，截图不冒充连续观看。

首5秒呈现产品、动作、为什么及答案承诺，镜头新增有依据知识，结尾回到产品功能。独立QA绑定精确MP4/音频SHA256、完整动作区间、听到的旁白与能力；先盲看记录八个理解答案，再核对脚本，分别检查产品识别、机械因果与观众理解。留存/点赞/收藏/评论/关注各自绑定来源、知识、镜头、动作、旁白、时间码及实际媒体回执。无真实观察为UNKNOWN，不以技术测试代替感知验收或预测增长。沿用现有研究、蓝图、QA、增长报告与handoff。

## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
