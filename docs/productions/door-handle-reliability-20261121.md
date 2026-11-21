# 门把手回正与斜舌扣合｜故障定位和修订验收

当前修订为 97.666667 秒、768×432、30 fps 的完整 Blender 动稿。使用同一门锁任务，保留 59.133333 秒原片与各轮失败证据。修订动稿 SHA-256 为 `97310f4f06d5a6a9b155d7a7ca6d1c9944d1c56f5641234ef6813bfeca0885fc`。独立连续视听和 1920×1080 终版是待完成的交付项。 [原片](../../output/tasks/door-handle-return-20261121/complete-door-cycle/门把手回正-完整门锁循环.mp4) · [修订动稿](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/door-handle-workprint.mp4) · [同期动作对照](../../output/tasks/door-handle-return-20261121/reliability-audit/old-vs-v2-motion.mp4)

## 根因与 Director 对照

| 检查项 | 结果 | 首次出现的位置与证据 |
| --- | --- | --- |
| 旧版关门斜舌反向与突缩 | FAIL | 原生 Blender `NOSE` 轮廓把弧面放在运动的后侧。`latch_stroke()` 的位移纠正使第一个接触样本从 `0` 跳到 `0.242708`。文件的实际第 1,221 帧对应约 40.667 秒。 |
| 开门至关门的跨镜状态 | FAIL | Blender `TRACKS` 中旧 `press`、`release` 的门角恒为 `0°`，关门镜头一开始便变为 `7.6°`。时间轴没有这次开启的可见过程。 |
| 双把手轮廓 | FAIL | 两个轮廓来自装在门两侧的真实独立把手对象。去掉门板以后，它们在 18、29、36.9 秒的剖视里投影到一起，丢失了装配方位参照。修订拆解明确提示近侧、远侧共用方轴，按压与回位剖视保留近侧。 |
| 合成裁切和固定时长 | PASS | 任务时长上限为 `null`。59.13 秒原片 1,774 帧完整解码，原生记录与帧数、18 段 Neil 和最后一句相符。已保存的 FFmpeg 合成脚本按 30 fps 顺序取帧。原命令 stderr 缺失。 |
| 原片故事 | FAIL | 原旁白有两条驱动路径，`story.json` 和 `edit.json` 从入孔直接接外景复演，缺少反拉时斜舌平面为何保持扣合与重新下压后怎样脱扣。开场问未按把手为何也能缩舌，画面留给关门动作的观察时间不足。 |
| Director 历史执行 | UNKNOWN | `task.json` 启用了导演版本，其 `handoffs` 和 `stages` 为空。现场留存的是原生 Blender 命令与 FFmpeg 合成脚本。Research handoff、冻结 Blueprint、Visual Planner、正式编译配置、原合成 stderr 无绑定可追；原生网格和轨迹已足以定位已证实的机械故障。 |

同一原片的关门镜 380 帧用于最小成本实验。A 用原轨迹，B 通过现有 Director 适配器改机位。两者 380 个源帧顺序、首个缩舌值、1,774 帧总长、旁白 IDs 和知识点完全一致。C 注入一条导演权限可以表达的时间映射，模拟在总长相同的情况下加速前半段。按最近样本回查只会读到 274 个不同源帧，首次缩舌输出由零基第 1,220 帧提前到 1,163 帧。该诊断能复现旧权限的潜在风险，现有保护明确拦截。C 的映射为实验注入，历史任务实际导演配置仍为 UNKNOWN。 [A/B/C 日志和逐帧映射](../../output/tasks/door-handle-return-20261121/reliability-audit/director-experiment.json) · [两轮失败的实体复审](door-handle-mechanical-audit-20261121.md)

