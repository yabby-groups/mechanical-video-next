# 主动产品检索与选择性拆解验证

新机制任务的 `produce` 入口写入型号、问题、缓存及多语种检索计划。现有 `continue` 在研究交接前执行有限的公共查询，留下去重候选和实际请求记录。从原始页面核实后，以 `reference_library product-ingest` 保存注明位置、哈希、型号、范围和使用权限的观察。候选按同一型号汇总。用 `--lock-product-model` 固定用户指定的不可替换型号。来源拦截继续应用于新线索和正式交接。

Blender 将 `product_assembly` 中指定的连接、拆卸顺序和相对路径编译到原有镜头。每个部件保留安装矩阵与来源标识。可用候选机位按顺序试拍，保持外壳参照和关键零件。剖切只涉及已指定的外壳。拆装与传动各用原有时钟，连续传动镜头可复用同一观察视角选择。

## 真实型号选择

| 核实来源 | 观察范围与选择 |
| --- | --- |
| Panasonic SR-FC106 官方资料 | 规格给出外形 255 × 366 × 210 mm，打开总高 402 mm。说明书印刷第 5 页确认图示为 SR-FC106，标明前部开盖按钮、锅盖、盖加热板、内胆和蒸汽盖。 [规格](https://panasonic.jp/suihan/products/SR-FC106/spec.html) · [说明书](https://panasonic.jp/suihan/products/SR-FC106/support.html) |
| SR-FC106 维修 | 照片 1、6–9、16 显示外观、前罩、ARE05-H64-SJ 锁扣、ARE06-H64 回位弹簧及安装位置。选为同一科学问题的新候选。 [维修文章](https://taakuyu.hatenablog.com/entry/2023/11/29/224804) |
| Midea FC307B 拆解 | 步骤 1、9、11、12 覆盖外形、后盖及锅盖内侧。步骤 3 的锁扣属于可拆蒸汽滤件。 [iFixit](https://www.ifixit.com/Teardown/Midea+FC307B+Rice+Cooker+Teardown/175902) |
| CUCKOO 维修 | 原地址返回错误，按韩文标题找到实际文章。照片和文字讨论铰链区域线束断裂。型号与弹盖力路缺少实证。 [维修文章](https://handyguy.tistory.com/entry/쿠쿠-전기압력밥솥-열림-Eco메시가-뜰-때-직접-수리하는-방법-따라하기) |

在原电饭煲任务下生成了 SR-FC106 的外形及前盖总成。外形包络取自规格，其余建模尺寸依据照片比例估计。公开图片和文档仅用于研究。日、英、中文补查后，同型号后铰链扭簧、两端固定点、受力状态下的脱扣接触和完整运动仍缺来源。整集机构动画保留 BLOCKED。 [证据清单](../../output/tasks/rice-cooker-lid-20261123/research/product-observations.json) · [Blender 资产](../../output/tasks/rice-cooker-lid-20261123/research/sr-fc106/sr-fc106.blend) · [前罩动作 MP4](../../output/tasks/rice-cooker-lid-20261123/research/sr-fc106/sr-fc106-front-cover.mp4)

## 历史对照

- 电饭煲前后第 20 帧的对照显示局部剖切后出现锅腔开口。独立抽样仍无法辨认内部机构。 [旧片](../../output/system-repair-validation/rice.mp4) · [新片](../../output/system-repair-validation/reveal-repair/rice.mp4)
- 垃圾桶后侧镜头露出推杆，但远侧机位遮挡踏板。另用原生 401–547 帧和固定外壳剖切，回放松脚至合盖，踏板、推杆与桶盖同时入画。 [拆装新片](../../output/system-repair-validation/reveal-repair/bin.mp4) · [传动回放](../../output/system-repair-validation/reveal-repair/bin-release/bin-native-replay.mp4)

所有诊断视频均保留抽样审查的覆盖范围。 [现有独立复核](../../output/system-repair-validation/reveal-repair/independent-qa.md)
