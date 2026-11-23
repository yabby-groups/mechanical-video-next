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
