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
