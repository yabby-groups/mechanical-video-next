# 科学故事视觉验证

本轮保留两个已有问题及其研究记录，分别用 18 秒和 17 秒的无旁白动稿检验画面。预览为 640×360，原生 Blender 12 fps 画面编码为 24 fps。两个试作由原工作流的研究交接、诊断动稿和场景方向记录追溯。

## 航海计时

基线在 2、13、31、54 秒抽查到平面帆船、双钟与地球、路线图，以及回到平面帆船。新版 0–5 秒从甲板移向图桌，船员举起计时器。5–9 秒切到手部，保留袖口和桌面背景。9–13.5 秒以圆表盘接圆地球，两条经线提供同时刻的空间比较。13.5–18 秒回到舷边，岛岸成为推算结果。地球段保留短标签说明两处时刻，岛岸段仍依赖一句字幕交代“预先算到”的历史含义。

格林尼治皇家博物馆记录了 1761 年威廉·哈里森携 H4 赴牙买加试航，以及他用它预判更早抵达马德拉。船体、服装、计时器外壳与岛岸是原创概括性重建，具体船型、人物肖像、精确海岸轮廓及表盘读数均未还原为档案事实。经线相差 15°，说明兼容太阳时下的一小时经度差。历史航程不套用该示例的时刻或角度。动稿只用试航与经度原理所需的资料。[H4 试航记录](https://www.rmg.co.uk/stories/topics/harrisons-clocks-longitude-problem) · [经度原理](https://www.rmg.co.uk/stories/topics/what-longitude)

[18 秒新动稿](../../output/visual-story-20261120/nautical-visual-preview.mp4) · [基线工作版](../../output/science-creation-20261120/longitude-v2/longitude-workprint.mp4) · [场景导演规划](../../output/visual-story-20261120/nautical-scene-direction.json)

## 硬币折射

基线从平面水槽和两条入眼光线解释视位置。新版先固定观察点。0–2.15 秒展示空容器与杯沿的遮挡，随后注水，6.7 秒抽查到露出的硬币。7.1–12.6 秒转到同一容器的剖面，画出光线经过水面再越过杯沿。回到同一机位排水，16.7 秒抽查到遮挡恢复。注水和排水使用编排的水位变化，湿态以实际光线追踪折射渲染。空气侧的虚线是一条反向延长方向。

用场景中的模型坐标复算，杯沿高度约 0.86，干态直线在杯沿位置高度 0.701。水高 0.74、折射率 1.333 时，符合 Snell 定律的出射光在杯沿位置高度 0.932。代表性光线的方程残差约 4.8e−15。模型假设平水面，水位动画与水流为示意。本片没有取得实验实拍，观察结果来自这个可复算的三维光学模型。[OpenStax 折射定律](https://phys.libretexts.org/Bookshelves/University_Physics/University_Physics_(OpenStax)/University_Physics_III_-_Optics_and_Modern_Physics_(OpenStax)/01%3A_The_Nature_of_Light/1.04%3A_Refraction) · [折射与视位置](https://www.physicsclassroom.com/tutorial/refraction-and-lenses/refraction/refraction-and-sight)

[17 秒新动稿](../../output/visual-story-20261120/optics-visual-preview.mp4) · [基线动稿](../../output/science-creation-20261120/optics/v2/draft.mp4) · [场景导演规划](../../output/visual-story-20261120/optics-scene-direction.json)

## 制作与验证

项目新增场景方向约束和正式配音前的观片检查。场景绑定实际媒介和带定位的来源，跨故事与解释的转场说明保留了什么。替代媒介必须说明理由。只存静态代用品、表达缺口或未完成全片观察的试作可以留档，正式生产继续等独立审看。

默认沙箱下 Blender 在 Metal 初始化退出 139。经允许的 Blender 原生运行完成两条动稿，串行占用现有生产锁。航海 EEVEE 216 帧、131.660 秒，折射 Cycles 204 帧、279.785 秒。两条成片 FFmpeg 全量解码通过。画面及剪辑都是原创，来源网页用于事实核对。此次使用无旁白的图像审稿，Neil 缓存照原流程保留。没有启动子 Agent，也没有进行独立全片观看、听审或正式验收。正式状态为 UNKNOWN。

475 项回归中 469 项通过、6 项跳过。新增测试覆盖有目的的静止观察、故事与解释之间的衔接、媒介替换理由和正式配音前的完整观片判断。两条验证任务均已绑定诊断动稿，当前交接为独立观片。

[原生场景源码](../../blender/visual_story_studies.py) · [航海媒体证据](../../output/visual-story-20261120/nautical-preview-receipt.json) · [折射媒体证据](../../output/visual-story-20261120/optics-preview-receipt.json)
