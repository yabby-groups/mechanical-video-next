---
name: mechanical-animation
description: 使用 Exploded Assembly Studio 参数化制作机械拆解、回装、原理示意镜头和局部预览。
---

# mechanical-animation

使用 blender/scene.py 的固定模板 overall、explode、detail、motion、assemble，不为每集重写动画脚本。先运行 produce.py 的 --phase keys，再 --phase preview。检查 checks.json 的分离间隙、回装误差、投影边界与数学约束。EAS 使用 bpy.ops.eas.set_assembly_position 和 bpy.ops.eas.animate，插件原样保存在 blender/vendor。运动仅支持有齿数依据的固定齿圈 Willis 模板；简化齿廓不代表接触仿真。关键部件按预设色区分。仅修改当前镜头配置以复用其他镜头缓存；配音字幕不进入 3D 哈希。失败立刻停止，只有明确证据与改善指标才能修复：每问题至多两策略，每策略至多两次，无改善即停止。投影通过不等于无遮挡或科学验收。
