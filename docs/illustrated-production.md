# 图片和结构资料制作路线

每条视频研究参考；热度是偏好，不是生产条件。Producer 根据实际资料选择 3D、2D 或 2.5D，无需用户逐步选择。静态资料的内容、部位与结构关系作为复刻依据，分镜记录 reference_region 和 adaptation；视频参考继续记录 reference_time_range。结构文本可据其绘制示意图层，不虚构未提供的结构事实。

在 asset-plan 和 creative-blueprint 交接前执行：

```sh
uv run python -m mechanical_video_next select-route <task> --route 2.5d --reason '结构图适合分层演示'
```

也可在创建任务时使用 `--asset-strategy illustrated`。asset-plan 包含 qualified=true、render_route（2d 或 2.5d）和 source_files（每项 path/sha256）。图片实际可读并绑定哈希，不要求 STEP、GLB、独立实体或接触仿真。冻结配置绑定所选路线及已批准图片。

基础视频配置保留现有 render、voice、asset 标识、storyboard 与字幕字段，增加顶层 render_route；shots 中使用：

```json
{
  "template": "layered",
  "render_route": "2.5d",
  "seconds": 3,
  "background": "#e5e7eb",
  "layers": [{
    "path": "assets/example/lever.png",
    "sha256": "实际文件的SHA256",
    "depth": 1,
    "from": {"x": 0.5, "y": 0.4, "width": 0.5, "rotation": 25},
    "to": {"y": 0.55, "rotation": 0}
  }],
  "camera_motion": {"to": {"x": 0.09, "zoom": 1.1}}
}
```

layers 顺序为从后到前。x/y 是画幅归一化中心，width 是画幅宽度比例，rotation 为角度；还支持 scale 和 opacity。from/to 缺省项保持初始值，旋转围绕图层中心；需要铰点旋转时将图片透明画布中心设在铰点。2.5d 的 depth 与相机平移生成视差，zoom 控制整体推进；2d 忽略相机景深。透明 PNG 可表达独立部件，整张 JPEG 可用于平移与缩放。

`scripts/produce.py` 的 keys/checks/local/preview/final 共用 layered 镜头入口；图层由 Pillow 合成并流式编码，之后复用既有配音、字幕和 Remotion 合成。先检查关键帧及局部运动，再按生产状态进入全片。路径动画是原理示意，是否准确表达讲解由实际媒体检查判断。

本次验证：143 项测试通过；2D 和 2.5D 分别生成 480×270、15 fps、3 秒的技术样片并完整解码。样片为自制色块夹合演示，不是指甲刀结构验收或完整教学成片。位于 output/diagnostics/illustrated-route-smoke，各含 shot.json、media.mp4、contact-sheet.png、checks.json。
