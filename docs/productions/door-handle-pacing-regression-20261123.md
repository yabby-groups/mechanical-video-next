# 门把手节奏回归

历史样片来自 `door-handle-return-20261121` 的路线 B 修订预演。账本为生产契约 v6，未固定正式时长版本。回归针对这份 40.50 秒 MP4。11 月 22 日单独打包的 125 秒版本属于正式时长 v1 的另一条制作记录。两者的本地哈希和用途分别列在下方。

| 样片 | 时长 | SHA-256 |
| --- | --- | --- |
| [路线 B 原版](../../output/tasks/door-handle-return-20261121/cinematic/animatic-revised/door-handle-animatic.mp4) | 40.50 s | `1bb6c1d936aeac0420ea81cea8022cd4b81490d1662a67db64e154ae567948f1` |
| [候选预演](../../output/door-handle-pacing-regression-20261123/door-handle-pacing-candidate.mp4) | 22.60 s | `5038ce07704a7e4b5bf478127196cb9de63cc07d6945bb17f9d01b68f0ef86b4` |
| [完整动态前后对照](../../output/door-handle-pacing-regression-20261123/full-before-after.mp4) | A 版后接 B 版，40.50 s 切换 | `978ec29bef4ee7a640a19593415fe09f6672ef888bce3db5ce4b62afcd28214a` |

## 实测变化

| 段落 | 原版时间 | 候选时间 | 改动与保留 |
| --- | ---: | ---: | --- |
| 安装状态下压 | 0.767 s | 0.033 s | 删除动作前 22 帧。功能结果约 3.133 s 提前到 2.400 s |
| 开场回正后的等待 | 3.200–5.300 s | 约 2.467–3.300 s | 保留观众辨认水平姿态以及原速 Neil 句尾，随后进入弹簧结构 |
| 底座拆解与方轴说明 | 5.300–15.533 s | 3.300–7.300 s | 从拆解已能定位弹簧和端座处进入。方轴如何传动移到原生下压镜头讲解。删除一段提前讲转动的旁白 |
| 内部下压的旁白 | 14.467 s 开口，15.700 s 动作 | 7.667 s 开口及动作 | 开口提前量从 1.233 s 缩至一帧内。保留拨片、方轴与把手的同步转动 |
| 压住与松手 | 23.800 s 开口，24.367 s 回程 | 14.400 s 开口，14.533 s 回程 | 删去 54 个相同机构状态帧。保留载荷状态观察。回程开始即呈现首个因果答案 |
| 内部回正与力矩 | 29.433–33.000 s 为回正后的停留 | 19.600–22.600 s 继续力矩解释后结束 | 复用完整原速解释，力矩说明从 17.367 s 开始，覆盖回程和静止状态。回正后尾段缩短约 0.57 s |
| 结尾外观再演 | 33.000–40.500 s | 删除 | 删除重复的外观循环和两句旁白 |

全部 1,215 帧的 Blender 角度与弹簧形变权重从历史场景求值。候选保留按压和回程的原生帧顺序与 30 fps 播放速度。被移除的中间 54 帧与拼接两侧的把手、方轴、两拨片和弹簧权重相同。留存帧上活动端随方轴转动，固定端保持原位。技术检查核对解码帧及时间戳、原生画面对应、知识覆盖和 AAC 对实测 Neil 加原拟音的样本对齐。678 帧完整通过，最小参考 SNR 为 28.62 dB。属于 US7900978B2 标定的教学模型，力值和实际回位速度没有实物测量。 [旧版逐镜审计](../../output/door-handle-pacing-regression-20261123/before-audit.json) · [候选逐镜审计](../../output/door-handle-pacing-regression-20261123/after-audit.json) · [技术回执](../../output/door-handle-pacing-regression-20261123/technical.json)

独立 QA 对精确 MP4 重算哈希并查看定点画面，确认了前置等待缩短和重播段删除。力矩在候选中主要靠文字和旁白，方轴传动可读性仍待连续复审。持续原速观看、实听和感知验收为 **UNKNOWN**。平台留存、互动与关注属于发布后的验证。 [独立 QA](../../output/door-handle-pacing-regression-20261123/independent-qa.md)

独立审查使用的两份审计以原 SHA-256 保留。当前审计另外记录逐镜头原生轨迹和 Neil 实测区间，审查对应的 MP4 字节相同。 [独立 QA 的原版输入](../../output/door-handle-pacing-regression-20261123/before-audit-qa-input.json) · [独立 QA 的候选输入](../../output/door-handle-pacing-regression-20261123/after-audit-qa-input.json)

## 其他本地版本

| 作品 | 本地版本与任务契约 | SHA-256 |
| --- | --- | --- |
| 门把手 | 125 秒观众优化版，正式任务 v6、时长 v1。本地发布包与输出文件哈希相同 | `9b8900f24b01ced767849200ddffc3cb2924f9d98cf344c3d4b883fd2afab236` |
| 皂液泵 | 65.4 秒修复版，生产契约 v1。本地发布包与 closure-revision 输出哈希相同 | `477a3ad1b4b14ee1144ee3947c14f669cddae4612fe9b0ef1a40edf53e02e736` |
| 脚踩垃圾桶 | 全片紧剪 r12，任务为生产 v6、时长 v1。存在本地候选 | `009dddac831e695d700bbfbda7a99e814135272b7dda1b09001fdd1d5c8cb1bf` |

平台在线文件的字节版本仍待核对。11 月 23 日复盘中的作品指标属于对应的历史数据快照。 [运营复盘](../plans/operations-growth-review-20261123.md)

## 复现

使用同一历史场景、源帧与缓存 Neil，输出到指定目录。完整审计分别读各自的 MP4、Blueprint、Neil 收据和原生状态清单。

```sh
out="$PWD/output/door-handle-pacing-regression-20261123"
base=output/tasks/door-handle-return-20261121/cinematic/animatic-revised
mkdir -p "$out"
/Applications/Blender.app/Contents/MacOS/Blender -b "$base/scene.blend" \
  --python-exit-code 1 --python examples/door-handle-return/pacing_native_samples.py -- "$out/native-motion.json"
PYTHONPATH=. uv run python examples/door-handle-return/pacing_regression.py "$out"
uv run python -m mechanical_video_next.pacing "$base/door-handle-animatic.mp4" \
  "$out/before-blueprint.json" --states "$out/before-states.json" --output "$out/before-audit.json"
uv run python -m mechanical_video_next.pacing "$out/door-handle-pacing-candidate.mp4" \
  "$out/after-blueprint.json" --states "$out/after-states.json" --output "$out/after-audit.json"
```
