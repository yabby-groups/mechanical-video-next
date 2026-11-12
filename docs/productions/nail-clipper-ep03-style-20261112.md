# 指甲刀三路线 EP03 风格修订

本轮按用户提供的 `机械系列_EP03_发布包/EP03.mp4` 优化全部三版，保持横屏 1920×1080、30 fps、38.2 秒、共享 Neil 旁白与已验证 CAD/规定运动。参考 SHA256 为 `1fa11d7a5240611bd1f4adde237154a10bfab5f7dac41fb1e34eae3d0057351b`；实际抽帧比较，不声称完整观看或听审。

## 已实施

- 统一蓝灰空间、银/深金属与少量青橙，移除常驻大标题、路线徽章与字幕黑底，保留片头/结尾、必要标注及底部白字描边字幕。
- 2D 保持平面机构图；2.5D 保持分层体积、遮挡、剖示与投影视差，均用实际机构局部取景代替独立放大框。
- 3D 取消把原生画面缩至约 38% 画布面积的合成，直接全幅输出；使用原生相机局部取景与逐部件材质。`camera_focus_region` 是米制编辑取景框，相关投影检查仅涵盖该区域，其他镜头仍检查完整装配。
- 剪切道具使用外侧主体固定、内侧短尖片脱落的关系。3D 教学指甲薄片不进入 CAD 零件库存，分离为规定路径，不是断裂、材料或接触仿真。
- 保留既有 Blender 网格运动对齐验证；样本检查不等同于完整科学验收。

## 记录与恢复

本轮进度、输入/输出哈希、缺陷和下一步保存在 `output/nail-clipper/shared/style-optimization-state.json`。旧成片及回执备份在 `shared/style-baseline-v1/`，初版新风格 3D 原生关键帧/检查/预览在 `shared/style-3d-baseline-v1/`。独立 QA 使用递增版本的 `shared/qa-style-*.json`，不覆盖旧失败证据。

共享图解配置：`config/nail-clipper-visual-style.json`；原生 3D 配置：`config/nail-clipper-studio-style.json`。图解配置和 3D 参数/渲染源码均绑定对应缓存。配音不重新生成；旁白/字幕不进入原生 3D 镜头缓存。

所有 Python 使用 `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run ...`。Blender 使用现有 `work/production.lock` 串行执行。缓存清理仅通过 `scripts/clean.py`，保留锁、保护和任务引用；本轮已归档的缓存才按精确 key 清理，清理清单单独保存。

## 验收边界

完整规格、解码和音轨一致性与实际画面抽样分别记录。无法完成的连续观看、听审和完整科学验收保留 UNKNOWN，不把技术通过或风格修订称为全面验收。最终路径保持 `output/nail-clipper/{2d,2_5d,3d}/final.mp4`、`compare.mp4`、`preview.jpg`、`report.json`。恢复计划及最终统计以本轮状态文件和 report 为准。

## 本轮实际结果

三版完整 MP4 和竖屏三版同步对比已实际输出。三版均为 1920×1080、30 fps、1146 帧、38.2 秒；对比为 1080×1920、30 fps、38.2 秒。独立完整解码通过，三版 Neil 解码 PCM 一致；每版抽样 14 个时间点，对比抽样 8 个时间点，未见新的明确阻断缺陷。连续视听及完整科学验收仍 UNKNOWN，状态不是 COMPLETED。

本轮从状态登记到独立报告完成约 40.7 分钟。首次高清输出耗时分别为 2D 18.877 秒、2.5D 55.196 秒、3D 1169.515 秒（其中原生六镜头合计 1151.494 秒）。记录了五类已处理缺陷，未将其冒称完整修复轮数；全局修复次数、人工干预、Token 和费用无完整计量时仍为 null。161 项工程测试通过。

缓存输入健壮性补充触发过一次轻量重合成，未重复 Blender 重渲染，三个 MP4 哈希全部保持不变。随后真实恢复验证为四步缓存命中、零步执行；仅 QA/统计变化时也复用已检查的 `compare.mp4`，防止更新报告使对比检查的哈希失效。证据为 `shared/style-resume-verification.json`。

恢复命令：`UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python -m mechanical_video_next route-run output/tasks/nail-clipper-three-routes-20261111 --plan output/nail-clipper/shared/style-resume-plan.json`。本修订计划复用已生成 CAD 和配音，不请求 TTS 或重新生成实体。
