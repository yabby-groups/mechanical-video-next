# 生产工具可靠性修复

## 基线与范围

当前 HEAD 为 `e85d3a12e6df8fac6b813cd30a5b14946d6028a8`，开始时工作区干净。实际环境为 macOS 27.3（26C5047e）arm64、uv 0.9.16、项目锁定 Python 3.14.2、FFmpeg 9.0.2、Blender 5.3.0、Node 27.0.0-alpha.0.1.0、npm 12.2.2、Remotion 4.0.542。测试使用生成媒体、隔离账本、真实文件锁和本地 HTTP mock。

R1 用 FFmpeg 生成 160×90 的 1 秒 H.264 文件。修改前的 `auto` 和显式 `passthrough` 各输出 1,296,000 字节 RGB24，对应 30 帧。原先两组媒体测试共 13 项通过。Linux FFmpeg 7.1.5 的 26 帧现象在这台 Mac 上未复现。

## 修复与验证

| 项目 | 结论与实际行为 | 关键文件和回归 |
| --- | --- | --- |
| R1 | 已修复输出帧率行为。FFmpeg 按滤镜生成的帧序列输出，解码错误导致失败。版本对比和 Video Review 共用输出同步参数，按半开区间核对帧数。stderr 写入临时文件，诊断带文件名、退出状态和错误文本。 | `media_revision.py` 的 `frames`、`compare`，`video_review.py` 的 `pixel_findings`。实际测试覆盖 30 fps、24 fps、可变帧率、非整秒切点、字幕和主体区域、倒放、真实截断及双侧提前 EOF。 |
| R2 | 已修复。原来先写不可变文件再更新指针，重试会撞上同一版本。现在在账本锁内验证孤儿身份与自身哈希，核对当前角色、payload、依赖和图像证据。内容一致时登记原文件，内容或依赖变化时保留原件并分配新版本。损坏孤儿保留原位并报出明确路径。事件日志先记录已封存的版本与哈希，当前登记以账本指针为准。 | `workflow.py` 的 `prepare_handoff`、`handoff_identity`、`put_handoff`。故障注入覆盖首次和后续版本、相同重试、冲突、过期依赖、篡改和并发版本分配。 |
| R3 | 已修复。六个阶段共用预算采样、取消和收尾。首次预算错误在本次运行中持续有效，子进程按进程组停止。报告同时记录执行异常、预算原因、可用观测值和峰值。Blender 诊断记录取消状态与进程回收。默认 work 上限 2 GiB、可用磁盘至少 3 GiB。 | `scripts/common.py`、`scripts/produce.py`、`blender_runtime.py`。验证了空间恢复后仍失败、执行错误与预算错误同时保留、真实 FFmpeg 被取消、后续命令未启动，以及 Blender 运行器和生产锁释放。取消测试用 Python 模拟长时 Blender 子进程。 |
| R4 | 已修复。清理按生产锁、渲染锁的顺序尝试取锁，两类锁争用都返回 `CleanupBusy`。阶段记录 `cleanup_deferred` 后等待全局生产锁。生产锁内的 Blender 若遇到独立渲染，也可等待渲染锁并响应预算取消。 | `scripts/clean.py` 的 `production_lock`、`workflow.py` 的 `run_stage`、`blender_runtime.py` 的 `blender_slot`。真实文件锁回归覆盖双锁排队与独立渲染锁占用。 |
| R5 | 已修复。合成开始时固定 HTTPS endpoint，请求、锁、原始 WAV 缓存和验收使用同一身份。处理回执绑定有效 endpoint 和批准配置哈希。历史回放使用封存请求，覆盖禁用时在发出收费请求之前拒绝。旧镜头缓存只在每条原始请求身份均匹配时复用。 | `scripts/narration.py`、`audio_timeline.py`、`audio_acceptance.py`。本地 WAV 与 HTTP mock 验证默认地址、尾斜杠、自定义地址、缓存命中、旧请求回放、覆盖策略、未决请求和回执篡改。 |
| R6 | 已修复，原生 Blender 验证通过。每个实际裁切区间的见证帧按当帧求值网格边界和相机投影取 ROI，缺失或出界即拒绝。检查机件和父级变换，利用已绑定约束的数值极值安排形变采样。刚体变换使用实际输出帧时钟，形变按类型选择求值时机，外部依赖修改器使用有界采样。区分有运动、证据不足、采样未发现变化和输出帧静止。 | `provenance.py`、`blender/provenance_audit.py`。原生测试覆盖裁切、机件和相机移动、首中末同姿态的往复动作、出界、静止核心拒绝和静态细节许可。实际 FFmpeg ROI 夹具验证背景一致时仍能识别主体替换，另有 Eevee 原场景重渲染和整段合成重放。 |
| R7 | 已修复。排队前后执行同一套阶段校验，获锁后重读账本并比对配置、相关文件和账本身份。子进程核验 `stage-*.inputs.json` 的哈希、实际读取的配置字节、任务与依赖，再启动生产。登记成功前再次确认输入身份。此处影响排队期间已更改的阶段前置证据。 | `workflow.py` 的 `validate_stage`、`stage_authorization`、`verify_stage_authorization`，`scripts/produce.py` 的 `main`。受控并发分别改了配置、来源证据和 QA，三者都在渲染前拒绝。 |
| R8 | 已修复。固定历史策略的 `shot_production` 与 `source-supported-film` 路线将当前配置对应的成功 final 阶段媒体交给共同验收。缺少独立 QA 或绑定过期时保留待审状态。正常推进至完成后，交付登记继续核对当前媒体、独立 QA 和必交文件。 | `workflow.py` 的 `continuation`、`advance`、`record_delivery`。生成的完整 MP4 与受控账本覆盖待审、QA 失败、QA 通过、缺交付文件、有效收据和依赖更新后失效。该夹具隔离模型、封面和增长报告的既有验证器。 |
| R9 | 已修复。环境入口补齐 `Path` 导入。模拟正常 Blender 版本输出后继续写环境报告。 | `scripts/environment.py`、`tests/test_reliability_repair.py`。 |

