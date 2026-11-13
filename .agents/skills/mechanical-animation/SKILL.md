---
name: mechanical-animation
description: 使用 Exploded Assembly Studio 参数化制作机械拆解、回装、原理示意镜头和局部预览。
---

# mechanical-animation

图片／结构路线：配置 render_route=2d 或 2.5d，每镜头 template=layered 并设置同名 render_route。layers 含 path、sha256、from/to（x/y 为归一化中心、width 为画幅宽度比、scale、rotation 角度、opacity），2.5d 另设 depth 与 camera_motion.from/to 的 x/y/zoom。scripts/produce.py 使用 scripts/layered.py 输出实际 MP4，无需 Blender、STEP 或独立实体。先检查关键帧与局部动作，再复用现有配音、字幕与合成。规定路径标注原理示意，不冒称接触仿真。

当前视觉参考为用户指定的打印机系列 EP03。优先读取 config/planetary-printer-ep03-style.json：原模板叠加 `blender/studio_style.py` 的 EEVEE 灯光材质预设与斜视相机，不新增场景引擎、不修改齿轮运动原理。先用 `uv run python scripts/style_preview.py <config> --phase keys` 检查关键帧，再做单镜头动态预览。render.framing=fullframe 保持输出画幅比例；视觉预设源码进入镜头缓存键，旁白字幕不进入 3D 键。

多 Agent 制作时由 Animation 子代理使用，先读取 Research 与 Asset 的版本化交接。只写自己的 animation-manifest.json、关键帧和镜头媒体，不改脚本或资产方案。通过 `uv run python -m mechanical_video_next stage` 获取全局生产锁，禁止并行 Blender。交接记录真实媒体、checks.json 和来源配置 SHA256；预览的完整独立 QA 由另一个线程执行。

使用 blender/scene.py 的固定模板 overall、explode、detail、motion、assemble，不为每集重写动画脚本。先运行 produce.py 的 --phase keys，再 --phase preview。检查 checks.json 的分离间隙、回装误差、投影边界与数学约束。EAS 使用 bpy.ops.eas.set_assembly_position 和 bpy.ops.eas.animate，插件原样保存在 blender/vendor。运动仅支持有齿数依据的固定齿圈 Willis 模板；简化齿廓不代表接触仿真。关键部件按预设色区分。仅修改当前镜头配置以复用其他镜头缓存；配音字幕不进入 3D 哈希。失败保存证据并由 Producer 自主诊断修复，不设总轮次上限；无改善更换策略，重跑实际动作及独立复验。投影通过不等于无遮挡或科学验收。


## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
