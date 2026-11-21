# 门把手回正｜三维预演与项目定位纠偏

> 拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。

原问题为「为什么按下门把手后，松手它就能够自动回正？」本次在原任务目录制作了 40.5 秒三维预演，使用公开专利的杠杆门把手复位组件。Yale 弹子锁保留为独立实验。 [原任务](../../output/tasks/door-handle-return-20261121/task.json) · [低成本预演](../../output/tasks/door-handle-return-20261121/restored-3d/revised/door-handle-return-preview.mp4) · [Yale 实验记录](story-development-door-lock.md)

## 已恢复的创作约束

新任务继续使用已有 Producer、Treatment、Blueprint、动作时钟和 QA。任务记录用户对象与指定问题。Research、Treatment 和正式 Blueprint 必须一致。核心分镜和预演绑定有来源的原生三维文件。人物、历史、实拍和图形承担辅助用途。Director 可以按题材选择拆解、剖视、接触视角和连续运动的编排。

现有独立审查在预演和正式剪辑上检查同一对象、同一核心问题、内部三维、连续动作、科学因果、辅助内容和使用回报。确认严重偏离时登记 REJECT。完整媒体上的审查通过后进入正式制作。 [制作契约](../production-contract.md) · [Producer 入口](../../mechanical_video_next/workflow.py) · [Video Review](../../mechanical_video_next/video_review.py)

## 实施例和三维动作

Ferco 页面支持外设弹簧盒、7 mm 方轴与复位功能。Emtek 安装手册支持其通道门型安装及斜舌方向。这两家现有资料没有公开本次需要的盒内接触。为回答同一个自动回正问题，选用 US 7,900,978 B2 公开的杠杆把手实施例，几何、配色和尺寸为依据专利图文重建的说明模型。图 1、2 给出装配，图 3–5 给出中位和两个方向的受力路径。片中呈现其中一个下压方向。 [专利 PDF](../../output/tasks/door-handle-return-20261121/restored-3d/sources/US7900978.pdf) · [分镜和证据边界](../../examples/door-handle-return/treatment.md)

- 0–5.3 秒及 33–40.5 秒展示装在门上的把手按压和回正。
- 5.3–14 秒沿同一方轴拆开盖板、拨片和压簧。
- 14–23.6 秒展示方轴驱动一侧拨片，弹簧沿弧形导槽缩短，另一端的拨片保持。
- 23.6–33 秒保留同机位与同一运动时钟，弹簧伸长后推动拨片使方轴和把手回到水平。推力与轴心有距离，产生回转力矩。

旧版曾把方轴与斜舌画进实心门板，压簧圈距低于线径，扣板接触也未证实。此次重建实际门板贯穿孔和方轴通道，使用同一复位组件的可检查模型。斜舌、扣板与关门扣合不属于上述预演的解释范围，历史版缺陷保留在原报告。 [旧版机械审计](door-handle-mechanical-audit-20261121.md) · [Blender 源场景](../../output/tasks/door-handle-return-20261121/restored-3d/revised/door-handle-return.blend) · [生成脚本](../../examples/door-handle-return/scene.py)

## 机械核对与交付状态

第一次预演发现压簧形变没有随拨片更新。修订后按同一轴角写入原生场景，570 个核心动作帧记录到最大下压约 28°、最小同相圈距 0.19147、线径 0.068，数值均为场景单位。重新打开最终 Blend，在 19 个姿态检查网格，未检出所测部件对的表面穿插或非相邻弹簧圈相交。在这些姿态中，线圈端面采样点与座面最小距离的最大值约 0.00000118 场景单位。实际零件预紧、材料、寿命及自然回位时长仍待实物验证。 [逐帧运动](../../output/tasks/door-handle-return-20261121/restored-3d/revised/motion.json) · [网格抽检](../../output/tasks/door-handle-return-20261121/restored-3d/revised/native-mesh-review.json)

预演为 768×432、30 fps、1,215 帧，保留实测 Neil 旁白与单行字幕，完整解码及 PCM 对齐通过。独立 QA 核对专利图文与实际 MP4 关键帧，连续机构观看、整片理解和实听为 UNKNOWN。正式高清交付需要独立机械与视觉审查通过。 [技术记录](../../output/tasks/door-handle-return-20261121/restored-3d/revised/technical-review.json) · [独立审查](../../output/tasks/door-handle-return-20261121/restored-3d/revised/independent-review.md)