## 缓存与历史兼容

渲染授权单独绑定，镜头键仍使用镜头局部输入。已验证合成与音频处理的媒体配方保持一致，`config/cache-code-equivalence.json` 保留 HEAD 的合成键和句级处理键。endpoint 变化会改变原始合成键。付费请求仍由独占提交标记防止重发。来源审计实现的变化使过往验证缓存重新核验。任务原有政策版本由账本继续解析。

## 命令和实测结果

```sh
export UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache
uv run --locked python -m unittest discover -s tests -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m unittest discover -s tests -p test_reliability_repair.py -v
uv run --locked python -m unittest discover -s tests -p test_media_revision.py -v
uv run --locked python -m unittest discover -s tests -p test_video_review.py -v
uv run --locked --with ruff ruff check --select F821 mechanical_video_next scripts blender tests
npm run --prefix remotion typecheck
git diff --check
```

- 完整原生回归用时 76.422 秒，执行 560 项，555 项通过、5 项跳过、0 项断言失败、0 项执行报错。跳过项包括 1 项可选 Remotion 浏览器测试和 4 项缺少历史产物的集成测试。日志位于 `/private/tmp/mvn-reliability-verified.log`。
- 首次默认运行发现一个旧预算 mock 缺少数值采样，首次原生全跑发现一个合成测试中的四个子案例使用空语音配置。修正两处夹具后，完整原生回归通过。
- 故障注入和并发专项 11 项通过。逐帧对比专项 6 项通过。完整原生回归包含 Video Review 9 项、Blender 场景见证与 Eevee 重渲染。F821、Remotion TypeScript 与 Git 差异检查通过。
- 沙箱 Eevee 首次尝试遇到 `GRAPHICS_INIT_ERROR` 和 `no default Metal device available`，原生执行后既有 Eevee 夹具 10 项通过、1 项因缺历史本地资产跳过。诊断保留于 `output/render-diagnostics/three-d-fixture-e9jys_to/result.json`。

## 依赖与验证范围

新克隆使用锁定的 Python 环境和 FFmpeg/FFprobe 执行基础回归和自动生成的媒体夹具。封面几何测试明确注入测试字体，优先使用 DejaVu Sans 或系统 Arial，也可设置 `MVN_TEST_FONT_PATH`。批准字体检验需要 PingFang SC Medium。封装帧率和时钟仍按完整媒体检查，错位帧专项直接核对真实解码时戳。

可选生产集成按依赖运行。以下两条命令需要本地 Blender，Eevee 重渲染在 macOS 上需要可用的 Metal。测试通过现有 Blender 运行器和文件锁执行。

