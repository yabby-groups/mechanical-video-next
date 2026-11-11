---
name: mechanical-animation
description: 使用 Exploded Assembly Studio 参数化制作机械拆解、回装、原理示意镜头和局部预览。
---

# mechanical-animation

当前视觉参考为用户指定的打印机系列 EP03。优先读取 config/planetary-printer-ep03-style.json：原模板叠加 `blender/studio_style.py` 的 EEVEE 灯光材质预设与斜视相机，不新增场景引擎、不修改齿轮运动原理。先用 `python3 scripts/style_preview.py <config> --phase keys` 检查关键帧，再做单镜头动态预览。render.framing=fullframe 保持输出画幅比例；视觉预设源码进入镜头缓存键，旁白字幕不进入 3D 键。

多 Agent 制作时由 Animation 子代理使用，先读取 Research 与 Asset 的版本化交接。只写自己的 animation-manifest.json、关键帧和镜头媒体，不改脚本或资产方案。通过 `python3 -m mechanical_video_next stage` 获取全局生产锁，禁止并行 Blender。交接记录真实媒体、checks.json 和来源配置 SHA256；预览的完整独立 QA 由另一个线程执行。

使用 blender/scene.py 的固定模板 overall、explode、detail、motion、assemble，不为每集重写动画脚本。先运行 produce.py 的 --phase keys，再 --phase preview。检查 checks.json 的分离间隙、回装误差、投影边界与数学约束。EAS 使用 bpy.ops.eas.set_assembly_position 和 bpy.ops.eas.animate，插件原样保存在 blender/vendor。运动仅支持有齿数依据的固定齿圈 Willis 模板；简化齿廓不代表接触仿真。关键部件按预设色区分。仅修改当前镜头配置以复用其他镜头缓存；配音字幕不进入 3D 哈希。失败立刻停止，只有明确证据与改善指标才能修复：每问题至多两策略，每策略至多两次，无改善即停止。投影通过不等于无遮挡或科学验收。
