# 雨伞导演、运动与局部合成回归

## 审计

修正带 V7 的本地 MP4 哈希与原交付报告一致。该片已有逐帧投影、局部接触、Remotion 分段更新和独立抽帧记录。它覆盖卷径、柔性带和滑移，雨伞任务补足空间连杆、滑套和伞骨联动。历史任务还保留了切换、遮挡、错误机构、掉轴和缓存输入失效的失败证据。连续视听与真人理解仍为 UNKNOWN。

已有 Blueprint、知识递进、相机路径、原生剖切、运动约束、媒体库、工作锁、分块编码和六维 QA 继续承担原有职责。此次发现的缺口是点重合检查无法检出轴线错误、观察目标虽保存在叙事计划却不能直接约束机位、投影结果与画面标注没有交叉检查，以及外部 Blender 输入可能共享同一装配规格键。历史雨伞复跑还发现原构建所引用的临时 Blender 装配已经清理。当前回归用保留的同源 GLB、网格和装配配置重建一次可检查的 Blender 输入。

## 生产代码

- `direction.observation` 可选择整体建立、接触、连杆、状态对照、跟踪或内部结构。选择 `camera.preset=auto` 后，接触、连杆和状态对照固定在作者提供的首个机位。跟踪、剖切等依赖已声明的执行输入。观察窗口绑定真实几何锚点，Blender 记录离屏数，合成检查列出落入活动标注或字幕框的帧。光照、色彩、时间轴、实际遮挡与受众理解继续用各自证据检查。
- M1 依赖原装配的零件位置、尺寸和几何记录。M2 增加 `hinge` 和 `slider`。依序给每件两点定义有向轴，滑套再给第三点检查绕轴转动，声明允许的轴向范围。逐帧报告位置、角度和越限时间。M3 仍为 UNKNOWN，所用轨迹是教学级运动学示意。
- 核心镜头的素材匹配由已知 `product_identity.mechanism_id` 约束，许可、素材时间范围和质量仍由现有匹配条件检查。外部 `.blend` 以实际文件哈希区分，原生已验证装配继续沿用现有缓存键。字幕修复读取当前配置中的装配绑定。

## 实际影片与前后证据

沿用杨氏 EP0493867A1 图 2–3 和第 [0006]–[0009] 段的手动直杆伞实施例。复用原教学尺寸、八组伞骨、Neil 和实测时间轴。只更新 43.900–59.467 秒的因果镜头，首轮真实预览后检查手机比例和动作时序。原镜头在「滑套上行」的一句期间仍在下行。修订按 467 帧输出时钟，从原生第 131 帧近收拢位置开始使用展开段，逐帧复用实际画面及相同锚点样本。独立抽帧在首个 1080p 工作片确认了方向改善，同时发现前镜近展开与新镜近收拢的状态切换。V2 以画面提示交代从收拢位置重新观察，单独重合成前 42 帧。视觉上仍是有标记的重置切换。

- [完整 V2 MP4](../../output/director-kinematics-regression/umbrella-revised-workprint-v2.mp4) 129.033 秒，1920×1080、30fps、H.264/AAC、3871 帧，完整解码通过。
- [完整动态分镜](../../output/director-kinematics-regression/umbrella-dynamic-animatic-opening-v2.mp4) · [15.57 秒合成镜头](../../output/director-kinematics-regression/final-composed-opening-v2.mp4) · [旧版工作片](../../output/tasks/production-1795015080131995000/review/umbrella-3d-workprint.mp4)
- [3:4 封面](../../output/director-kinematics-regression/cover-v2/portrait_cover_3x4.png) · [4:3 封面](../../output/director-kinematics-regression/cover-v2/landscape_cover_4x3.png) · [来源、CAD、原生场景与逐帧证据索引](../../output/director-kinematics-regression/source-index-v2.json)
- [独立 V1 缺陷记录](../../output/director-kinematics-regression/independent-qa.md) · [独立 V2 抽帧复查](../../output/director-kinematics-regression/independent-qa-v2.md) · [V2 解码对照](../../output/director-kinematics-regression/decoded-comparison-v2.json) · [整片音画身份](../../output/director-kinematics-regression/full-build-v2.json)

新版目标区间 467 帧均有可测变化。区间外 3404 帧的解码 YUV 哈希完全一致，整条 Neil 解码 PCM 一致。整片以无损编码完成拼接，其余十个镜头直接复用原片像素。467 帧原生求值的三个观察点均未离屏。两个铰链的最大位置残差为 0.134 µm，轴向与滑套横向误差在本模型测量精度内。独立复查在 43.91 和 44.25 秒看到了重置提示，45.33 秒已退出。切换处的状态差异仍然存在。整体感知质量为 UNKNOWN。

## 验证与资源

Python unittest 461 项，456 通过、5 个既有条件跳过。Remotion TypeScript 检查通过。本机 Blender 26 个测试全部获得预期结果，其中注入了定点倾斜、滑套横漂、绕轴转动和越程。真实缓存复跑命中装配和原生镜头，已核对输出 SHA256，修改机位改变原生缓存键。

| 项目 | 实测 |
| --- | --- |
| 同源 Builder 首次导入 | 3.697 s，39 个部件 |
| 原生低成本预览与高清镜头 | 99.98 s / 572.02 s，包含 Blender 分块编码 |
| 修订时序的 Remotion 局部合成 | 540p 37.49 s / 1080p 40.39 s |
| V2 1080p 标注重合成与整片拼接 | 42 帧 / 6.03 s，之后 FFmpeg 全片拼接 15.77 s |
| 高清分块中间数据 | 已验证并清理 507 个临时文件、795,643,179 字节；阶段采样 work 18,971,035 字节 |
| 复跑 | 2 个真实缓存命中，装配 0.011 s、镜头 0.022 s，Blender 执行 0 次 |
| 原生子 Agent | 1 个独立 QA，首次与复检各一轮，使用现有 Terra/high 角色配置，实际运行遥测、Token、费用、人工干预总数为 null |
| Neil 请求、新建 CAD、发布 | 均为 0 |

启动和修订失败保留原日志。Blender 受限 Metal 初始化和 Chrome 受限启动失败，随后本机执行成功。原生首轮行程断言拦下作者错误的上界预期。Remotion 分别拦截越界与重叠标注框。当前证据覆盖一级工程回归和本任务二级真实镜头、局部重合成、完整技术工作片。第三级正式感知验收、任意主题稳定性、手机端连续可读性、真实锁止与布料/接触/摩擦动力学、完整原创版权独立审查和观众理解仍缺少证据。增长指标尚未采集，沿用原任务的增长问题和来源记录。无正式账本交付回执。