```sh
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -p test_provenance_witnesses.py -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -p test_three_d_only.py -v
MVN_TEST_AUDIENCE_RENDER=1 uv run --locked python -m unittest discover -s tests -p test_audience_render.py -v
```

历史资产测试需原任务的冻结配置、装配、交付 MP4 或缓存目录。历史封面检查需要 `output/` 中的实际封面，缺失时单独跳过。可选 Remotion 浏览器渲染与真实成片连续视听未执行。真实 TTS、外部服务和平台环境未验证。来源审计覆盖几何投影和采样帧，遮挡与机械因果的感官结论仍由独立审片给出。已发出的 HTTP 请求在返回前仍遵守请求超时及不可重发标记。Linux FFmpeg 7.1.5 尚无本轮运行结果。

## 工作区文件

- 执行和交付涉及 `mechanical_video_next/workflow.py`、`mechanical_video_next/blender_runtime.py`、`scripts/common.py`、`scripts/produce.py`、`scripts/clean.py` 和 `scripts/environment.py`。
- 媒体检查和来源涉及 `mechanical_video_next/media_revision.py`、`mechanical_video_next/video_review.py`、`mechanical_video_next/joint_timeline.py`、`mechanical_video_next/provenance.py` 和 `blender/provenance_audit.py`。
- 配音和缓存涉及 `mechanical_video_next/audio_acceptance.py`、`mechanical_video_next/audio_timeline.py`、`scripts/narration.py` 和 `config/cache-code-equivalence.json`。
- 新增回归和夹具为 `tests/test_reliability_repair.py`、`tests/test_provenance_witnesses.py`、`tests/fixtures/provenance_motion_scene.py` 和 `tests/fixture_fonts.py`。
- 更新既有回归 `tests/test_asset_import_duration.py`、`tests/test_audio_timeline.py`、`tests/test_cleanup_lock.py`、`tests/test_cover_detail.py`、`tests/test_covers.py`、`tests/test_film_integrity.py`、`tests/test_growth_report.py`、`tests/test_hd_workprint.py`、`tests/test_media_revision.py`、`tests/test_narration.py`、`tests/test_production_contract.py`、`tests/test_qa_images.py`、`tests/test_remotion_editorial.py`、`tests/test_source_supported_render.py` 和 `tests/test_text_layout.py`。

## 7157bb0 复核补修

本轮从 `7157bb0d81f6f5623547179fdcc57a9d1c681981` 开始，工作区干净。使用 macOS 27.3 arm64、uv 0.9.16、锁定的 Python 3.14.2、FFmpeg 9.0.2 和 Blender 5.3.0。Linux FFmpeg 7.1.5 的复核结果来自外部环境。

### R7 阶段授权覆盖来源文件

修复前，真实镜头校验通过后，`manual.json` 缺席授权清单。模拟子进程通过启动前复核，在写好合成收据后修改来源，父进程未抛出授权错误。缺口涉及来源采集和执行完成登记。`verified-shots` 子进程原有的启动检查继续执行。

`scripts/common.py` 负责文件哈希和 JSON 读取的授权采集。JSON 登记所解析字节的哈希，绑定校验与解析阶段再次读到不同内容时立即拒绝。来源、模型、数值清单、研究依据和适用的审核配置经现有校验器登记。采集保留调用方路径和解析后的路径，可识别符号链接改指。`produce.py` 与涉及门禁的验证器使用同一 `scripts.common` 上下文。来源或配置在执行期间改变时，`workflow.py` 拒绝登记有效成功，并在 `stage_output_rejected` 事件中记录原因、日志及授权凭据路径。镜头产物和执行日志留存。阶段日志和本次生成的收据属于执行产物。

`test_verified_shots.py` 用真实来源、模型、清单和授权校验覆盖文件变化、缺失、符号链接改指和正常登记。执行中变化测试以合成收据代替昂贵渲染，走实际父进程登记代码。`test_reliability_repair.py` 继续覆盖排队期间配置、证据、QA 变化及真实锁行为。

### R6 裁剪面的主体见证范围

修复前，实际范围函数在近、远裁剪面相交的数值夹具中均只返回另一零件的 `[0.7, 0.4, 0.8, 0.6]`。同一相机移动夹具在主体由完整可见变为部分可见时返回空范围。非有限点也会被跳过。

