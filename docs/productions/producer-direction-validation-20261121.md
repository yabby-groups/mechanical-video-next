# Producer 创作与视觉验证 · 2026-11-21

## 审计

核对本地 `main`、`origin/main` 与远端 `refs/heads/main`，三者均为 `7a7b1a6`。开工时只有未跟踪的运营复盘计划。选择雨伞作为完整回归，因为已有可回放的 74.333 秒 MP4、Neil 原句、逐镜画面和机构来源。选择修正带的轮缘与摩擦环接触作为局部回归。皂液泵的历史对照用于审计中段重复剖视，已有完整成片和验收边界。 [雨伞原报告](../../output/tasks/umbrella-teardown-20261120/ending-recut/交付说明.md) · [皂液泵历史复盘](../../output/tasks/soap-creative-first/production-report.md)

| 位置 | 现有证据及根因 | 本轮处理 |
| --- | --- | --- |
| [Producer 提示](../../mechanical_video_next/workflow.py#L1005) · [故事检查](../../mechanical_video_next/production_contract.py#L282) | 默认已要求先定故事，但落到 Blueprint 主要验证问题、答案和事实引用。重述旧事实时，开场现象、首次发现和兑现仍可能没有可定位画面。 | 新立项记录观众切入点和设计矛盾，把四个观察时刻绑定到画面帧区间。镜头目的、整体到局部的关系、观察时间和声画意图随同一 Blueprint 编译。 |
| [Blueprint 编译](../../mechanical_video_next/blueprint.py#L109) · [镜头配置](../../mechanical_video_next/visual_narrative.py#L443) · [摄影棚](../../blender/studio_style.py#L11) | 相机路径、布尔剖视、EAS 和附加相机架已有实现。语义预设的名称本身只影响部分参数。摄影棚可在未明确选定运动时自动推近或统一金属化。已知时长的运动也可能被拉长以配合画面。 | 新版编译关闭隐式推近，可按镜明确调整环境色、灯光和源材质。已有运动长度不足时要求显式编辑。固定包络相机允许在动作前推进并在动作期锁定比例，随几何位置取景。 |
| [相机实验库](../../config/cinematic-shots.json) · [视觉实验](visual-story-validation-20261120.md) | Dolly/Crane、剖切、跟随有真实渲染和工程记录。独立连续视听仍缺证据。历史研究片有独立场景脚本和实际动稿，手工场景的表达依然由 Producer 选取。 | 在现有 Blender 入口加入按帧求值的包络和网格标记投影。新样片继续列为 EXPERIMENTAL。 |
| [Reference Library](../../mechanical_video_next/reference_library.py#L163) · [参考交接](../../mechanical_video_next/viral.py#L252) | 搜索和不可变交接已接通，原则能挂镜头 ID。旧记录缺可验证的技巧时间窗，应用效果很难回到实际媒体。 | 验证技巧区间处于观看范围，记录适用条件、理解作用与实现。原版工作片 QA 直接记录所用技巧在精确 MP4 的对应镜头表现。 |
| [QA 调用](../../mechanical_video_next/workflow.py#L1991) · [阶段](../../mechanical_video_next/workflow.py#L2770) | 本地代码已有工作片入口，但旧版 Producer 导演任务可以没有 `preview-qa` 就进入编辑和最终阶段。技术探测只知道文件、流、时长和来源。 | 新版走原有低成本完整预览和独立 QA，记录已知缺陷与真实覆盖。连续视听缺口可记 UNKNOWN，最终验收按原独立 QA。手动观众审片 Skill 继续用于成片。 |

## 实际动态对照

**雨伞完整影片。** 74.333 → 70.200 秒。删掉首次切入锁扣前 13 帧和片尾 111 帧重复雨中开伞，移除重复开伞中的一句过场。雨景、单组连杆、整环联动、槽和护片、释放、收拢、卡舌伸出及整伞仍撑开都在整片内。保留 22 个实测 Neil 句段。使用原画面帧、原速度与原动作，容器重新编码为 1920×1080/30。 [基线](../../output/tasks/umbrella-teardown-20261120/ending-recut/umbrella.mp4) · [完整低成本工作片](../../output/producer-direction-validation/umbrella-workprint.mp4) · [高清回归版](../../output/producer-direction-validation/umbrella-after.mp4) · [逐镜画面与机构绑定](../../output/producer-direction-validation/umbrella-edit.json)

| 对照 | 原片时间 | 新片时间 | 已核实改动 |
| --- | --- | --- | --- |
| [开场 A](../../output/producer-direction-validation/umbrella-opening-before.mp4) · [开场 B](../../output/producer-direction-validation/umbrella-opening-after.mp4) | 0–7.900 秒 | 0–7.467 秒 | 首次进入卡舌托住滑环由 5.400 提前至 4.967 秒。两版都有同一段原活动作和滑环标注。 |
| [兑现 A](../../output/producer-direction-validation/umbrella-payoff-before.mp4) · [兑现 B](../../output/producer-direction-validation/umbrella-payoff-after.mp4) | 60.333–74.333 秒 | 59.900–70.200 秒 | 删掉重复雨景开伞。锁止剖视由 66.500 提前至 62.367 秒，保留完整 162 帧动作。收拢全景接推环剖视的连续性仍 UNKNOWN。 |
| [修正带 A](../../output/producer-direction-validation/correction-tape-contact-comparison-before.mp4) · [修正带 B](../../output/producer-direction-validation/correction-tape-contact-comparison-after.mp4) | 64.767–77.200 秒 | 0–12.433 秒 | 同一 373 帧机械时钟、同一几何、形变、轨迹、材料与灯光。B 在约 2.24 秒的原有机械停留期收紧取景，随后稳定比例跟随两标记。A 来自历史成片，含原图层。B 为原生静音镜头，低成本采样和文字层有异。 |

**修正带复拍。** 第一次复拍把整个镜头切成极近特写，且把标记对象原点当作投影点。独立抽查发现空间参照不足。第二次复拍保留部分轮辐与外壳作为开场参照，并将两组投影改为求值网格中心。两个中心在全部 373 帧内可投影，关键运动窗口第 68–373 帧共 306 帧，各零脱框。四个抽查时刻均见两色标记。完整整机关系、画中遮挡和相机跟随能否提升理解仍需连续观察。原输入机械轨迹、来源和时钟按字段比对一致。动作范围是 US8746316B2 描述的同型教学运动，约 7.5 mm 规定接触段。实际摩擦、力和整卷速度仍没有物理测量。 [第二版原生样片](../../output/producer-direction-validation/correction-tape-contact-v2.mp4) · [相机配置与场景回执](../../output/producer-direction-validation/contact-v2-render.json) · [机械与媒体比对](../../output/producer-direction-validation/comparison.json) · [独立抽查](../../output/producer-direction-validation/independent-qa.md)

## 参考映射

通过本地现有研究和本轮浏览器播放补查同一雨伞参考。在 1.2、6.2、13.4、21.7 秒可分别看到闭合、局部打开、较大展开和收拢构图，橙色滑环在不同状态仍可定位。适用条件是几个状态共享同一输入件。雨伞新剪辑保留已有原生滑环标注，把同一观察目标从雨景骨架交接到 4.967 秒开始的锁扣剖视，采用更早剪点。参考本身展示滑环和伞骨，锁扣采用本片的 EP0493867A1 图 2–3 实施例。公共视频只作为构图参考。截图证据支持视觉锚点，无法给实际播放节奏、音效、注意力效果或连续动作赋值。该参考保持 `SCREENSHOTS_ONLY`。 [参考作品](https://www.youtube.com/shorts/vEgE-EuyRHo) · [历史研究](../../output/tasks/umbrella-teardown-20261120/research/viral-analysis.json) · [本轮抽帧回执](../../output/producer-direction-validation/public-reference-images.json) · [原生成片对应开场](../../output/producer-direction-validation/umbrella-opening-after.mp4)

## 工程回归与边界

Python 495 项，489 通过，6 跳过。TypeScript typecheck 和单独启动的 Remotion 编码回归通过。真实 Blender 渲染两轮，串行使用已有锁，镜头阶段分别 69.676、74.889 秒。雨伞只合成，低成本工作片约 6.6 秒，高清约 16.0 秒，重用 22 个 Neil 句段，增加零 Blender 渲染与零 TTS 调用。候选全量解码通过，最终 AAC 与原句重新编排的 PCM 样本对齐，响度 −16.9 LUFS、真峰值 −1.4 dBFS。最大报告工作占用约 1.55 GB，磁盘可用约 70 GiB。使用一个独立 QA Agent 并复用同一会话复查，模型账单和 token 遥测均为 null。 [Python 日志](../../output/producer-direction-validation/python-regression.log) · [Remotion 日志](../../output/producer-direction-validation/remotion-render-regression.log) · [Blender 指标](../../output/producer-direction-validation/contact-v2-metrics.json)

另用同一原生场景的镜头中段比较两种摄影棚设置。两张关键帧的轮缘和环带位置相同，较冷背景下仍可辨认两色标记。第二种灯光的关键帧阶段用时 3.071 秒。不同机械题材的最佳构图、真实遮挡、长片完整节奏、听感、观众收益及平台数据仍为 UNKNOWN。镜头库的 VALIDATED 仍为空。验证影片保留为系统回归样本，独立报告记录了实际抽查和科学检查范围。 [同帧灯光对照](../../output/producer-direction-validation/studio-validation.json) · [相机库](../../config/cinematic-shots.json) · [独立 QA](../../output/producer-direction-validation/independent-qa.md)
