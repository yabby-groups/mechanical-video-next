# 君哥拆机器｜定位纠偏与门锁预演

本文作为 Yale 弹子锁的独立实验保留。现行账号定位和《门把手回正》的恢复记录见
[制作契约](../production-contract.md)和[门把手预演](door-handle-return-restored.md)。

> 拆开机器，看见发明背后的智慧。

《门合上以后》的 40 秒修订动稿按用户判断保留为**失败基线**。这次重新选题为《把钥匙放进口袋》，围绕扁平小钥匙的便携、门锁适配和不同齿高的识别展开。处理稿获得独立文字 PASS。58 秒动稿已经制作、修订并复审，独立视觉审查为 **UNKNOWN**。

[40 秒失败基线](../../output/tasks/door-latch-skill-pilot-media/revised/door-latch-story-preview.mp4) · [58 秒新动稿](../../output/story-development-door-lock/v3/door-lock-story-preview.mp4) · [41 秒并排动态对照](../../output/story-development-door-lock/before-after.mp4) · [门锁任务台账](../../output/tasks/door-lock-story-development/task.json)

## 流程偏差及修改

| 入口 | 原流程偏差 | 现行默认 |
| --- | --- | --- |
| README、AGENTS、制作契约和 Research | 立项优先考虑现象和动作发现。现实需求、历史和改进虽有提示，交接不要求产出研究结果。 | 固定账号定位。先查机器为何出现、使用问题、背景、局限、改进及科学。每项指向事实或具体未知。 |
| Producer、选案与参考入口 | 站外参考检索在先。固定的选案字段与素材优先级容易使最便宜可测的动作变成正片主题。 | 先交整片 Treatment 和因果分镜，按故事需要取参考。用过审故事决定正式资产与媒介。 |
| Director、Blueprint 与资产 | 固定的情节选项、路线评分、摄影棚和机构动作先行，使三维解释容易占据主体。 | 每场根据观众能看到的事件选择媒介。生活、历史、实物、专利、实验和三维剖面各有叙事任务，现有 Blueprint 绑定可执行输入。 |
| Skill-driven 试点及 Review | 试点允许更自由的低清动稿，但文字意见与动稿审查未能在正式资产入口形成两道创意否决。 | 独立文字 PASS 才继续完整低成本动稿。独立视觉 PASS 才进正式资产和渲染。REJECT 退回故事，REVISE 修定位明确的问题，UNKNOWN 保留观测缺口。 |

新建混合任务固定 Story Development 版本，包含沿用 --skill-driven 入口的任务。历史账本保留各自立项版本。创建、恢复、审查和制作共用原台账与既有 QA 角色。Video Review 继续检查实际机械与媒体，Audience Review 保持用户显式调用。 [统一契约](../production-contract.md) · [Producer 入口](../../mechanical_video_next/workflow.py) · [Creative QA](../../mechanical_video_next/creative_selection.py) · [Director](../../mechanical_video_next/director.py) · [Blueprint](../../mechanical_video_next/blueprint.py)

## Treatment 与动稿对照

| | 《门合上以后》｜40 秒失败基线 | 《把钥匙放进口袋》｜58 秒 |
| --- | --- | --- |
| 观众的问题 | 门为什么能推上却不能直接拉开？ | 同样小的两把钥匙，为什么只有一把能转开 203 号门？ |
| 使用情境 | 纸袋人物推门、回拉，最后按把手开门。 | 蓝标钥匙先卡住，黄标钥匙转开同一扇门，最后回到日常携带。 |
| 中段发展 | Yale 和插闩比较留在选题材料。11–32 秒在同一俯视斜舌示意中解释三个动作。 | 6.5–26.5 秒从银行保险锁转到一般用途的扁平小钥匙，再看不同门厚的适配条件。26.5–38 秒比较平边薄片与两把钥匙的齿高读数。 |
| 关键科学 | 斜舌的斜面让位、保持面受挡，按把手退舌。 | 38–50 秒比较错配和对齐。分段弹子的接缝与固定边界对齐后，锁芯获得转动自由。 |
| 回报 | 回到同一公寓与把手。 | 50–58 秒回到 203 号门，锁芯的高度读取解释为什么两把小钥匙会给出不同答案。 |

[失败基线处理稿](../../examples/skill-driven-door-latch/story.json) · [新 Treatment 和视觉分镜](../../examples/door-lock-design-story/treatment.md) · [独立文字审查 v3](../../examples/door-lock-design-story/story-review-v3.md)

并排视频由两个实际 MP4 的原速剪辑区间组成，保留两边的片内字幕。比较视频为静音，完整动稿各自保留音轨。