`blender/provenance_audit.py` 使用当帧求值的包围盒，在投影前计算近、远裁剪面的交点。透视或正交投影后的凸包与画面边界相交，范围由实际相交部分推导。完全不可见时返回空范围，无法得到可靠数值时带对象和帧位置拒绝。每个见证帧的算法只访问包围盒及有限交点。逐帧运动检查继续使用上一轮的求值策略。

修复后，两种深度裁剪数值夹具都覆盖 `[0.05, 0.4, 0.8, 0.6]`。专项还验证了左右、上下画面边界、相机移动、不可见主体、非有限数值和完整可见物体。生成的真实 MP4 验证变更仅落在被裁剪主体时，ROI 仍能检出。原生 Blender 用 Eevee 重渲染同一见证帧并渲染隐藏该主体的替代版本，原帧和重渲染一致，替代帧超过现有 MAE 3 阈值。初次沙箱运行因 Metal 不可用退出，其后原生运行通过。[沙箱诊断](../output/render-diagnostics/provenance-clipped-witness-fixture-1zk_bdeg/result.json)

### R8 历史成片默认路径

修复前，真实短成片已经写在隔离项目的 `output/scoped-fixture-final.mp4`，`paths_for()` 却返回缺失的任务目录 `3d/final.mp4`。此前测试用替代的封面和增长验证器，未经过默认入口。

`workflow.py` 的历史成片解析使用当前配置和真实来源门禁，核对成功 final 阶段的配置哈希、媒体哈希、时长、格式和章节覆盖。封面、增长报告、路线 QA 和交付校验共用派生绑定，磁盘台账保留原历史格式。配置、来源或媒体失效会拦截旧输出，已有路线绑定和显式封面来源覆盖保持各自的用途。现有独立 QA、封面、来源证明、增长报告和必交文件门禁继续执行。

`test_source_supported_render.py` 运行真实来源验证、默认媒体解析、封面生成与校验、增长报告生成与校验、状态推进和交付登记。测试使用 FFmpeg 生成的 1920×1080/30 H.264/AAC MP4 和 10 秒技术预览。配置、媒体、来源变化和配置改换均使旧媒体失效。既有普通路线绑定由 `test_growth_report.py` 覆盖。历史交付夹具使用合成独立 QA 记录并替代昂贵的最终来源重放，真实原生重放由 Blender 专项及完整回归中的现有夹具执行。

### 缓存与验证

来源验证键继续包含审计脚本的实际哈希，因此旧 ROI 审计通过记录需要重新验证。仅为 `produce.py` 的公共模块导入调整更新媒体等价条目，保留既有合成键。镜头配方和付费缓存身份保持原有定义。封面与增长报告仍检查各自生成器版本和精确文件。原有历史媒体、资产、账本和失败证据没有移动。

```sh
export UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache
uv run --locked python -m unittest discover -s tests -p test_verified_shots.py -v
uv run --locked python -m unittest discover -s tests -p test_reliability_repair.py -v
uv run --locked python -m unittest discover -s tests -p test_source_supported_render.py -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -p test_provenance_witnesses.py -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -v
uv run --locked --with ruff ruff check --select F821 mechanical_video_next scripts blender tests
git diff --check
```

镜头授权专项 11 项通过，可靠性与排队专项 11 项通过，历史成片专项 5 项通过，原生来源见证专项 8 项通过。最终完整原生回归用时 109.599 秒，共 569 项，564 项通过、5 项跳过、0 项失败、0 项报错。跳过项为 1 项可选 Remotion 浏览器测试和 4 项缺少历史本地产物的测试。F821 与 Git 差异检查通过。[完整日志](/private/tmp/mvn-followup-verified.log)

本轮范围为工具回归与隔离原生渲染。实际成片连续视听、真实 TTS、外部平台、可选 Remotion 浏览器回归和 Linux 运行环境未验证。本轮未改动 Remotion 代码。

## 1a4872d 复核补修

开始时 HEAD 为 `1a4872db47d6693a49669f7fb369253c36aced36`，分支为 `main`，对齐 `origin/main`，工作区与暂存区均干净。运行环境为 macOS 27.3 arm64、uv 0.9.16、锁定的 Python 3.14.2、FFmpeg 9.0.2 和 Blender 5.3.0。基线复现使用同一 HEAD 的隔离源码副本。Producer 执行复现、修改与测试，原生 QA 子会话 `/root/r8_review` 独立审阅 R8 差异，未重复运行测试。子会话 token、费用及额外干预计数未取得。

### R8 配置替换后的旧成片失效