旧 QA 对原片做了独立解码、来源哈希、音轨和 41–49 秒四个样本，已经把科学、完整叙事和连续视听列为 UNKNOWN。有限的技术结果允许任务外的合成脚本生成可观看 MP4。台账未完成正式 QA 或交付。当时的运动检查使用作者安排的同步数值与简化的二维间隙，没有检查与可见扣板、木料和弹簧求值实体的关系。 [旧片独立 QA](../../output/tasks/door-handle-return-20261121/complete-door-cycle/independent-final-qa.md) · [原始任务台账](../../output/tasks/door-handle-return-20261121/task.json)

## 机构修订与观察窗口

Emtek CF 2.0 通道门型的原厂手册第 2 页 §4B 规定关门先碰弧面。第 1、3、4 页支持两侧回位组件、饰盖、贯穿轴和斜舌总成以及把手向下操作。旋转方向、装配、门板和扣板凹位按该来源约束。自定义拨轮、拉片、弹簧锚点及入孔回弹节奏是这次采用的原理演示，片中按压和回位标注「传力原理示意」。厂商内部形状、材料、真实回弹速度与接触力均为 UNKNOWN。 [原厂手册](../../output/tasks/door-handle-return-20261121/complete-door-cycle/research/emtek-cf2-installation.pdf)

| 故事和机械状态 | 原片时间 | 修订时间 | 验证 |
| --- | ---: | ---: | --- |
| 提问并展示斜舌两次回缩 | 0–6.57 秒 | 0–8.50 秒 | 画面提出把手回正问题，Neil 提问关门为何也缩舌。开场从关门开始，退舌、开门、松手、闭门均在同一个镜头中。 |
| 展示装配、方轴与回位组件 | 6.57–16.30 秒 | 8.50–21.47 秒 | 源模型在拆解末尾重新装配。定点确认近远把手标识。 |
| 下压、方轴传力、缩舌、开门 | 16.30–25.63 秒 | 21.47–35.63 秒 | 源帧 911 的把手约 37°，斜舌退至门板边缘内约 0.005525 场景单位。门扇随后开至 8.5°。 |
| 松手回正，斜舌弹出 | 25.63–37.23 秒 | 35.63–52.13 秒 | 把手从 37° 回到 0°，斜舌行程 `0.505525 → 0`，门保持 8.5°。原理模型压簧最小轴向圈距约 0.071119，线径 0.058。取样的弹簧与座接合体积和真实结构仍待验证。 |
| 斜面接触、缩入、弹出入孔 | 37.23–49.90 秒 | 52.13–70.60 秒 | 把手全段保持水平。源帧 1,732 首缩 `0.001782`，2,007 帧达峰值 `0.317504`，2,019 帧完全伸出。木框设实体孔位，回弹曲线为 12 帧演示节奏。 |
| 反拉止动、再按把手开门 | 缺段 | 70.60–86.10 秒 | 预留木孔加宽，保持钢扣板开口。停在约 0.49116°。将门沿开启方向额外转 0.02°，钢扣板有 8 个 BVH 表面交叉候选，木门框为 0。停点与前移 0.02° 两个样本均为 0。该检查定位模型中钢扣板限制的位置，测不到受力。 |
| 复演两条驱动路径、收于扣合 | 49.90–59.13 秒 | 86.10–97.67 秒 | 明示「从关门状态复演」。独立 QA 看到此提示，最后外景看不清扣孔，扣合证据出现在前面的剖视。 |

源帧 1,069→1,070、1,564→1,565、2,118→2,119 的门角、把手角度和斜舌位移吻合。最后一次切换由门已开 6.2°、把手下压 37°切到关门状态，实际画面明示复演。原片和修订版并排对照把两版第一次缩舌对齐至对照片第 16 帧。原片一侧在素材切点后定格并标明。 [修订 Blueprint 审片记录](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/creative-blueprint.review.json) · [原生求值几何与钢扣板扰动](../../output/tasks/door-handle-return-20261121/reliability-audit/geometry-v2-evaluated-geometry.json) · [原生逐帧轨迹](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/motion-frames.json)

