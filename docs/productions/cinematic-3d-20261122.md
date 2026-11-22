# 君哥拆机器 · 电影化三维重构

> 拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。

本次验证门把手回正机构。核心问题是为什么按下门把手后，松手它能够自动回到水平位置。实施例采用 US7900978B2 图 1–5 的单向演示，方轴、两片拨片及弧形压簧沿用已有教学重建。外部场景是安装情境重建。讲述范围限于把手回正。 [专利图及说明](https://patents.google.com/patent/US7900978B2/en)

## 现状与环境

- 开工时 `main` 与本地 `origin/main` 同步指向 `54ce43df7840094c9e77a46fc97314ec01cd681a`，工作树干净。远端为 `yabby-groups/mechanical-video-next`。历史输出目录独立于 Git 跟踪。 [README](../../README.md) · [生产契约](../production-contract.md) · [历史 Skill-driven 实验](../skill-driven-production.md)
- 新主题默认由当前会话作为 Producer，依次进行问题与实施例、Research、Treatment、独立故事审查、完整诊断预演、独立预演审查和正式制作。单集账本沿用固定版本。该历史门把手任务使用 contract 6、producer-directed、visual policy 2 和 media policy 1。修订证据以本地工作稿身份保留。 [工作流](../../mechanical_video_next/workflow.py) · [版本解析](../../mechanical_video_next/production_contract.py) · [旧样片审查](../../output/tasks/door-handle-return-20261121/restored-3d/revised/independent-review.md)
- 项目技能目录包含 CAD、Director、Mechanical Animation、Mechanical Research、Mechanical Asset、Mechanical Video、Viral Video Research、Video Review、Audience Review。现有配置中 Producer 与 Mechanical Research、CAD 为 Sol，Animation、Editor、Research 与 QA 为 Terra，Asset、Viral Research 为 Luna，默认并发上限为两名子代理。本轮独立审查复用同一 QA 角色。实际模型与 token、成本等以报告可用遥测为准。
- 确认存在 40.5 秒 768×432/30 H.264/AAC 旧预演、原生 Blend、逐帧 motion.json、网格诊断、可查专利 PDF、原始 Neil 母带、Treatment 与编辑时间轴。历史目录另有门锁循环与不同结构的迭代稿，本次模型与问题都绑定上述旧预演。可重复利用的第二题材资产为皂液泵 US5738250 图 1 的原生循环与位置记录。风格参考仍在 `assets/style-reference/`。 [基线与来源](../../output/tasks/door-handle-return-20261121/restored-3d/revised/) · [泵源场景与旧动稿](../../output/tasks/soap-joint-timeline-v1/master/)
- Apple Silicon arm64，Blender 5.2.3 LTS `e13b728c6880`，FFmpeg 9.0.2，项目 Python 3.14.2，Remotion 4.0.542。Metal 在沙箱下于 Python 启动前失败，实际渲染使用获准的同一 Blender 二进制进程。工作起点约 1.7 GiB，空闲约 61 GiB。可直接使用本地 EEVEE、Workbench、Cycles CPU、FFmpeg、项目音画校验和 CodeGraph。已有 Neil 音轨及其受绑定的语句缓存支持重新合成。当前审查可看定点图、检测媒体与声音波形，连续观看与实听覆盖未知。 [Metal 失败日志](../../output/tasks/door-handle-return-20261121/cinematic/metal-sandbox.crash.txt)

## 根因及处理

| 根因与影响 | 当前代码与配置 | 真实证据和处理 |
| --- | --- | --- |
| 画面被工程用途的渲染默认值主导。对象色、固定棚灯和屏幕腔体阴影抹平材质与照明差异 | `blender/scene.py` 的 `setup_render` 默认为 Workbench。门把手示例也单独设置 Workbench 和 Standard | 旧片 1 秒把手、底座与门板主要靠平涂和硬影分层。同机位第 617 帧中，EEVEE 使拉丝、软箱反射和弹簧座边缘可辨。保留 Workbench 技术预览，显式启用独立电影化配置 |
| 正交适于尺寸与状态比较，观察产品和轴向分离时深度线索较弱 | `frame_camera` 从包络求正交尺度。旧门把手 `camera` 也设置 ORTHO。已有 `science_guides.camera_motion` 支持 `camera_path` 及 Add Camera Rigs | 旧片 9.4 秒看到轴伸出，盖板后移与装配层次依然重叠。新镜头先沿轴拔出，然后看到盖板横移、方孔露出。外观透视，机械对照保留正交。使用原生 Track To 固定焦距和位移。现有 Dolly、Crane 路径继续可用 |
| 固定棚拍掩盖题材美术与真实光源的变化 | `studio_style.apply` 限于 `printer-ep03-studio-v1`，三盏灯、同一地面、材质调灰与正交尺度推近。 `visual_narrative.configure_blender` 只接受旧 profile 下的导演灯光字段 | 旧片门板无木纹且看不到门框参照。新片 1 秒有门板、门框阴影和拉丝反射。保留复现 profile，新 profile 使用实际面积灯和材质选项。原生门把手场景另有针对弹簧的窄面积光 |
| 导演计划的描述只有在执行器已有对应路径时才生效 | `director.apply_strategy` 传入相机、剖视、图形、时间和不透明选项，校验动作摘要。 `blueprint.compile_config` 编译已有动作和输出。 `production_contract.py` 管节目事实与变更范围。 `creative_selection.py` 的策略筛出可表达的内容 | 文本里的「微距」不能自己改变材料、剖视或故事，同一模板使多个改稿继续产生近似影像。新选择由可运行场景编排，原生位置、相机、灯和成片同存。方孔镜头 11–15.55 秒明确展示去掉近景手柄后的孔形 |
| 拆解缺少共同的固定参照，呈现顺序改变后会影响空间理解 | 旧示例 `visibility` 隐藏门板，将六组零件并发移开，盖板朝后运动 | 新片先固定门板和壳体，并在轴拔出后移开盖板。首版独立审查发现拆解时门板下缘浮在背景，修订版延伸门板并固定与门框的关系。移除外壳为说明性拆解。 [首版审查](../../output/tasks/door-handle-return-20261121/cinematic/core/independent-qa.md) |
| 同步转动的教学模型无法独立证明力的发生，早期画面把过多解释交给旁白 | `examples/door-handle-return/scene.py` 驱动轴、把手、拨片和弹簧 shape keys。方轴轮廓预留建模 clearance，原模型注册为 `physical_simulation=false` | 15.65–29.6 秒完整时钟有压缩与回程。首版 20.9 和 24.2 秒看不到弹簧上端和把手，修订版只保留 20.25–21.38 秒微距，释放时回到整体。逐帧角度、弹簧键权重及端点样本用于核对几何。真实游隙、接触力和动态参数依实物另测 |
| 流程与验收能排除坏输入，缺少持续有效的画面样板会让技术阶段重复完成 | `joint_timeline` 校验动作源时钟与配音。 `video_review` 和 `production_contract` 要求实际媒体。 `render_with_provenance` 记录实际场景。 `scripts/produce.py`、`remotion_build.py`、Remotion TS 和 `scripts/clean.py` 执行缓存、画面及技术检查 | 首稿能连续解码依然因微距构图退回。动作绑定补齐后复用同一实际 MP4。独立审查无法正常速度连续视听，本轮正式成片状态 UNKNOWN |

以上观察绑定原 MP4 在 1、9.4、22、29 秒的抽帧与新版同状态对照。甄别摄影、灯光与构图的参考信息还见 [旧相机实验](../cinematic-shots.md)、[视觉分镜](../visual-narrative.md)、[创意方向](../creative-direction.md)。

## 路线比较

| 项目 | A，扩展旧系统 | B，保留机械内核并重做视觉 | C，全面重建 |
| --- | --- | --- | --- |
| 节目定位与导演自由 | 科学路径成熟，创意易被模板和默认棚拍约束 | 同一证据用于不同题材，原生场景可直接导演 | 可重做全部创作接口，需重新接回事实和动作 |
| 三维机械表达、接触、拆解与剖视 | 已有 EAS、轨迹、局部剖切，擅长工程诊断 | 复用可检查的 CAD 与动作。可按空间和接触调度，并联用既有剖切 | 可定制，需重新验证装配、几何和所有动作约束 |
| 材质、灯光、摄影与视觉 | 旧棚景已有 EEVEE。导演映射集中在有限参数 | 原生材质节点、逐镜灯光、透视真位移与正交观察并存 | 原生 Blender 的视觉上限与 B 相同，接口自由度更大 |
| 可靠性、独立 QA | 迁移风险低，旧产物兼容最容易 | 独立 QA 与技术边界继续使用。新场景需增加媒体和动作来源证据 | 易将重建时间花在重做 QA、锁、配音与缓存协议 |
| 复用、批量与维护 | 旧任务复现成本最低，场景差异大时累积特例 | 共享灯光、材质、摄影、分块编码。装配与镜头取舍仍按题材 | 有潜在简化机会，迁移与并行维护成本最高 |
| 渲染性能与迁移影响 | Workbench 快，旧 EEVEE 路径可优化 | 用实测 EEVEE 生产样板，Cycles 用于明确受益的帧。旧诊断路径仍可走 | 同渲染器条件下无天然加速，需重新验证恢复机制 |

采用 **B**。路线选择先依据旧片与四组 EEVEE 样板，随后用同机位的 Workbench、EEVEE、Cycles 对照复核。保留机械网格、CAD、已知动作、来源定位、Neil 与联合时间轴、Remotion 合成入口、分块编码和独立 QA。重写本集说明性拆解、拍摄和视觉环境。新增吸收真实验证结果的 Blender 复用模块。历史资产和模块没有删除，旧棚拍与模板默认降为复现和诊断路径，本次证明能用显式 opt-in 执行新路径。 [共享制作代码](../../blender/cinematic.py) · [同机位三引擎](../../output/tasks/door-handle-return-20261121/cinematic/renderer-comparison/)

## 实际成品与差异

| 交付物 | 实测范围 |
| --- | --- |
| 匹配源姿态的旧版和新版 | 新核心修订片 320 帧、10.667 秒、30 fps。左旧右新，源帧完全一致。外观段与拆解段之间切换源区间。完整机械段保持一个单调取样的三倍时间映射，成片原速周期看完整预演。 [旧版](../../output/tasks/door-handle-return-20261121/cinematic/core-revised/old-workbench.mp4) · [新版](../../output/tasks/door-handle-return-20261121/cinematic/core-revised/door-handle-cinematic-reveal.mp4) · [同屏](../../output/tasks/door-handle-return-20261121/cinematic/core-revised/side-by-side.mp4) · [因果无字幕](../../output/tasks/door-handle-return-20261121/cinematic/core-revised/mechanical-review-silent.mp4) |
| 四类视觉样板 | 同屏 1.0 秒外观与门体，5.4 秒轴向拔出和盖板移开，完整预演 20.9 秒弹簧端微距、24.2 秒释放全局。5.4 秒相较旧片可同时定位盖板轮廓、方轴与仍装在门上的弹簧壳体。旧片在首版新 7.6 秒特写的同状态下保留更多机械上下文。 |
| 40.5 秒完整动态预演 | 640×360、1215 帧、H.264/AAC、Neil 单声道 48 kHz、单行字幕。完整展示安装外观、按压回正、拆解、方孔、装配剖视、储能和释放、回到使用。局部微距修订已回到整片。 [影片](../../output/tasks/door-handle-return-20261121/cinematic/animatic-revised/door-handle-animatic.mp4) · [动作绑定 Blueprint](../../output/tasks/door-handle-return-20261121/cinematic/animatic-revised/action-bound-blueprint.json) |
| 源文件 | [核心 Blend](../../output/tasks/door-handle-return-20261121/cinematic/core-revised/scene.blend) · [逐镜摄影和灯光](../../output/tasks/door-handle-return-20261121/cinematic/core-revised/photography.json) · [预演 Blend](../../output/tasks/door-handle-return-20261121/cinematic/animatic-revised/scene.blend) · [剪辑与拟音](../../examples/door-handle-return/cinematic_edit.py) |
| 机械及音画技术 | 原模型与两套修订场景各在 1215 帧有完全相同的局部旋转与弹簧权重，八处弹簧两端几何座距离在 .002 场景单位阈值内。压簧和座有求值样本，方轴开口有教学游隙。已检查连续帧时间戳、完整 AAC、虚拟拟音混音峰值与人声间隔。Neil 拼装母带逐字节匹配。现有语音授权范围沿用源项目证据，拟音是原创程序生成。 [机械证据](../../output/tasks/door-handle-return-20261121/cinematic/mechanical-verification.json) · [预演技术](../../output/tasks/door-handle-return-20261121/cinematic/animatic-revised/technical.json) · [混音](../../output/tasks/door-handle-return-20261121/cinematic/animatic-revised/audio-mix.json) |
| 皂液泵 | 199 帧 768×432/30 动片，沿用 US5738250 重建的回升、进液球和压簧运动。共用 PBR、面积灯和固定焦距相机。需为泵头行程重新适配垂直空间。修订后 2.8、5.7、6.5 秒均保留泵头和出嘴。流体示踪沿用示意。 [修订 MP4](../../output/tasks/door-handle-return-20261121/cinematic/soap-pump-revised/soap-pump-refill.mp4) · [摄影和源运动](../../output/tasks/door-handle-return-20261121/cinematic/soap-pump-revised/photography.json) |
| 现有标准渲染入口 | 在 `render_with_provenance.py` 以旧修正带约束和新 profile 实际运行，输出 373 帧范围的三张关键帧、评估报告与源 Blend。 [实际执行日志](../../output/tasks/door-handle-return-20261121/cinematic/standard-render.log) · [约束与执行报告](../../output/tasks/door-handle-return-20261121/cinematic/standard-render/checks.json) |

同机位第 617 帧，Workbench 约 0.057 秒，EEVEE 约 0.379 秒，Cycles CPU 约 4.649 秒。Cycles 的局部连接出现明显黑色矩形，且每帧更慢。当前电影化样板使用 EEVEE。首版核心渲染至 331 帧约 202 秒，初版整片至 1215 帧约 195 秒，二次泵片约 35 秒。锁排队、编码与启动分别保留日志。实际模型 token、推理成本和机器电耗未知。 [引擎计时](../../output/tasks/door-handle-return-20261121/cinematic/renderer-comparison/timings.json)

## 独立审查与当前边界

- 第一轮核心和完整预演的长微距获得局部 REVISE。修订后的完整预演在 24.2 秒补回上座、下端和把手。20.9 秒仍刻意用短微距显示下座。两段运动之间的切换、动作接触持续可见性及 Neil 的发音和音画整体感需连续观看与实听。 [首版完整审查](../../output/tasks/door-handle-return-20261121/cinematic/animatic/independent-qa.md) · [修订独立审查](../../output/tasks/door-handle-return-20261121/cinematic/independent-revised.md) · [跨题材和时钟复核](../../output/tasks/door-handle-return-20261121/cinematic/independent-recheck.md)
- 抽帧支持外观材质、拆解空间和复位微距的具体改善。观众能否在首次观看时完整复述科学因果，以及是否愿意看完、点赞或关注，仍为 UNKNOWN。整片 1080p 及正式交付仍取决于规定的完整独立验收。
- Python 全量回归 532 项，526 项通过、6 项跳过。Remotion TypeScript 检查通过。历史完整交付媒体、冻结的风格基准和 Remotion 浏览器等集成条件以现有测试日志为准。 [回归日志](../../output/tasks/door-handle-return-20261121/cinematic/regression.log)

## 高清与补充复核

- 1080p 核心片以 16 个 EEVEE 渲染采样重新输出。320 帧，10.667 秒，渲染到最后一帧约 250 秒。该片为无旁白的镜头验收素材。 [高清核心片](../../output/tasks/door-handle-return-20261121/cinematic/core-hd/door-handle-cinematic-reveal.mp4) · [同屏](../../output/tasks/door-handle-return-20261121/cinematic/core-hd/side-by-side.mp4) · [Blend](../../output/tasks/door-handle-return-20261121/cinematic/core-hd/scene.blend) · [独立抽样](../../output/tasks/door-handle-return-20261121/cinematic/core-hd/independent-qa.md)
- 修订预演的三个拼接区间共 1215 帧，逐帧比较源与拼接的解码亮度。完整画面最大单帧平均偏差 0.438，最终带字幕画面的中心观察区为 0.556，量纲为 8 位亮度级。视频保持准确的 30 fps 序列。 [逐帧验证](../../output/tasks/door-handle-return-20261121/cinematic/picture-splice-verification.json)
- 历史修正带 B/C 的原导出、源 Blend 和若干 shot JSON 在当前工作树缺失。按历史相机配方和存续的同一修正带接触程序重渲两个 373 帧版本。B 前段能看到两个卷轴和机壳，C 较早收紧到左卷，中段构图相近。历史 v2 锁定特写的 4 秒和 8 秒仅能看到局部。三者目前仍为实验。 [复现 B](../../output/tasks/door-handle-return-20261121/cinematic/historical-B/camera.mp4) · [复现 C](../../output/tasks/door-handle-return-20261121/cinematic/historical-C/camera.mp4) · [独立比较](../../output/tasks/door-handle-return-20261121/cinematic/historical-camera-review.md)
- 额外运行 Remotion 浏览器实渲检查并通过。Blender 原生运动约束测试通过。Blender 历史旋转回归的合成转子用例完成，后续 Boston 卷笔刀全片配置查找跑到文件缺失，保留原日志。门把手实物重建、皂液泵动作和历史摄影棚都保留了各自的来源及检查范围。 [Remotion](../../output/tasks/door-handle-return-20261121/cinematic/remotion-render-regression-authorized.log) · [原生约束](../../output/tasks/door-handle-return-20261121/cinematic/blender-motion-constraints.json) · [历史缺件](../../output/tasks/door-handle-return-20261121/cinematic/blender-rotation-regression.log)
- 本地制作目录约 290 MiB，work 约 1.7 GiB，渲染结束后检查空闲约 60 GiB。整片分块由现有工具核验并回收临时帧。核心对照保留实际帧，供来源比对。

## 职责落点

| 职责 | 本次执行 |
| --- | --- |
| Mechanical Truth | 专利定位、原生方轴与拨片几何、弹簧形变、逐帧姿态及接触样本。保留限位与力学测试的证据边界。 |
| Cinematic Production | 按题材布置真实光源和场景，用 PBR 拉丝金属、木纹、涂层及原生透视摄影。两题材复用材质与面积灯。 |
| Presentation Animation | 说明性拆解、孔形的去遮挡镜头和短微距各有自己的时间区间。真实机械动作使用不变的源时钟。 |
| Editorial & Sound | 测时 Neil 原速度、字幕及原创拟音。正式 Producer 仍能调用 Remotion，诊断动稿走 FFmpeg 并同样绑定源帧和声音。 |
| Independent Review | 原生几何、解码和片级感官证据分别记录。独立报告确认局部画面改善，整体验收保留 UNKNOWN。 |

[四类样板及逐帧来源索引](../../output/tasks/door-handle-return-20261121/cinematic/samples/index.json) · [来源清单](../../output/tasks/door-handle-return-20261121/cinematic/sources.json) · [耗时与容量](../../output/tasks/door-handle-return-20261121/cinematic/production-metrics.json) · [皂液泵逐帧机械复用](../../output/tasks/door-handle-return-20261121/cinematic/soap-pump-revised/motion-equivalence.json)
