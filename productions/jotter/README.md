# 按压式圆珠笔的工作原理

- 选用派克乔特（Parker Jotter）。查阅 Bill Hammack 的实物拆解与机构讲解，抽看约 0:49 到 3:49 之间的关键画面，并查阅 Hackaday 的机构说明。实物参考支持按钮、笔芯、弹簧、旋转凸轮与导向止挡的关系。该型号在国内的普及程度未核实。 [实物参考](https://www.youtube.com/watch?v=MhVw-MHGv4s) · [机构说明](https://hackaday.com/2015/09/22/how-retractable-pens-work/)
- `scene.py` 保存可编辑的原创 Blender 场景。为看清接触，剖视省略部分外壳，放大凸轮和笔尖，简化齿形、弹簧和球座。动画演示两次按压以及滚珠将油墨带到纸面的原理。模型尺寸、材料、油墨运动与实物公差保留为教学示意。引用的视频画面仅供研究。
- `narration.txt` 是实际 Neil 配音稿。`edit.json` 记录配乐和拟音位置。按压声由 FFmpeg 合成。配乐使用项目自产的 CC0 曲目 Quiet Link: Curiosity。 [配乐许可](../../assets/audio/bgm/starter/CC0.md)
- 本次导出为 64.43 秒，1920×1080、30 fps。完整解码成功，16 条字幕与配音文本核对一致。抽看 16 帧，覆盖开场、拆解、两次按压、滚珠出墨和结尾。音轨比对确认配乐进入成片。连续观感、发音和配乐是否遮盖人声待人工确认。MP4 的 SHA-256 为 `d475aff7f8d93e78a22df17d5e39fff178a5fda6c7c9bfe5327fbd1ae66ac1b4`。