## 旁白与故事覆盖

原片 18 段 Neil 的文本、音频输入哈希与顺序全部保留。补充 5 段，包括反拉判断及片尾把手回正。23 段均按实测 PCM 放入各镜头，最终像帧与音轨总时长一致。最低参考信噪比约 18.11 dB。末句「到孔口，它自己弹进去」在 95.333333–97.380167 秒，后留 0.287 秒画面。故事问题、方轴传力、两个弹性元件、扣板驱动、复演回报均有旁白链接与实渲图片窗口。技术覆盖 PASS，完整视听效果和主观理解 UNKNOWN。 [逐句与逐镜前后时间轴](../../output/tasks/door-handle-return-20261121/reliability-audit/timeline-and-speech-comparison.json) · [实际 MP4 帧时戳及音频核对](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/door-handle-workprint.verification.json)

用现有 Remotion 渲染器按七个镜头的源偏移重放这条动稿，重新混入实测 Neil PCM。重放验证 2,930 帧和完整旁白。每帧与缩至相同分辨率的 FFmpeg 动稿比较，最低 SSIM 为 0.981518，末帧为 0.993493。 [Remotion 核验](../../output/tasks/door-handle-return-20261121/reliability-audit/remotion-replay-verification.json) · [逐帧日志](../../output/tasks/door-handle-return-20261121/reliability-audit/remotion-replay-ssim.log)

## 通用门禁和验收状态

- **Mechanical Truth / Cross-shot Continuity**。每个关键动作必须声明来源、方向、初末与中间状态、驱动与接触。Blender 镜头绑定轨迹、插值、运动驱动、约束和原生帧数。跨镜延续同一动作的程序和时钟必须一致。镜头能调整摄影，动作保护区间保持源帧顺序。
- **Timeline Integrity**。实测 Neil 先决定旁白窗口，蓝图与执行配置必须一致。Remotion 合成前核对总帧数并从正确源偏移开始。合成和缓存命中均核对 MP4 的实际每帧时间戳、逐段 PCM、尾句和全片解码，技术失败留在待核验产物上。
- **Narrative Completeness**。故事结构把问题、首次发现、因果解释、结果和结尾绑定到画面与旁白。现有独立动稿 QA 和终版 QA 要在对应 MP4 哈希上覆盖全部关键动作和故事窗口。有开放缺陷或缺失观察证据时，技术指标无法代替观察。规则适用于新启用 `film_integrity_version=1` 的 Producer 任务。该历史任务的视频修订沿用实际独立 Blender 场景和 FFmpeg 编辑，任务台账尚无冻结交接。
- **自动测试 PASS**。515 项中 509 项通过、6 项跳过。覆盖运动反向、约束变更、跨镜更换程序和重设时钟、元数据合格但单帧时戳错位、旁白超窗、尾句静音、合成过短及漏审片尾。Remotion TypeScript 类型检查和 `git diff --check` 通过。 [测试日志](../../output/tasks/door-handle-return-20261121/reliability-audit/tests.log)
- **独立 QA UNKNOWN**。复核了新版 2、30、43、63、73.1、77、86.1 和 96.5 秒及整片技术解码。接触可见性、整片听感与连续动作仍缺连续观察。依本任务指定的阶段顺序，连续视听未取得独立 PASS，本轮新增修订的 1920×1080 输出待此关关闭。 [独立 QA 报告](../../output/tasks/door-handle-return-20261121/geometry-repair/independent-audit-this-turn.md)

动稿画面来自本任务自建 Blender 场景，原厂资料仅用于核对，外部媒体区间为空。两个审片封面复用同一原生拆解板，已检查模板边界和字形。 [来源与媒体哈希](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/media-provenance.review.json) · [3∶4 封面](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/封面-3比4.png) · [4∶3 封面](../../output/tasks/door-handle-return-20261121/geometry-repair-v2/封面-4比3.png)
