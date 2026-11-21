# 修正带导演试片与对照

用用户指定的 [B-director-r3.mp4](../../output/creative-director-correction-tape/B-director-r3.mp4) 做基线。先从实际 MP4 抽查 12 帧和完整解码，再查源镜头和测长时间轴，最后制作用于对照的 [新版 MP4](../../output/director-skill-correction-tape/B-director-skill-r2.mp4)。[并排视频](../../output/director-skill-correction-tape/AB-comparison-r2.mp4) 左侧为 R3，右侧为新版，两侧共享同一画面时间轴和音轨。

| 播放时间 | R3 的可见事实 | 导演决定与新版证据 |
| --- | --- | --- |
| 00:00.000–00:02.500 | 00:00.400 的双色标记同框，文字已经提出打滑的问题。 | 保留谜面。它在 00:00.400 的并排采样中仍提供问题与可见线索。 |
| 00:02.500–00:05.867 | 00:02.500、00:05.000 仍用同一组卷和轴的构图，卷径与转角的关系由字幕说明。 | 插入 101 帧等带长对照。00:03.100 可见两卷从各自虚线基准转开，00:05.600 小卷约半圈、大卷约四分之一圈。用 `s = rθ` 的理想条件解释同一时间内所需转角的区别。两种半径是示意值。新版在字幕安全区加深色底，公式仍在底条上方。 |
| 00:05.867–00:10.633 | R3 原有整体镜头随后切到近景。00:08.533–00:09.500 的抽样能见轮缘和色标，另一卷已在画外。 | 回到原有装配构图，再用 video-shotcraft 的减速停留配方。新版 00:08.550 两卷、传动环带和压头同框，00:10.800 落在已稳定的轮缘特写，蓝橙标记与标签可以对读。 |
| 00:10.633–00:25.500 | 00:13.600 和 00:18.300 可见双色标记处于不同相对位置。00:24.200 可见白条留在纸上，回程留在构图内。 | 核心段保留原 Blender 驱动、动作映射、约束及纸面收尾。全段使用 R3 的已测长 Neil 和拟音。 |

## 执行与验证

- [Blueprint](../../output/director-skill-correction-tape/creative-blueprint.json) 由原编译器以 draft 模式生成执行配置。实际 960×540 移动动稿经本项目合成，五镜的运动或图形变化分别覆盖 75、101、79、372、138 个不同解码帧。[移动动稿与检查](../../output/director-skill-correction-tape/preview-build-r2.json)
- Blender 重渲染接触镜头，373 个原生画面帧。既有机械程序摘要与 R3 相等，显式核对了 `time_map`。从原生帧 65 至 373 两个锚点的出框计数都是 0。投影检查覆盖视锥，定点图片补充可见性证据。[原生镜头检查](../../output/director-skill-correction-tape/contact-final-checks.json)
- A 与 B 均为 1920×1080、30 fps、765 画面帧，两版完整解码通过。解码 PCM SHA-256 均为 `a32dd725e857073d882e78fc3a9ab4ba19197ccb418fa6977a5a7aa96ff6d3f7`。并排片 1920×600、30 fps、765 帧，完整解码通过。[高清构建绑定](../../output/director-skill-correction-tape/final-build-r2.json)
- Skill 结构校验和 Remotion TypeScript 检查通过。Python 共运行 503 项，497 项通过、6 项跳过。回归覆盖默认 Producer 引用、摄影机曲线兼容性以及两种 Remotion 路径的角位移图验证。[Python 日志](../../output/director-skill-correction-tape/python-tests.log)

## 审看范围

本次确认的是实际帧中转角对照、整体到局部的空间线索，以及新版字幕区域的可辨性。没有连续观看或听审能力，连续动作观感、音画节奏、观众理解和正式验收仍为 UNKNOWN。纸面收尾引用 R3 使用的现存原生视频和历史渲染记录，旧缓存的逐帧检查已归档清理。高清使用同一已编译动稿的 Remotion 配置及高清素材生成，当前可核对构建绑定和解码结果。

| 文件 | SHA-256 |
| --- | --- |
| B-director-r3.mp4 | `f224366f6219aa83cf36bbe5edafe943e3ff7f4da6a6ac4c124a17e26a82e505` |
| B-director-skill-r2.mp4 | `5dd73bfec627ad484de39bf5f105b19c9ec500213a823b304f8827c8c8d83d77` |
| AB-comparison-r2.mp4 | `fb53771534b1e462aa90b433c43fb5f5500df47cd6c9cced18c4235f87a673a3` |
