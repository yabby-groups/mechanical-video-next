# 镜头配方

## 接近接触面后留观测时间

video-shotcraft 的 `PullBackIsolation` 在运动段使用 cubic ease-out，随后切换为固定画面的停留段。修正带改成从两卷进入供带轮缘，保留同一接触位置并减速停定。原配方的卡片、淡出、文字、音乐和时间常数由本片自己的机械状态、声画帧和镜头设计取代。依据和许可见文末。

1. 两个实体状态先过固定机位检查。标出首帧需要看见的轴、轮缘或外壳和进入后需要对读的两个锚点。
2. 在 `director.presentation.camera_path` 中填写首帧位置 `progress: 0`、落定位置、末帧位置 `progress: 1`。首段起始 pose 使用 `easing_to_next: "ease_out_cubic"`。第二和第三 pose 保持相同的 `target`、`direction`、`width`。Blender 在正交镜头插值机位和取景宽度，在原有透视 rig 路线按固定焦距更新机位。
3. 用 `camera_framing.scale_mode: "locked"`、两个有来源的 `anchors` 和落定后的 `observation_window` 让接触前后可比较。需要外壳参照时调整首帧位置和宽度。当前后两镜用到同一部件时，看切点是否保留其识别特征。
4. 下面是修正带实测片中的 `camera_path`，`target` 是该相对构图模式的画面偏移，`width` 是锚点包围盒的倍数。每个选题重新验证锚点位置、窗口和遮挡。

~~~json
[
  {"progress":0,"target":[-0.20,-0.20,0],"direction":[0.05,-0.55,1],"width":17,"easing_to_next":"ease_out_cubic"},
  {"progress":0.17204301075268819,"target":[0,0.08,0],"direction":[0.05,-0.55,1],"width":3.35},
  {"progress":1,"target":[0,0.08,0],"direction":[0.05,-0.55,1],"width":3.35}
]
~~~

## 其他可迁移的拍法

- 动作已清楚时用定机位和带基准的稳定尺度。读物体相对运动时，让轮缘、接触处和运动见证标记同框。运动只在需要改变观察条件时发生。
- 发现跨切点丢失时先用同一零件的轮廓或方位做视觉对位。场景里有需要同时清楚的相邻零件时，保持它们可辨，转场只在观察完成后发生。
- 等条件对照用现有 Remotion `angular_comparison`。声明共同带长与两种半径，让两个角位移同时开始，以相同时间归一化。在画面标明原理示意，回到原生装配验证实际要讲的关系。FFmpeg 对照时保持同一时间轴并保留可用于单独查看的两版。

镜头时间曲线来自 Vincentwei1021/video-shotcraft 的 `demos/camera/tension-camera-moves/PullBackIsolation.tsx`，提交 `075b548c2405a07b77129eb448b0b504fc60dea3`。本项目修改了方向、起止尺度、媒介和节拍，并翻译了相机曲线至 Python。 [上游源码](https://github.com/Vincentwei1021/video-shotcraft/blob/075b548c2405a07b77129eb448b0b504fc60dea3/demos/camera/tension-camera-moves/PullBackIsolation.tsx) · [Apache-2.0](LICENSE-video-shotcraft.txt)