隔离历史账本绑定真实 FFmpeg 生成的 1920×1080/30 H.264/AAC 成片、10 秒来源技术预览、来源摘录、部件清单、当前配置、测量章节和通过 `continue --plan` 登记的计划。通过 `put_handoff` 写入合成独立 QA 数据，执行真实 handoff、精确 MP4、封面、增长报告和状态校验。仅把最终 `provenance.validate` 的 Blender 来源重放替换为测试替代。夹具保留旧路线、阶段、媒体、交接和已登记场景的完整收据，并一次更新配置和全部镜头的配置绑定。新镜头此时等待研究。

基线在旧成片已验收、尚未登记交付时，从配置切换后的 `FINAL_RENDERED` 回到重新生成增长报告后的 `QA_ACCEPTED`。已登记场景在刷新前后均为 `FINAL_RENDERED`，解析和状态仍引用旧 MP4。增长报告递归扫描任务台账时把旧收据引用的 `growth-report.json` 当成输入，重写报告后自身依赖过期，产生 `Growth report STALE: referenced evidence changed`。两种场景分别复现。 [R8 基线日志](/private/tmp/mvn-repair-1a4872/r8-baseline.log)

`workflow.py` 将当前 scoped 配置识别、同配置成功阶段查找和历史媒体拒绝分开。当前阶段用配置哈希、实际来源、镜头绑定、真实文件和章节验证。后续阶段写入明确的 scoped 身份，旧账本沿用技术阶段的媒体哈希及技术预览或工作样片记录推断身份。历史判定对照实际候选路线的媒体，独立于变更后的镜头绑定。缺少当前成片时给出阶段未产出原因。失效时通过 `invalid_evidence` 指出旧阶段被替代，并返回未完成镜头的下一步。QA、默认封面、增长报告及交付共用该判断，历史账本无需补写记录。

`growth_report.py` 将收据、账本中的增长报告指针作为历史输出处理。交付文件清单使用实际通过校验的当前增长报告及其哈希，旧收据仍须匹配原已提供文件。两个替换场景在生成入口、QA 校验和交付入口均拒绝旧媒体，状态保持 `RESEARCH_PARTIAL`，并保留原 MP4、阶段、handoff 和收据。测试还用正常 `route-run` 产生不同哈希的新 MP4，补齐当前 QA 和封面后通过验收与新登记，已登记场景的旧收据保留到新登记前。原有普通路线和 scoped 正常交付门禁通过回归。新路线 MP4 为 FFmpeg 重封装测试媒体，交付仅在隔离任务内登记。 [R8 专项日志](/private/tmp/mvn-repair-1a4872/r8-final.log)

### R8 候选封面默认入口

基线夹具用真实 MP4、当前来源、模型、配置、技术预览和章节，另有与当前配置哈希相同的成功 preview 阶段、已登记的 `outputs.candidate` 和有效封面计划。没有 final 阶段时，`covers.prepare` 经 `growth_report.paths_for` 先抛出 `Current source-supported final stage media is missing`，候选回退未执行。 [R8 基线日志](/private/tmp/mvn-repair-1a4872/r8-baseline.log)

`covers.py` 通过 `current_source_supported_film` 的封面用途解析候选。成功的 final 优先。当前配置尚未成功生成 final 时，候选须有真实 MP4、有效路径和哈希、适用的音频和章节绑定，以及精确匹配当前配置的成功预览阶段。当前配置、来源或已登记媒体失效时给出错误。封面报告在实际来源上记载 `candidate: true`。显式 `source_overrides` 继续按原规则校验。已生成的旧封面报告沿用生成器哈希时效规则。

专项从默认入口生成并校验两张候选封面。删除候选、修改候选、来源或配置都会拒绝。候选封面生成前后的协调状态一致，纯 candidate 的增长报告和正式交付入口均拒绝。有效 final 出现后默认解析使用其阶段媒体。测试全程使用真实 FFmpeg、Pillow 和封面校验。该段夹具无需 QA 或 Blender 替代。涉及 `workflow.py`、`covers.py`、`growth_report.py`、`test_source_supported_render.py` 和 `docs/cover-delivery.md`。 [R8 专项日志](/private/tmp/mvn-repair-1a4872/r8-final.log)

### 来源见证关键部件局部比较

