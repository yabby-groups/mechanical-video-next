# Unified visual evidence preprocessing

## Audited paths

| Path | Existing behavior | Integration |
|---|---|---|
| workflow.py / role handoffs | source image paths, immutable JSON | compressed bounded visual_evidence in envelope, production payload untouched; rejects inline image data |
| scripts/produce.py / Blender keys | retained original PNG frames, content caches | qa-images.json for selected existing keyframes, on cache hits too |
| scripts/layered.py | three original key PNGs | shared make_shot wrapper creates compressed evidence |
| scripts/style_preview.py | calls make_shot | inherits shared evidence generation |
| scripts/cad_preview.py / cad.py | geometry/config then existing renderer | numerical geometry unchanged; shared renderer evidence and CLI for external CAD snapshots |
| multiroute.py | comparison preview.jpg | compressed preview in report, corrupt/missing image remains UNKNOWN |
| covers.py | formal PNG candidates and two final PNGs | separate cover previews in report, originals unchanged |
| viral.py / reference_library.py | observations and source bindings | shared CLI for downloaded screenshots/video event frames; role instructions require cache paths |
| .codex/agents and .agents/skills | agent-directed tool reads | all roles use same API and cache; no role-specific compression |

No existing base64 image transport implementation was found in the audited Python entry points. The host image tool is external to this repository: these changes cannot intercept arbitrary manual tool calls or enforce context deduplication across independent host sessions. Handoffs use paths; they do not embed pixels. Cache content deduplication is distinct from actual image-read accounting.

## Usage

`uv run python -m mechanical_video_next.qa_images IMAGE --sheet`

`uv run python -m mechanical_video_next.qa_images VIDEO --times 0 12.5 30 45 --sheet`

`uv run python -m mechanical_video_next.qa_images COVER --cover`

`uv run python -m mechanical_video_next.qa_images IMAGE --crop 100 100 600 450`

Crop coordinates use EXIF-oriented original pixels. The tool never silently substitutes a full-resolution image. Overview maximum 1024px, sheet 1280px, cover 1200px, crop 1600px. Encoding starts at quality 80 and decreases to 35 under a 300000-byte budget; impossible budgets fail and request a crop. This limit is a byte budget, not a guarantee of readable text or contact detail. RGB conversion composites transparency onto white. Production inputs are never overwritten. Crop is explicitly bounded and never stretches geometry.

Every round permits four frames and one sheet; contact sheets contain at most sixteen representative images. For long media the Producer must choose chapter/action events, then make additional bounded rounds as needed. This does not establish continuous review. Deterministic full decode, timing/codec checks and CAD/animation motion checks remain in the existing pipeline. No static-image tool grants PASS.

`record_reads` records successful host reads when called by the consumer, not preparation attempts. Byte totals, dimensions and formats are observable; visual token usage is unavailable. Identical cache paths do not prove the host avoided resending an image.

## Real validation

Run `uv run python scripts/validate_qa_images.py`; detailed source and output hashes, sizes and timings are in work/qa-images/validation.json. The measured run used six existing route/CAD/cover images: 1276147 original bytes, 85308 compressed bytes, 100% repeat-cache hits. Original files unchanged. Initial six-image preparation took approximately 0.385 seconds across cold/warm runs; timings are cache-state dependent; use the JSON for the latest run. No production video rerender, voice change or source resolution change occurred.

Two actual host reads used WebP only (actual-reads.jsonl): overview plus title crop. The Chinese title was legible in the crop; fine mechanical contact remains UNKNOWN. This is not scientific acceptance or comprehensive continuous viewing. The source JPEG/PNG images and final video bytes are preserved. Tests exercise actual project renders and a real final video, not only synthetic fixtures.

## Limits and follow-up

Unreadable-region detection and semantic selection of motion events require agent judgment: the API supplies bounded crops, not a fabricated readability classifier. A future host integration could make successful read logging mandatory and enforce cross-session image deduplication. Missing or insufficient evidence stays UNKNOWN. Existing historical QA is not retroactively rewritten. The shell CLI returns evidence packets; it cannot force external CAD viewers/browser screenshot tools to render compressed pixels before the agent sees them. Export their screenshots and pass through this entry before further review.

