# 全链路升级与实际验收记录 · 2026-11-18

本次沿用现有原生 Producer、角色路由、Handoff、状态机和制作工具，未增加
调度服务或后台。最终验收状态以本文末尾的实际媒体与任务 QA 为准。

## 实现范围

- 统一生效入口为 `docs/production-contract.md`。旧规则原文归档，新任务显式
  固定 mixed-original-v1，历史任务按原版本读取。扩展现有任务、研究、
  Blueprint、派生配置、build 和来源清单，不另建事实账本。
- Research 保存来源位置、具体实施例、事实类型、假设和局部未知。
  非机械现象绑定有边界的概念/数学模型，不伪造零售产品身份。
- Blueprint 保存原创问题、矛盾、答案及镜头知识增量、可见动作、选择理由、
  构图、光照、衔接、素材决策和实测配音时轴。
- 在现有 Blender 镜头系统中扩展共同时间映射、透明度、求值后几何约束和
  柔性带材轨道；保留剖切、跟随、轨迹、状态和场线等已有能力。规定路径
  属教学动画，不等于接触、材料或流体仿真。
- Remotion 增加双来源分屏独立许可清单、数据关键帧、手机字体检查和实际
  浏览器文字碰撞检查；跟随坐标、公式、放大、字幕继续使用原有合成层。
- Neil 先按字体实测拆分句子，再合成并记录真实时间；音频缓存加锁，短句
  动态处理使用独立缓存策略，保留原始音频。字幕修改不触发 CAD。
- 成片修订工具逐帧比较声明区间的实际解码画面，拒绝改名、元数据或仅
  重编码充当视觉升级。像素差异与独立质量判断分开记录。
- 六个独立质量维度绑定精确媒体。UNKNOWN 允许有依据的技术制作，不能
  授予正式 COMPLETED / DELIVERED。历史失败和修复证据保留。

具体场景能力及尚未验证的边界见
[能力审查](workflow-capability-coverage-20261118.md)，代码审查见
[独立集成复核](workflow-upgrade-independent-review.md)。

## Level 1：基础功能

2026-11-18 最后一次完整回归：416 tests，OK，5 skipped；TypeScript
`tsc --noEmit` 和 `git diff --check` 通过。日志：
`/private/tmp/mechanical-upgrade-final-regression-v4.log`。新增两项回归使用真实
proof/manifest 序列化与校验，拒绝契约字段遗漏/篡改及第二分屏来源的
权利/区间遗漏或篡改；临时媒体与模拟 probe 不冒充实际渲染。

跳过项涉及未随仓库保存的历史集成媒体/冻结输入和需要显式启用的 Blender
运行测试。实际新片另有真实 Blender 执行证据，不能倒填成历史测试 PASS。
批准截图未更换，历史风格锁未通过改写哈希消除差异。跨任意新主题的质量
自动保证尚未成立。

另对剖切、跟随、场线、流线、透明度/共同时间映射完成五个实际Blender
渲染回归。实际为1120×720/30、各30帧（沿用旧横向面板默认值），对应
绑定回执见能力审查；不是正式影片或物理/感知验收。

## Level 2：实际全链路

验收任务 `output/tasks/workflow-acceptance-20261118`：修正带为什么越用卷径
越不同，带子却能保持收紧？采用 Sanford US8746316B2 Figs.1–4C 的单一
专利实施例，不声称对应某零售 SKU，不拼接其他机构。

实际执行了来源检查、原创脚本、导演分镜、既有资产检查与复用、局部弹性
几何修正、Neil 合成/测时、Blueprint 编译、Blender 镜头、完整动态工作片、
Remotion 合成和独立 QA。13 镜头共 4417 帧，147.233 秒视频；9 个原生
3D 镜头与4个数学/信息画面。单片 `author_plan.py` 是这条作品的创作输入，
不作为公共引擎或预制全片媒体入口。

首次完整工作片出现图表遮挡；保留 FAIL 后修改信息图保留区域。实际新旧
媒体逐帧比较见任务 `preview-revision-comparison.json`；独立 QA 只对实际
查看的 72s / 96s 帧关闭静态遮挡，完整连续动作、听审和理解不推断 PASS。
之后首答案时间字段更正属于元数据修正，不宣称又一次视觉升级。

