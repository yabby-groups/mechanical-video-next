# 指甲刀｜2026-11-11 制作记录

本次用户已授权“制作下一个视频”，按现行运营计划选择指甲刀：**手柄动一大段，刀口只合一点，为什么？**。任务为 `output/tasks/nail-clipper-20261111`，protocol v2、自主参数化 CAD。当前为失败候选诊断，**没有合格完整成片，不进入高清制作**。

## 已生成的可检查交付

- [8 秒失败运动诊断](../../output/tasks/nail-clipper-20261111/diagnostics/core-motion-FAILED-v1.mp4)：960×540、15 fps、H.264、120 帧、无音轨；有“失败诊断／原理示意／非材料接触仿真”标注，完整 FFmpeg 解码通过。它没有实现合格的闭合／张开动作。
- [装配图](../../output/tasks/nail-clipper-20261111/diagnostics/assembly-v1/review-0.png)、[独立零件爆炸图](../../output/tasks/nail-clipper-20261111/diagnostics/exploded-v1/review-2.png)、[实际 CAD 纵剖图](../../output/tasks/nail-clipper-20261111/diagnostics/section-v1/review-0.png)。这些是低成本诊断，不能代替连续运动验收。
- [CAD v3 交接](../../output/tasks/nail-clipper-20261111/cad/handoff.v3.json)：可重复源码、参数、STEP、GLB、独立零件库存、装配、规定形变与数值验证。三版资产分别保留于 `assets/assemblies/nail-clipper-cad-v{1,2,3}/`，没有覆盖失败版本。
- [机械研究](../../output/tasks/nail-clipper-20261111/mechanical-research/research.v1.json)：已实际取得 US2739379A、US6173497B1 原文及图纸，区分专利事实、教学几何和未知。尺寸均为设计近似，不是商品实测，不宣称数值省力倍数。
- [参考研究](../../output/tasks/nail-clipper-20261111/research/reference-videos.md)与[未冻结蓝图 v2](../../output/tasks/nail-clipper-20261111/research/creative-blueprint.v2.json)：筛查 29 条，保留 5A/3B/2C 共 10 条；完整视听 0 条、合格低粉同题样本 0 条。不能据页面元数据宣布爆款研究通过。

## 机械失败与修复上限

源结构为两片尾部连接的弹性刀片、带底头和钩槽的拉销、带横杆及凸轮的手柄。规定的连续刀片弯曲不是材料、载荷或接触仿真。

首版存在拉销/刀片交叠、连接拓扑偏离所选专利、缺少侧向导向。第一轮改为钩槽与横杆、增加导向并改善刀片形状；第二轮修正横杆连接和凸轮座位关系。每版有原生 BRep 数值证据，独立 QA 重新导入 STEP 核查。

| 验证版本 | STEP 实体数 | 最大交叠 mm³ | 上刀片／手柄交叠 mm³ | 结论 |
|---|---:|---:|---:|---|
| 基线 v1 | 4 | 1.229584 | 0.0000183 | FAIL |
| 修复一 v2 | 5（要求 4） | 0.611624 | 0.105684 | FAIL |
| 修复二 v3 | 4 | 4.206947 | 4.206947 | FAIL，停止 |

最终四个实体有效、正体积、网格闭合，STEP 回读四个；原有拉销/刀片交叠已消除。但**打开阶段，手柄横杆与上刀片仍有 4.206947 mm³ 实体交叠**，由独立 QA 对精确 STEP 复算确认。不能用相机遮挡或凸轮局部接触通过来消除此缺陷。

独立 QA 对实际 MP4 抽样还发现渲染动作不符合输入：0/1/2 秒及 4 秒处刀片大幅扇开、拉销脱离，两个片段都向装配状态收拢，没有完成“闭合后张开”的正确顺序。这些新渲染缺陷记为 `clipper.render_motion_pose_mismatch` 与 `clipper.close_open_sequence`，目前各 0 次修复；由于上游机械缺陷已耗尽预算，不再继续依赖它的动画修复。CAD 中规定的 2 mm 刀口间隙不能当作实际视频已实现的动作证据。

持久缺陷 `clipper.cam_leaf_interference` 指上刀片／手柄接触副缺陷；本版实际侵入部位为横杆，凸轮趾部本身的所测样本没有交叠。保留同一持久键和两轮额度，不因细分命名或新版本重置。`clipper.closed_body_collapse` 与 `clipper.jaw_edge_first_contact` 属于同一刀口优先接触问题，不另开预算。

## 制作门禁与检查范围

参考研究不是 READY，因此正式 `viral-analysis` 交接被门禁拒绝，没有伪装通过、冻结蓝图或登记全 PASS 的 feasibility。机械检查 FAIL，同样阻止完整动态分镜、高清预览和最终制作。默认 Neil 与打印机 EP03 横屏方向保留；没有对未合格脚本提交新配音请求。

收口时检测到工作区同期更新的主参考复刻规则，已读取并为本任务登记 `production_method=reference-recreation`，没有修改其他会话的规则或源码。当前还缺已实际分析的合格主参考、task-bound READY 研究与逐镜头 `reference_recreation.shot_mapping`。旧 PROVISIONAL 蓝图原样保留，不作为满足新增要求的冻结蓝图；详见任务 `policy-addendum.v1.json`。

Blender 在沙箱进入场景 Python 前 SIGSEGV；保存失败日志后，通过已批准本机执行现有 `stage --diagnostic` 恢复，未改沙箱配置。五个成功低清阶段串行执行，总计 53.14 秒；逐阶段工具记录保存在任务与 `output/runs/`。工作目录采样峰值约 1.55 GB，未触及 2 GiB 上限。源资产与输出保留，仅按既有工具规则清除已编码验证的本次 PNG 序列。

当前原生工具总线程上限拒绝新增 Animation；既有研究角色的开发者指令不允许转写动画配置，因此由 Producer 使用现有确定性工具执行低清诊断。没有用普通进程冒充代理。机械研究、CAD、创意研究与独立 QA 均为真实原生线程，身份与事件保存在任务中。没有完整连续视频输入或听审能力，相关检查保留 UNKNOWN；抽帧和解码不代替完整观看。

[独立机械 QA 最终报告](../../output/tasks/nail-clipper-20261111/qa/mechanical-final.v1.json)已通过不可变 `mechanical-qa.v1` 交接登记：solids PASS；assembly、motion、interference、mechanism_visibility FAIL；retention UNKNOWN。实际覆盖 5 张静态图及 10 个视频抽样帧。[Producer 收口记录](../../output/tasks/nail-clipper-20261111/producer-closeout.v1.json)再次核对所有交接依赖、CAD 源与媒体哈希，确认机械门禁拒绝，任务已置为 BLOCKED，残余缺陷与两轮停止状态保留。

没有提交 Git、上传、保存平台草稿或发布。原有 README 与运营计划的在途改动保留。
