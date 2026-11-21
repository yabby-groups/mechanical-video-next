# 门把手回正｜故障定位与修复验收

**复审结论更新。** 97.67 秒版本的机械验收为 `FAIL`。斜舌朝向已在模型中翻转，但实心门板与门框、压簧自相交和未证实的接触传力使该版本不能作为正确示范。以下保留此前的时间轴、媒体与旁白核对记录。 [整片机械复审](door-handle-mechanical-audit-20261121.md)

任务 `door-handle-return-20261121`。以 `complete-door-cycle` 的 59.133333 秒高清审片版为故障基线。它包含原来六个镜头和 18 段实测 Neil 旁白，也是上一轮独立 QA 核对的版本。修复审片版为 97.666667 秒、2,930 帧，分别输出 768×432 和 1920×1080，两版均为 30 fps。任务状态仍为 `CREATED`，连续视听和正式交付待验收。 [原始 MP4](../../output/tasks/door-handle-return-20261121/complete-door-cycle/门把手回正-完整门锁循环.mp4) · [完整工作片](../../output/tasks/door-handle-return-20261121/integrity-repair/door-handle-workprint.mp4) · [高清审片版](../../output/tasks/door-handle-return-20261121/integrity-repair/door-handle-hd-review.mp4)

## 故障第一次出现的位置

| 问题 | 首次出现的位置 | 修复和证据 |
| --- | --- | --- |
| 关门时斜舌突跳 | Blender 模型的 `NOSE` 多边形把大斜面放在关门方向后侧。随后 `latch_stroke()` 按相交量纠正位移，使第一次接触直接收回 0.242708 个场景单位 | Emtek CF 2.0 安装手册第 2 页步骤 4B 要求关门时先碰到斜舌弧面。复用这套门扇、扣板、转轴和驱动模型，改正斜舌朝向。第一个接触样本收回 0.000113，之后沿斜面推进。旧版与修订版的接触首帧均放在对照视频第 16 帧。 |
| 动作显得被压缩 | 第一个大幅位移出现在旧 Blender 轨迹的第 1,221 帧，成片约 40.667 秒。旧 `CLOSE` 和 `payoff` 的时间在运动脚本中直接编排，主关门段从接触到最大收回只留 98 帧。修订主关门段从接触到最大收回用 261 帧 | 改正几何，再重排可见接触窗口。修订片按 Blender 帧序号逐一合成，解码得到 2,930 帧。原片图片和音轨均为 59.133333 秒，已记录的 FFmpeg argv 及逐帧记录支持按原速输出。实际查到的是模型位移突跳与源轨迹编排形成的压缩效果。 |
| 故事收尾缺一段 | 旧 `story.json` 和 `edit.json` 从斜舌入孔直接跳到外景复演，未安排反拉门时斜舌平面承力、门仍被扣住的镜头。49.8 到 50.2 秒之间发生这次切换 | 增加反拉受挡与再按把手开门两个动作。外景结尾明确标示复演，整体回看开门、回位、关门扣合。原片最后一句 PCM 已播放，故障首先在故事规划。 |

机械突跳和局部动作节奏共同受 Blender 原生模型与运动脚本影响。故事缺段来自脚本和镜头表。三项的流程缺口相同，原任务台账未登记 Research handoff、Blueprint、编译配置或 stage，无法从这些阶段追溯出更早的修改。现存研究笔记、`story.json`、`edit.json`、`.blend`、帧序列、动稿、QA 与 `compose.py` 已按 SHA-256 绑定。原合成 stderr 日志缺失，原命令来自现存脚本。修订合成的命令与日志均已保留。 [跨阶段证据](../../output/tasks/door-handle-return-20261121/integrity-repair/trace.json) · [机构来源](../../output/tasks/door-handle-return-20261121/corrected-door-mechanics/research/机构依据.md) · [动作对照 MP4](../../output/tasks/door-handle-return-20261121/integrity-repair/motion-comparison.mp4)

