# 自主 CAD 拉链：实际产物与机械关卡失败

当前状态 **BLOCKED / MECHANICAL_FAIL**。本次已实际自主建模、导出、渲染短动作和独立复核，未产出完整科普成片。拉片及销轴与上盖的局部干涉在两轮修复后仍未消除，按用户上限停止，不启动高清或完整制作。

## 实际交付

- [8 秒动态诊断预览](../../output/tasks/zipper-cad-20261111/editor/dynamic-preview-v4.mp4)：960×540、15 fps、120 帧、静音，明确标注装配失败、教学近似及移除上盖。完整解码通过。
- [4 秒啮合](../../output/tasks/zipper-cad-20261111/editor/diagnostic-v4-close/review-0.mp4) / [4 秒分离](../../output/tasks/zipper-cad-20261111/editor/diagnostic-v4-open/review-0.mp4)。移除上盖、拉片、销轴仅用于观察，不宣称修复铰接。
- [装配图](../../output/tasks/zipper-cad-20261111/editor/diagnostic-v4-assembly/review-0.png)、[爆炸终点图](../../output/tasks/zipper-cad-20261111/editor/diagnostic-v4-exploded/review-2.png)、[真实布尔剖切图](../../output/tasks/zipper-cad-20261111/editor/diagnostic-v4-section/review-0.png)。爆炸布局不是已验证的拆卸路径。
- [参数化 build123d 源码](../../mechanical_video_next/cad.py)、[生成入口](../../scripts/cad_generate.py)、[参数](../../config/zipper-cad-parameters.json)、[已验证环境版本](../../requirements-cad.txt)。
- [STEP](../../assets/assemblies/zipper-parametric-v3/zipper-parametric-v3.step)、[GLB](../../assets/assemblies/zipper-parametric-v3/assembly.glb)、[装配清单和局部基准](../../assets/assemblies/zipper-parametric-v3/inventory.json)、[运动采样和连续布带形变](../../assets/assemblies/zipper-parametric-v3/motion.json)。
- [CAD 验证](../../assets/assemblies/zipper-parametric-v3/validation.json)、[独立 QA 目录](../../output/tasks/zipper-cad-20261111/qa)、[全部媒体及哈希](../../output/tasks/zipper-cad-20261111/editor/diagnostics-final.v1.json)。
- [自动执行及返工统计](../../output/tasks/zipper-cad-20261111/execution-statistics.v1.json)、[完整交付清单](../../output/tasks/zipper-cad-20261111/delivery-manifest.v1.json)。

## 验证范围与停止原因

最终模型为 16 颗独立链牙、两条连续简化布带支撑、具有真实导向空间的拉头组件、拉片、销轴与止挡，共 28 个正体积有效实体；STEP 回读仍为 28 个。源 CAD 使用 mm，GLB 和渲染显式换算为 m；未合并成单网格。布带采用规定运动的薄实体/对应闭合网格，不是材料接触或弹性仿真。尺寸来自明确的教学比例，不是某款量产拉链的测绘。

25 点稀疏采样曾漏掉链牙间干涉，独立 QA 的 191 点加密采样推翻该结论。第二轮齿头轮廓修复后，同一采样条件下链牙与原导向结构未检出相交；最终 v3 保留这些已耗尽修复额度的几何和路径。横向拉离探针显示齿头阻挡；不推断强度、材料受力、帧间连续无碰撞或厚度方向保持。

连续布带与齿根、止挡的接触已验证。拉片铰接两轮修复后仍有上盖/拉片 **0.8093692071 mm³**、上盖/销轴 **0.0104688825 mm³** 的相交。独立 QA 在 191/191 状态共发现 382 个对应相交事件。因此整体数值检查 FAIL，不能将局部链牙运动通过当作装配合格。

真实视图中上盖遮住啮合区，观察片明确移除相关件以看清 Y 导向和两排链牙；装配图与报告保留原始缺陷。连续观看、听审、厚度方向保持等未证实项保留 UNKNOWN。六段已有 Neil 配音已核验缓存与解码，没有新增 TTS 请求，但未合成为新全片。

## 已落地的生产策略

新 `produce` 任务默认自主 CAD：ViralResearch 只研究创意，MechanicalResearch 研究真实结构、尺寸依据和未知，CAD 生成参数化实体、装配及验证，之后才进入 Animation、Editor、独立 QA。主会话是唯一 Producer。旧 Asset/Research 接口保留历史兼容，默认不访问成品模型网站。

已读取用户指定 GitHub CAD Skill，远程版本与旧本地版本 SHA256 一致：`da533e7b5ac1b8e8d5e2616f5e8e52e2b95b7099984adf0831c2f1f7e46d9d6b`。复用了 STEP-first、参数、独立实体、基准、几何检查和局部修复方法，未复制旧工程。新项目新增窄职责 CAD/机械研究 Skill 与角色文件。

工作流新增 CAD 文件及源码哈希、机械诊断和独立机械 QA 交接；机械关卡和既有视频分镜关卡分离。数值失败、缺失证据、UNKNOWN、旧依赖或同一作者自审均不能解锁高清/全片。自动修复总计最多两轮，无改善的策略必须更换；缺陷别名共享预算。125 项测试通过，包含新增门禁回归；这不代表模型或视频验收通过。

## 复现

在含 `requirements-cad.txt` 依赖的 Python 3.11 环境运行，使用新输出目录保留历史证据：

```sh
python scripts/cad_generate.py --parameters config/zipper-cad-parameters.json --output output/zipper-cad-repro --report-dir output/zipper-cad-repro-report --asset-id zipper-cad-repro
```

该源码重现的是已记录失败的诊断模型；导出文件成功不能替代读取 `numerical_status`。本次实际复用本机已验证的旧项目 Python 环境，未复制其工程或另装 CAD 内核。进一步铰接修复和完整制作尚未执行；不将未运行方案计为完成。没有上传、发布或平台草稿。
