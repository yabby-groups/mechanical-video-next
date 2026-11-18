# 原创科普与素材复用升级：集成验证

本轮在现有 reference_library、Blueprint、Producer、Remotion/FFmpeg、3D Provenance 和独立 QA 上扩展；没有增加生产角色、服务或管理系统。当前原则是原创内容优先、自有素材复用优先、外部素材辅助。八个已有角色的名称、模型和推理路由与 HEAD 一致。已有工作区中的知识递进改动保留。

## 实际产物

本地 [18 秒验证片](../../output/asset-first-demo/hybrid-demo-v4.mp4) 为 1920×1080、30fps、540 帧，含三段此前项目制作的 Blender 原生机械动画、Remotion 原生流程动画、既有 Neil 旁白与字幕。没有使用第三方视听片段，也没有把项目 3D 片段称为实拍。本片验证素材复用与混合合成，不是新题材的完整原创作品。

视频 SHA256：`cd0028c0fe99a4ad321404d54e5ca7939c8a95eda4a99db10603afec1904a49c`。

四个镜头分别展示压头用途、底膜收卷、涂层与底膜去向的信息动画、摩擦环与轮缘的运动。每镜头实际入库匹配，视频记录原始 0–4/0–4/0–7 秒区间，原生图解 JSON 没有源视频时段，输出位于 8–11 秒。所有源内容哈希、许可声明/证明、使用范围、匹配回执、实际输出时段、生成方式及音频绑定见 [媒体清单](../../output/asset-first-demo/hybrid-demo-v4.media-provenance.json) 和 [匹配结果](../../output/asset-first-demo/hybrid-demo-v4.library-match.json)。源使用历史写入同一库的 media/uses。v4 复用与 v2/v3 完全相同的媒体及 props 字节；修订来源绑定不额外渲染。

重跑本地验证使用 `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python scripts/asset_first_demo.py --v4`，需要本地历史输入和检查回执。新检出仅提供公共工具，不包含这些本地影片和 CAD。

## 技术回归与独立审查

- 相关回归 77 项：75 通过、2 跳过。
- 全套 394 项：375 通过、4 跳过、15 失败。将未修改 HEAD 导出到临时目录，逐项复跑相同 15 项并全部复现。缺失本地 assembly/config、历史指甲刀媒体，以及既有风格锁不匹配是该基线的边界；没有通过改旧素材或放松门禁消除它们。
- 完整解码、540 帧时间戳的连续 30fps 检查通过。
- Blender 原生场景见证重渲染与完整 Remotion 回放通过，状态 `HYBRID_PROVENANCE_PASS`；六个见证帧的最大 RGB MAE 约 2.00；逐帧 PSNR 最低 49.2 dB；解码音轨一致。该结论没有冒用原版全时间线 3D-only 验收。
- 独立 QA 实际检查 1/6/9/14 秒压缩帧；相同媒体哈希允许 v4 沿用这些观察。另分别完成版权与原创表达审查，不以素材比例判定原创。

详见 [验证记录](../../output/asset-first-demo/validation-report.json)、[来源回放](../../output/asset-first-demo/provenance-replay.json)、[独立版权与原创审查](../../output/asset-first-demo/qa-originality-v1/review.json)。

## 未授予的验收

连续观看、听审、整体理解、完整 TTS 使用权/署名范围仍是 UNKNOWN。本样片复用以前的研究、脚本与配音，不能被当成新选题原创研究和解说的完成证明。版权和原创表达的正式验收没有通过，未发布，也没有承诺会话外后台继续。

正式新任务继续要求本任务独立研究、原创脚本和知识/分镜/视觉设计，分别通过版权、原创表达、机械、产品、连续媒体及理解等既有 QA。不能因为素材来自项目、许可允许复用或技术回放通过，就自动授予原创作品验收。