旧 `press` 和 `release` 的门角恒为 0°，下一镜 `strike` 开始时直接变成 7.6°。这次跨镜缺段在 Blender `TRACKS` 就已出现。修订的 `press` 先退斜舌再转门扇，`release` 保持门扇敞开。`strike` 用新机位和「关门」说明下一次施力。`catch` 结束时门已经打开，接到 `payoff` 的关门初始状态时明确打出「从关门状态复演」。 [动作轨迹与切镜记录](../../output/tasks/door-handle-return-20261121/integrity-repair/trace.json)

## 故事和时间轴

| 镜头 | 基线秒 | 修订秒 | 画面与解释 |
| --- | ---: | ---: | --- |
| `hook` | 0–6.57 | 0–8.50 | 下压开门，提出关门时未动把手为何斜舌也会缩回 |
| `explode` | 6.57–16.30 | 8.50–21.47 | 分解贯穿方轴、饰盖下的回位件和斜舌总成 |
| `press` | 16.30–25.63 | 21.47–35.63 | 把手经方轴、拨轮和拉片带动斜舌缩回，门扇随后开启 |
| `release` | 25.63–37.23 | 35.63–52.13 | 扭簧回正把手，压簧推出斜舌 |
| `strike` | 37.23–49.90 | 52.13–70.60 | 斜面先接触扣板，斜舌缩回再进孔。辅视图跟踪把手保持水平 |
| `catch` | 缺段 | 70.60–86.10 | 回拉时平面挡在扣板上，随后按把手再次开门 |
| `payoff` | 49.90–59.13 | 86.10–97.67 | 外景复演开门、回位、关门扣合。最后一帧保留关门状态 |

输出时间轴精确到半开帧区间。技术核对使用完整 MP4，画面定点覆盖拆解、下压、回位、斜面接触和入孔、反拉止动、再次开门及最后一段复演。按每个事件记录 `mechanical_event_id`、`shot_id`、`knowledge_id`、原生帧与输出帧区间、关联旁白和首末姿态。修订使用已修正的原生 Blender 画面重新合成，覆盖 2,930 张连续原生板，预览与高清共享板序列哈希。 [时间轴和事件映射](../../output/tasks/door-handle-return-20261121/integrity-repair/trace.json) · [故事完整性](../../output/tasks/door-handle-return-20261121/integrity-repair/story-completeness.json) · [修订字幕](../../output/tasks/door-handle-return-20261121/integrity-repair/captions.srt)

## 旁白覆盖

两种分辨率输出都有 4,688,000 个解码 PCM 样本，解码 PCM 哈希相同。原片 18 段旁白全部按原顺序复用，逐段核对文本、输入 PCM SHA-256 和样本长度。补充 4 段用于反拉、受挡和再次开启，另加 1 段末尾回位说明。最终一句仍为「到孔口，它自己弹进去」，实际窗口 `4,576,000–4,674,248` 样本，即 `95.333333–97.380167` 秒。尾部保留约 0.287 秒，包含最终关门姿态。整轨逐窗比对覆盖此句，最低参考信噪比 18.11 dB。全部 23 段也已核对 Neil 请求、缓存来源和 PCM 封存。 [工作片旁白覆盖](../../output/tasks/door-handle-return-20261121/integrity-repair/workprint-verification.json) · [高清旁白覆盖](../../output/tasks/door-handle-return-20261121/integrity-repair/hd-review-verification.json) · [Neil 来源记录](../../output/tasks/door-handle-return-20261121/integrity-repair/neil-source-receipts.json)

## 工程变更

