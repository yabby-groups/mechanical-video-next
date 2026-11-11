---
name: mechanical-asset
description: 检索、导入和验证可独立拆解的机械装配资产，记录来源许可证并管理模型缓存。
---

# mechanical-asset

先读 config/assembly.json 和 blender/vendor/SOURCES.json。本示例通过 Blender 官方齿轮生成器一次生成教学装配，不建立 CAD 求解器。运行 `python3 scripts/produce.py config/planetary-01.json --phase keys`，检查缓存内 assembly.inventory.json 的部件数、required_parts 和独立网格。外部 GLB 用 `python3 scripts/import_asset.py --help` 导入检查；只有一个整体网格必须拒绝。STEP 需已安装 FreeCAD 做格式转换，不把 STEP 文本当装配。未明确授权或许可证未知的素材只登记，不进入制作。素材证据放 assets/assemblies；可再生成缓存放 work/cache/assets。仅用 `scripts/clean.py` 清理已登记临时文件，原始资产与 output 不可自动删除。