## 机械画面诊断

在低成本动稿和正式 MP4 上各做一次。先用 `--overview` 生成全片窄屏播放和可用的镜头区间。边看边检查产品及完整工作循环，主动标记出乎预期的配件、方向、悬浮、穿模、失联、传动和旁白矛盾。没有播放能力时记录抽样覆盖。已有运动预演窗口可作为线索，接触、啮合、锁止、释放、反转、复位、装拆和行程转折还要按实际发生位置选择。

```sh
uv run python -m mechanical_video_next.visual_diagnosis film.mp4 --overview --directory work/diagnosis/overview
uv run python -m mechanical_video_next.visual_diagnosis film.mp4 --at 12.5 --directory work/diagnosis/detail
uv run python -m mechanical_video_next.visual_diagnosis film.mp4 --frames 370 374 379 --window 367 389 --crop 800 220 1220 700 --zoom 2 --model --directory work/diagnosis/contact
```

时钟使用从零开始的 30 fps 解码帧，窗口终点不含在内。局部坐标是实际解码画面的左、上、右、下像素。查看 JSON 中的 `images[].qa_path`，保留一张带周边机构的原尺寸画面，再在同一区域观察动作前、中、后。裁剪发生在放大前，倍数只改变显示尺寸。动稿原生像素不足时，可从同一姿态渲局部诊断。单批最多 16 张，事件片段最多 300 帧。

正式入口的 MP4 收据绑定镜头、裁切偏移、动稿重复步长、原始场景和依赖哈希。使用 `--model` 时，一次选择同一镜头内的帧。先读默认的对象求值结果，按裁剪位置查看原相机投影范围、对象、父层级、网格、变换和动画驱动线索。投影框会包含遮挡对象。多画面拼接、重构图和缺少来源映射的旧片需要核实到实际相机与帧，再用 `--blend scene.blend --blend-frames 101 105 109` 提供旧场景。复核场景结果时读取 `blender.poses[].image.path`。

`--view camera` 可重放原相机的局部画面。用 `--view front`、`side` 或 `top` 加 `--objects` 为部件做固定正交特写。可通过 `--hide` 移去既有外壳，通过 `--isolate` 只显示选定部件，或用 `--xray` 查看重叠。优先选择足以解释接触的一种视图和少量姿态。诊断相机、可见性和渲染改动只在临时 Blender 进程中生效。

显式指定的网格还提供八个最大求值面的位置、法线和面积。可用它们对照模型的开合方向，找到可能先接近相邻件的斜面或平面。法线符号受网格绕序影响，首次接触仍需核对相邻几何和前后运动。

从疑点图片追到源对象、驱动和型号资料。修复后用 `--baseline old.mp4` 对同一剪辑时钟、相机及裁剪区域生成修复前后的逐帧与动态材料。剪辑时钟变更时，记录两个版本对应的源动作及各自时码，再用匹配姿态对照。复看实际编码画面，检查原问题、相邻状态和新异常。记录实际看到的画面、时段、判断与余下疑点。工具生成的材料将连续观看保留为 UNKNOWN。

局部清楚以后，沿真实机构的输入、相邻界面和输出逐段追查。先问哪个表面在当前运动方向上先受力，或介质必须从哪个孔穿过哪一道零件边界。用动作前、中、后的姿态和型号资料核对具体答案。正交图上形状相叠只提示下一处观察位置。补充视角保留相邻配件及运动方向，直到疑点定位到具体配件、几何或驱动，或明确记录缺少哪段场景或哪项型号证据。

对外形和装配直接影响正确性的零件，开看前先用本集的实物或原厂资料建立可核对的参照。开场、拆装和工作行程中复用同一接口时都要比对。历史录像、截图盲测、同机位局部修复与实际成片映射见[自主机械视觉诊断复盘](productions/visual-mechanical-diagnosis-20261126.md)。