| 并排时间 | 失败基线源时间 | 新动稿源时间 | 对照点 |
| --- | --- | --- | --- |
| 00:00–00:06.5 | 00:00–00:06.5 | 00:00–00:06.5 | 推门与钥匙在 203 门受阻 |
| 00:06.5–00:18.5 | 00:11–00:23 | 00:13–00:25 | 斜舌图解与历史用途、门厚条件 |
| 00:18.5–00:24 | 无对应区间 | 00:32–00:37.5 | 不同齿高由桌面触点读出 |
| 00:24–00:33 | 00:23–00:32 | 00:39–00:48 | 斜舌退让与弹子接缝对齐 |
| 00:33–00:41 | 00:32–00:40 | 00:50–00:58 | 按把手开门与钥匙归袋 |

## 实际审查结果

文字初审 REVISE，要求解决门号和两把钥匙的追踪问题，补充可定位的机构证据。最终稿改成一扇门、两把有标记的钥匙，引用 1861、1865 两项原始专利，获独立文字 PASS。 [初审](../../examples/door-lock-design-story/story-review.md) · [最终审查](../../examples/door-lock-design-story/story-review-v3.md)

首个完整 58 秒版的独立动稿审查给出 REVISE。44 秒的对齐字幕早于接缝实际对齐，53、57 秒的钥匙标记和归袋动作不清。修订调整了视线、字幕与手部动作。独立复审在 44.9、46.3 秒看到两个接缝对齐，48.9 秒看到锁芯转动，55.2、57 秒钥匙已从手边消失。两个修订区间有实测像素变化。关键接触、钥匙身份接力、连续归袋、节奏和听感仍为 UNKNOWN。 [首个完整动稿](../../output/story-development-door-lock/v2/door-lock-story-preview.mp4) · [REVISE 报告](../../examples/door-lock-design-story/visual-review-v2.md) · [修订版复审](../../examples/door-lock-design-story/visual-review-v3.md) · [画面修订测量](../../output/story-development-door-lock/v3/revision-measurement.json)

在实际抽帧中，历史用途、门厚和桌面对照承担了中段发展的工作，说明两版已有可见的叙事结构变化。完整创意效果仍依赖正常速度下能否看清动作和因果。当前审片能力只有抽帧及技术解码，创意验收为 UNKNOWN。技术核对覆盖完整 58 秒、1,740 帧和 48 kHz Neil 音轨，音频比较覆盖最后一句。 [技术记录](../../output/story-development-door-lock/v3/technical-review.json)

## 科学、历史和制作依据

- 美国国家发明家名人堂记载，Linus Yale Jr. 先改良银行保险锁，后来转向一般用途的锁，改进父亲的小钥匙弹子设计。保险柜、走廊和人物动作是原创情境，人物动机、对话与完整商业传承缺少本片证据。 [NIHF 人物档案](https://www.invent.org/inductees/linus-yale-jr) · [本地存档](../../output/story-development-door-lock/sources/nihf.html)
- 1861 年专利 31,278 开篇列举抽屉、壁橱和橱柜。说明书对图 4、7–11 的解释支持分段销、弹簧、钥匙抬升和旋转。1865 年专利 48,475 的引言和安装段支持适应不同门厚，薄钢钥匙段描述了接缝与锁芯外周齐平。门厚镜头比较装配条件，省略专利的内部安装机构。 [1861 年专利](../../output/story-development-door-lock/sources/US31278.pdf) · [1865 年专利](../../output/story-development-door-lock/sources/US48475.pdf)
- 桌面对照只比较同一基准下的边缘高度。两组弹子的通用剖面说明转动约束，省略侧槽、门栓传动以及具体产品尺寸。接触按钥匙轮廓和中心线生成，三维完整碰撞和实际受力仍待验证。专利图和人物档案用作参考。影片画面由新建几何生成，配音沿用 Neil。 [事实与出处](../../output/story-development-door-lock/research.json) · [Blender 场景程序](../../examples/door-lock-design-story/scene.py) · [剪辑源](../../examples/door-lock-design-story/edit.json)

基线 SHA-256 为 f874576cd6fecc5e0bb00f3abe9d7659109c2b9f1d6209d9936aefff0b2d468a。
复审版 SHA-256 为 d4b426f2b7a3dc7ad8a5acef96b0874e23cdf2b2618cb864953b41c2e11497a6。

## 进入正式制作的条件

独立审查需按正常速度看完同一版的 58 秒 MP4。重点复核错钥匙阻挡、正确接缝对齐后的转动、203 门切回和钥匙实际入袋。实听用于判断 Neil 发音、节奏与声画。局部问题走 REVISE，整片设计故事无法成立时走 REJECT 并回到 Treatment。视觉 PASS 后进入正式资产、原生动作验证、正式 Blueprint 和最终 QA。