新增 1920×1080 FFmpeg 夹具在两个对角各放置一个 192×108 的主体。按相同 H.264 参数编码完整、删除单个主体和替换其颜色三个版本。基线的总矩形 MAE 分别为 0.0395、2.5692、1.7307，三个版本都通过旧阈值。验证走真实帧解码和见证比较，测试替代仅供给 Blender 场景审计和静态 PNG 见证，并用同字节复制隔离最终合成重放。 [局部见证基线日志](/private/tmp/mvn-repair-1a4872/witness-baseline.log)

`blender/provenance_audit.py` 保留 R6 的近远裁剪平面、投影凸包和画面边界计算。每个部件记录独立投影范围，并在裁剪区内采样相机射线，用首个表面命中确定局部可见范围。完全在画外、没有可见采样或尺寸不足的部件记录证据不足。某一见证帧没有可比较部件时明确拒绝。`provenance.py` 每个见证帧解码两次，在各部件的实际像素范围分别计算 MAE，沿用 3 的误差阈值。报告记录部件、像素区域、MAE 和比较结果，失败信息提供镜头、帧、部件、区域和阈值原因。总矩形仍参与检查。采样可见性体现首个几何表面，透明材质和不足 8×8 的小区域没有独立的像素级可见性证明。

数值回归保留原有近远裁剪、相机移动、画面边界、不可见与非有限数据检查，并验证分离的部件区域。真实编码完整样片通过，删除和替换均由部件比较拒绝。原生 Blender Eevee 专项实际重渲染近裁剪主体与另一主体。相同场景的编码版通过，仅隐藏裁剪主体的版本定位该部件并拒绝，后置被遮挡部件报告证据不足。初次沙箱运行保留了 Metal 初始化失败，当前登录会话通过项目启动器及现有锁运行成功。专项 11 项全部通过。 [沙箱诊断](../output/render-diagnostics/provenance-clipped-witness-fixture-olc9vf7i/result.json) · [原生专项日志](/private/tmp/mvn-repair-1a4872/witness-native.log)

见证版本加入验证缓存键及收据，累计矩形的旧 PASS 必须重新验证。缓存命中与重新验证采用同一个 MP4 路径和哈希检查，章节元数据不改变媒体身份。测试在隔离目录构造旧版本收据，验证它不会命中新比较。媒体、模型、镜头和合成的生产缓存键沿用原有定义。涉及 `blender/provenance_audit.py`、`mechanical_video_next/provenance.py`、`tests/test_provenance_witnesses.py` 和 `tests/fixtures/provenance_motion_scene.py`。

### 回归命令与范围

```sh
export UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache
uv run --locked python -m unittest discover -s tests -p test_source_supported_render.py -v
uv run --locked python -m unittest discover -s tests -p test_provenance_witnesses.py -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -p test_provenance_witnesses.py -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -p test_three_d_only.py -v
RUN_BLENDER_TESTS=1 uv run --locked python -m unittest discover -s tests -v
uv run --locked --with ruff ruff check --select F821 mechanical_video_next scripts blender tests
git diff --check
```

第一次完整原生回归在 `test_three_d_only.test_blender` 报错。Blender 嵌入式 Python 导入 `provenance.py` 的媒体合成函数时缺少 Pillow。将图像依赖移至宿主的帧比较函数内。三维专项复跑 10 项通过、1 项跳过，覆盖实际 Eevee 重渲染、全片来源重放、平面伪造和替换媒体拒绝。 [首次完整日志](/private/tmp/mvn-repair-1a4872/full-native.log) · [Blender stderr](../output/render-diagnostics/three-d-fixture-drozhyox/stderr.log) · [三维专项日志](/private/tmp/mvn-repair-1a4872/three-d-native.log)

最终完整原生回归耗时 118.144 秒。572 项中 567 项通过、0 项失败、0 项报错、5 项跳过。跳过 1 项需要本地 Remotion 浏览器的测试和 4 项依赖历史本地交付、Blender 动作证据、冻结风格输入和旋转拖把缓存产物的测试。来源授权、文件变化、符号链接改指、父进程最终登记拒绝、媒体帧数和原有 R6 裁剪面回归均通过。F821 与 Git 差异检查通过。 [最终完整日志](/private/tmp/mvn-repair-1a4872/full-native-final.log) · [Ruff 日志](/private/tmp/mvn-repair-1a4872/ruff.log)

实际机械成片的连续视听、真实 TTS、外部发布和 Linux 环境未验证。本轮测试使用隔离产物，代码与报告留在本地工作区。
