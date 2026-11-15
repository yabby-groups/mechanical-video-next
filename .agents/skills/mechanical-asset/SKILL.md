---
name: mechanical-asset
description: 检索、导入和验证可独立拆解的机械装配资产，记录来源许可证并管理模型缓存。
---

# mechanical-asset

未来新任务优先选择可信、匹配且可合法使用的现成媒体，其次检查现成 CAD 装配；仅在没有合格现成内容且有可靠技术依据时自主建模。先查本地已验证参考与资产缓存，再补网络。记录候选、许可范围、未采用原因、具体机构与实际复用口径，不能把许可未知或外观猜测标为合格。遵循 docs/reference-first-contract.md；历史任务保留原策略与状态。

多 Agent 制作时由 Asset 子代理与 Research 并行准备，只输出自己的 asset-plan.json。记录 qualified、实际 model.path/model.sha256、independent_meshes、missing_required_parts、来源与许可、可复用镜头和制作路线。只有实际检查过的资产可合格；无合格资产时 BLOCKED，不生成虚构复杂结构。Producer 用版本化 handoff 交接，不覆盖其他角色产物。

先读 config/assembly.json 和 blender/vendor/SOURCES.json。本示例通过 Blender 官方齿轮生成器一次生成教学装配，不建立 CAD 求解器。运行 `uv run python scripts/produce.py config/planetary-01.json --phase keys`，检查缓存内 assembly.inventory.json 的部件数、required_parts 和独立网格。外部 GLB 用 `uv run python scripts/import_asset.py --help` 导入检查；只有一个整体网格必须拒绝。STEP 需已安装 FreeCAD 做格式转换，不把 STEP 文本当装配。未明确授权或许可证未知的素材只登记，不进入制作。素材证据放 assets/assemblies；可再生成缓存放 work/cache/assets。仅用 `scripts/clean.py` 清理已登记临时文件，原始资产与 output 不可自动删除。


## Compressed visual evidence
Before inspection run uv run python -m mechanical_video_next.qa_images SOURCE (video: --times T1 T2 T3 T4). Read returned WebP/JPEG qa_path only, not source PNG. Reuse work/qa-images cache paths. Maximum four frames and one contact sheet per round; select chapter/motion events. Use prepare_crop for unreadable regions; retain UNKNOWN until adequate evidence. No inline/base64 images in handoffs. Production paths are bindings, not image-read instructions. Use record_reads only after actual tool reads; byte savings are not token savings. Static images never replace numerical CAD, continuous-motion or listening checks. Producer forwards paths, hashes, timecodes and conclusions.
