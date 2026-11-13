---
name: mechanical-asset
description: 检索、导入和验证可独立拆解的机械装配资产，记录来源许可证并管理模型缓存。
---

# mechanical-asset

新制作的默认模型来源已改为自主参数化 CAD。先读 `.agents/skills/mechanical-research/SKILL.md` 和 `.agents/skills/cad/SKILL.md`，由 MechanicalResearch + CAD 生成独立实体与 STEP/GLB。网络模型下载不是默认路线，登录失败不阻断 CAD。下文导入流程只适用明确选择的既有资产或历史任务。新任务机械门禁独立于视频门禁，每缺陷不设自动修复总轮次上限，无改善更换策略并保留历史。

多 Agent 制作时由 Asset 子代理与 Research 并行准备，只输出自己的 asset-plan.json。记录 qualified、实际 model.path/model.sha256、independent_meshes、missing_required_parts、来源与许可、可复用镜头和制作路线。只有实际检查过的资产可合格；无合格资产时 BLOCKED，不生成虚构复杂结构。Producer 用版本化 handoff 交接，不覆盖其他角色产物。

先读 config/assembly.json 和 blender/vendor/SOURCES.json。本示例通过 Blender 官方齿轮生成器一次生成教学装配，不建立 CAD 求解器。运行 `uv run python scripts/produce.py config/planetary-01.json --phase keys`，检查缓存内 assembly.inventory.json 的部件数、required_parts 和独立网格。外部 GLB 用 `uv run python scripts/import_asset.py --help` 导入检查；只有一个整体网格必须拒绝。STEP 需已安装 FreeCAD 做格式转换，不把 STEP 文本当装配。未明确授权或许可证未知的素材只登记，不进入制作。素材证据放 assets/assemblies；可再生成缓存放 work/cache/assets。仅用 `scripts/clean.py` 清理已登记临时文件，原始资产与 output 不可自动删除。


## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
