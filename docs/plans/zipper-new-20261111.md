# 全新拉链视频制作记录

用户要求“不要管旧版的，重新制作，全新的”。本任务独立重新研究、检索源模型、编写文案和配置，没有复用旧拉链的模型、脚本或媒体。当前 **FAILED / 未出合格成片**，禁止把局部预览当成交付。

任务目录：`output/tasks/zipper-new-20261111/`。新文案六镜头，Neil 原速，横屏，打印机 EP03 灰色摄影棚视觉；未调用新文案 TTS、未合成全片、未上传或发布。

## 新来源与实际资产

- YKK 拉链技术说明、Sundback US1219881A 及 US9622550B2 支持交错链牙、Y 形导向和反向分流的原理。
- 新模型：[Yet Another Zipper](https://www.thingiverse.com/thing:2338290)，msadler2，CC BY 4.0。原始 STL SHA256：`c561776892456754a680d594de0b44235d0ba7ea9a1f17156a3c447e65e6cda8`。
- 源模型是放大可打印教学模型，不是工业金属拉链 CAD。源牙头裁切、封口、实例化；连接带和分隔舌是来源支持的简单示意几何。署名和修改说明见任务内 `editor/credits.txt`。
- 最新实际装配含 22 个闭合独立网格，边界/非流形计数为零；Asset v6 只认可几何局部检查，明确不认可动态和最终制作。

## 动作验收失败

问题 `ZIPPER-CORE-PATH-001`：链牙沿导向路径运动时发生真实穿插。已保存两种策略、各两轮的基线、参数与结果，详见任务内 `core-repair-ledger.json`。最终冻结配置为 `config/zipper-new-path-s2a2-v2.json`，不是正式可制作配置。

最终关闭镜头按 30fps 检查 270 帧，既有检查对覆盖对向牙、同侧相邻牙、导向件和分隔舌。最后修正消除了导向件、同侧相邻牙及分隔舌的候选，但仍有 482 个对向牙 pair/frame 事件。独立 QA 用严格线段穿越三角面内部、端点位于平面两侧的数值见证复核，482 个事件均存在严格穿越，共 15300 个三角面多边形对见证，不是单纯包围盒候选。证据：任务内 `qa/exact-crossing-diagnostic.json`，含输入 SHA256、帧、交点、重心坐标、容差、正负控制与 Blender 5.2.3 构建信息。此检查不推断受力或连续帧间行为。

遵守 `AGENTS.md`：“每问题最多两策略各两轮，无改善停止。”本问题修复次数已达上限，已停止生成并将任务置为 FAILED，没有开启第三种策略或自动重试。新候选未渲染，因此其视觉/完整观看/听审仍为 UNKNOWN；初版局部媒体仅保留为失败基线。

## 可复核产物

- `research.json` / `script.json` 及不可变 handoff：全新事实与六镜头文案。
- `asset-plan.json` / Asset v6：实际源模型、许可、网格与资产边界。
- `animation/preview.mp4`：初版无声局部失败基线，不能发布。
- `qa/exact-crossing-diagnostic.json` / `core-repair-ledger.json`：最终数值证据与修复限额。
- `stage-*.log` / `output/runs/`：工具耗时、缓存及空间采样；未取得的 Token、费用、人工介入计量为 null。

工程验证：58 项 Python 测试通过，Remotion TypeScript 类型检查通过。这些结果不代表运动或媒体验收通过。