| 文件 | 原因 |
| --- | --- |
| `joint_timeline.py` | 校验事件源区间、输出区间和跨镜共用时钟。核对实际解码帧数、AAC PCM 和末句。 |
| `director.py` | 绑定经过验证的驱动、轨迹、约束、旋转插值和源帧数。阻止改变保护窗口的时间映射。 |
| `blueprint.py`、`three_d.py` | 编译时保留原生动作时长。发现剪辑需要更多源帧时明确报错，校验可执行镜头与冻结时间轴一致。 |
| `production_contract.py`、`workflow.py` | 新 Producer-directed 任务固定完整性版本。为原有研究、Blueprint、stage 和 QA 加入事件与故事覆盖验证。用实际 MP4 校验收尾以及每个观察窗口。 |
| `scripts/produce.py`、`remotion_build.py` | 锁定动作的低清原生源保持 30 fps。分开源镜头长度和输出切分长度。Remotion 核对总帧数，合成及缓存命中后复验媒体。 |
| `tests/test_film_integrity.py`、`tests/test_production_contract.py`、`tests/test_review_observations.py` | 回归覆盖反转、压缩、动作裁切、跨镜重置、尾句静音、旁白超窗、`-shortest`、缺少解释、实际收尾缺失和导演覆盖约束。 |

检查了 `duration`、`time_map`、源区间、帧数取整、Remotion `durationInFrames`、FFmpeg `trim`、`concat`、`shortest` 与 `-t`。历史独立脚本、对比片和任务专用 FFmpeg 路径保留原策略，保护范围为启用新完整性版本的现有 Producer 主线。门把手修订沿用其实际本地 Blender/FFmpeg 来源，并独立执行主线使用的解码与 PCM 核验。导演可以在保护区间外使用合法视觉时间映射，保护区间当前保持与原生帧一一对应。

另用现有 Remotion `visualEntry` 按七个真实切点重放完整工作片画面，与同一 Neil PCM 重新混流。重放片解码为 2,930 帧，逐帧对应，最低 SSIM 0.991660，最后一帧 0.996878。AAC 逐窗对照覆盖最后一句，尾部多出的 880 个样本在编码填充容差内。此验证走真实 Remotion 渲染器。任务仍缺冻结交接和正式 stage 产物。 [Remotion 重放核验](../../output/tasks/door-handle-return-20261121/integrity-repair/remotion-full-check.json) · [逐帧比较](../../output/tasks/door-handle-return-20261121/integrity-repair/remotion-frame-comparison.log)

## QA 与正式交付状态

| 项目 | 状态 |
| --- | --- |
| 工作片及高清审片版全片解码、帧率和时长 | PASS |
| 18 段原旁白与 5 段补充 PCM 覆盖，末句与片尾 | PASS，具体样本区间已落盘 |
| 几何朝向与源轨迹 | 通过该原理模型的数值检查和实际画面取样。旧版突跳在接触帧已显著减小。约 67.0 秒的斜舌入孔仍按间隙判定在相邻帧完成回弹。源资料无回弹高速测量，真实回弹速度、接触力、内部尺寸及实际锁体几何仍为 UNKNOWN |
| 画面表达和故事 | 定点核对所有七段，包括重新构图的平面止动和外景结尾。连续动作、跨镜主观连续性、接触可读性及听感为 UNKNOWN |
| 独立与正式 QA | 现有独立 QA 是旧版或前版动稿。当前两个新 MP4 缺少整片独立连续审看和实际听审。任务缺冻结交接链及正式 stage 产物，继续保留为审片状态 |
| 来源与权利 | 原有来源记录和封面保留。成片外部媒体区间为空。厂商资料用于参考，涉及封闭机构内部接触的拨轮、拉片及回位件为原创原理示意 |

反拉止动的前版动稿曾被指出局部遮挡。此次低清和高清都取自切开遮挡部位后的同一原生板，76 秒样本能看到斜舌平面与扣板边缘。该观察仍需独立连续审看片段才能关闭原问题。合成和校验绑定了当前精确 MP4 字节，保全两款封面。 [前版独立 QA](../../output/tasks/door-handle-return-20261121/corrected-door-mechanics/independent-workprint-qa.md) · [看图记录及封面哈希](../../output/tasks/door-handle-return-20261121/integrity-repair/trace.json)

全项目 Python 回归执行 512 项，506 项通过，6 项跳过。Remotion TypeScript 类型检查与 Git 空白检查通过。
