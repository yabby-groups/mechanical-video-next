# 电影化三维制作

从一处必须看懂的动作设计镜头。安装外观用能看出使用位置和材质的机位。说明性拆解保留至少一个装配参照，从轴向拔出到侧向分离都有明确的用途。观察弹簧、齿面或密封时，可以近看接触，随后回到包括输入和结果的画面。能用固定相机比较状态时，把运动留给机械。

## 现有 Blender 入口

普通 Blueprint 镜头可在已绑定的基础镜头设置 `visual_profile: cinematic-native-v1`。将取景写在已有的 `science.camera_path`、`camera_rig` 或正交取景字段。导演在已有 `studio_lighting` 可调整主光、补光、轮廓光、环境颜色和强度。基础镜头可用同一字段配置 `engine`、`render_samples`、`lights`、`material_overrides` 和 `preserve_materials`。灯的位置、目标与面积以装配最大包络边长除以四为尺度，功率按面积同样缩放。材质覆盖按对象精确匹配。场景背景和可见的地面由布景负责。

| 方案 | 使用方式 |
| --- | --- |
| Workbench | 省略 visual_profile。快速核对几何、视野和运动。 |
| 旧棚拍 | 保留 `printer-ep03-studio-v1` 及其原参数。 |
| EEVEE | 新 profile 的默认发动机。面积光、AgX 与已有 PBR 材质。 |
| Cycles | 在新 profile 选 `engine: CYCLES`。从同构图抽帧确认具体收益与成本。 |
| 原生场景 | 可直接以 `blender/cinematic.py` 的相机、面积光和 shader 函数组合源 Blend。保持原动作和呈现动画各自可检查。用现有分块渲染、音画时钟和 QA。 |

片场材质以原资产为依据。可用拉丝纹理区分金属表面，用粗糙度变化描绘涂层或塑胶，用木纹提供安装情境。保留读懂形状和接触所需的明暗分离。微距镜头先确认上、下游零件各在何处，再决定景深是否会遮掉关键线索。

## 复现门把手样片

以项目根为工作目录，先确保已拥有门把手 `restored-3d/revised` 的实际 Blend、原始帧、专利和 Neil 文件。下面的 Blender 二进制使用本机安装。执行清单和可用本地源见 [实证报告](productions/cinematic-3d-20261122.md)。

```sh
task=output/tasks/door-handle-return-20261121
blender_bin=/Applications/Blender.app/Contents/MacOS/Blender
"$blender_bin" -b "$task/restored-3d/revised/door-handle-return.blend" --python-exit-code 1 \
  --python examples/door-handle-return/cinematic_scene.py -- "$task/cinematic/reproduction" \
  --width 960 --samples 12 --core --revised
PYTHONPATH=. uv run python examples/door-handle-return/cinematic_edit.py \
  core "$task/cinematic/reproduction"
```

`--full` 渲染整个 1215 帧；加 `--revised` 使用约一秒的弹簧座微距。`--motion-patch` 只生成半开源帧 [556, 794) 的局部替换段。对应的 `full --revised` 合成命令需要 `animatic/native-picture.mp4` 作基线，生成逐区间拼接记录。完整预演共用同一段实测 Neil WAV，并保留原创拟音配方和混音检查。相同输入用原配方和同一输出目录可恢复分块；修改素材或镜头时使用新的输出目录，以保留上轮记录。

[镜头库](../config/cinematic-shots.json) 保存技术状态和真实媒体。采样审查用于发现确定的问题，持续的镜头价值由精确 MP4 连续审查确定。并行核对机械资料与画面时，保留各自证据。旧实验的 B/C 记录仍在，引用的 MP4 缺失时，从证据可用的镜头着手。

## 两个题材的复用范围

门把手用了门、饰盖及两次机位关系的定制编排。皂液泵使用相同摄影和材质代码，调整焦距和目标以容纳完整回升。泵的透明边界、活塞、钢球与弹簧仍来自原生源场景。环境、取景、读懂因果所需的部件和装配遮挡由每个题材决定。科学范围和版权继续走原项目验证。
