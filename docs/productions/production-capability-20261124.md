# 三组机械画面局部回归

以 `950e2a61a1b86f79babc4de350e98d52e7016073` 为基线。对照左旧右新。短片及原生场景保存在 `output/production-capability-20261124`。

| 对照 | 实际变化 | 仍待解决 |
| --- | --- | --- |
| [电饭煲 3.20 秒](../../output/production-capability-20261124/rice-before-after.mp4) | 按 SR-FC106 实物照片 1、6、7、16 修订面罩后缘和按键。0 秒保留整机，1.27–1.90 秒用同方向镜头放大机身显示屏和已移开的面罩。96 帧网格对比无新增表面相交候选。 | 独立抽样认为型号辨识和显示组件与机身的关联仍不足。实物锁扣的受力脱扣和后铰链缺同型号运动证据。 |
| [垃圾桶 4.90 秒](../../output/production-capability-20261124/bin-before-after.mp4) | 同一历史回程的 147 帧。左侧保留踏板、底杆、竖杆与盖。右侧显示上部销槽和下部叉接头的原生近景。相较第一次仅放大同一侧视，盖沿从上部细节视角移出，销和槽露出。 | 独立抽样仍无法确认上部销槽的持续接触及下叉两侧关系。两个局部之间的断开构图可能被误读为断杆。 |
| [门把手 22.60 秒](../../output/production-capability-20261124/door-before-after.mp4) | 在此前紧剪上移除重复顶注。17.37–19.60 秒随原拨片角度画出轴心、作用位置和切向示意。回程源帧及 Neil 混音沿用原候选。两版解码 PCM 完全相同。 | 切向箭头依据历史教学几何，实际受力位置和方向待实证。ASR 将末句定位到 20.72 秒附近，晚于所示回正。实听和感知同步待确认。 |

| 对照 MP4 | SHA-256 |
| --- | --- |
| 电饭煲 | `302e8085e516c0136190fec76ea7c267c3692d1c175db8a6ff08088fef47ba45` |
| 垃圾桶 | `96fcf07abf03d94bc30f062a4abc5832b888e58a965767ae199a8900f68d2f47` |
| 门把手 | `ac6d0d7865b90fcf07b73e07b484f1ee22bd1ae01ed3737ce39473bfd4cf1033` |

沿用观察记录中的构图方法。Branch Education 硬盘 8–14 秒的分层分离保留机身参照，对应电饭煲整机向面罩细节推进。自动铅笔 249–280 秒以同方位实物和剖视保留笔尖参照，本轮重播了约 247–261 秒，对应垃圾桶用同一条竖杆联系侧剖与上下放大。两组样片使用本地原生几何。第三方画面用作研究。 [历史实际观察](system-repair-20261123.md) · [硬盘原作](https://www.youtube.com/watch?v=ZZTC_dXcC2o) · [自动铅笔原作](https://www.bilibili.com/video/BV1zFyQzgEC9/) · [SR-FC106 实拍拆修](https://taakuyu.hatenablog.com/entry/2023/11/29/224804)

新任务的原有 Producer 路径接回参考检索和视频观察。选中的时间码手法进入 Treatment 的场景、预演和正式 Blueprint 的实际镜头，并用精确 MP4 的时间码复核。原生拆解可在同一方向下从整机推进到已选零件。历史案例的两次局部修复结果保存在本地。 [制作契约](../production-contract.md) · [参考交接执行回执](../../output/production-capability-20261124/reference-execution.json)

三个对照完整通过 FFmpeg 解码。浏览器按 1× 播放至末尾，独立 QA 实读精确哈希媒体的时序抽帧。连续视觉判定、实听和首次观众理解保持 UNKNOWN。发布后留存和互动数据尚无。 [独立 QA](../../output/production-capability-20261124/independent-qa.md) · [新垃圾桶播放记录](../../output/production-capability-20261124/bin-native-playback.json) · [电饭煲与门把手播放记录](../../output/production-capability-20261124/playback.json) · [门把手 ASR 时间码](../../output/production-capability-20261124/door-asr.json)