## Level 3：完整媒体与正式验收

实际已生成以下完整产物；任务处于 `FINAL_CHECKING`，正式验收未完成，
未执行 `record-delivery`，没有记录 DELIVERED。

- [完整 MP4](../../output/workflow-acceptance-20261118-blueprint-1e5165c30fbf9457-final.mp4)：
  1920×1080、30fps、4417帧、147.233333秒视频、147.243秒容器，H.264/AAC。
  SHA256 `d56f96f81d419351e6335604832930894e1dc7500ed185d22798f0fba0eca806`。
- [3:4封面](../../output/tasks/workflow-acceptance-20261118/cover/portrait_cover_3x4.png)、
  [4:3封面](../../output/tasks/workflow-acceptance-20261118/cover/landscape_cover_4x3.png)。
  独立审查发现竖版空白过大后，仅修复封面布局，补入同片110秒弹指局部。
  旧FAIL、旧图和中间版本保留于任务 `qa/`、`cover-history/`。
- [来源与假设](../../output/tasks/workflow-acceptance-20261118/sources.md)、
  [完整媒体清单](../../output/workflow-acceptance-20261118-blueprint-1e5165c30fbf9457-final.media-provenance.json)、
  [场景与合成证明](../../output/workflow-acceptance-20261118-blueprint-1e5165c30fbf9457-final.hybrid-build.json)。
- [来源链实际重放](../../output/tasks/workflow-acceptance-20261118/final-provenance-verification.json)：
  9个原生场景通过见证重渲染，4417帧完整合成重放；逐帧最低55.85dB PSNR，
  解码音频一致。不是科学、版权、视觉或听感验收。
- [独立影片QA](../../output/tasks/workflow-acceptance-20261118/qa/final-qa.v2.json)、
  [封面QA](../../output/tasks/workflow-acceptance-20261118/cover/cover-qa.json)、
  [五目标增长报告](../../output/tasks/workflow-acceptance-20261118/growth-report.md)、
  [实测生产报告](../../output/tasks/workflow-acceptance-20261118/production-report.json)。

实际渲染阶段耗时1895.891秒；采样work峰值821,954,238字节。分块过程累计
生成并验证清理7,107,200,885字节临时PNG（累计量，不是峰值），清理3287个
文件。100.733秒为原生3D，46.5秒为原创信息画面；既有成片镜头复用为0秒，
模型/模板复用另按9/4镜头计数，不据此推断节省时间、Token或费用。

必需验收缺口：

- 完整连续观看、听审、盲看理解和六维最终质量均为 UNKNOWN。独立QA实际
  看了22.5/72/96/110秒四帧及72秒三种手机宽度，仅支持相应局部结论。
- 版权/原创表达、配音使用权及组织使用资格未获得完整独立确认。
- 历史风格代码锁为 FAIL：批准截图哈希仍PASS，`studio_style.py` / `scene.py`
  与旧锁不同；不等于已证明画面风格错误，实际视觉等效性仍UNKNOWN。
  未改旧锁哈希来制造通过。
- 两个封面的主体、文字、构图等已局部PASS；与既有发布封面的系列一致性
  仍UNKNOWN，因此整体封面不冒充正式PASS。

| 级别 | 实际结论 |
| --- | --- |
| Level 1 | 回归通过，5项历史/可选集成检查跳过并保留限制 |
| Level 2 | 真实选题到研究、导演、资产、Neil、渲染、合成和独立QA已执行 |
| Level 3 | 完整视频与配套文件已存在，正式质量验收未完成 |

本次实现不能证明任意科学主题都可自动产出成熟纪录片质量。一般场线/流线
属于给定路径示意，机械约束属于几何断言，不是物理求解器；EAS原有部分
检查仍针对既有教学装配。具体可用接口、实际验证范围与尚存限制以能力审查
和绑定媒体为准。未上传、发布或保存平台草稿。
