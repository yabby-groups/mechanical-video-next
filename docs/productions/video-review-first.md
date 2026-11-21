# Video Review First

审计覆盖 Director、audience-review、Blueprint、Joint Timeline、生产契约、Mechanical QA、preview-qa、final-qa、Blender、FFmpeg、Remotion 和 Neil。现有生产流程已校验机械程序及 time_map、故事窗口、MP4 帧时戳和 AAC 对实测 Neil 的匹配。此次补充实际画面与源片段的逐帧比较，并把技术发现放进原有独立审片流程。

## 默认生产流程

- 新 Producer-directed 任务在登记 animation-manifest 和 timeline 时自动生成 Video Review。不可变交接绑定实际 MP4、Remotion 参数、原生片段及 Blender 检查记录。既有 continue 用带时间码的发现把修复工作交给 Producer。
- Blender 缓存保留现有数值约束的逐帧求值。动作可声明有证据支持的方向、状态顺序、最短运动帧数、最大单帧位移和跨镜最大跳变。FFmpeg 逐帧比对最终画面与选取的源片段，同时检查完整时钟、字幕计划及 Neil 音轨。独立 QA 检查接触、遮挡、故事兑现和音画理解。
- 当前完整动稿的技术结果及独立 preview-qa 共同约束高清渲染。更新 MP4 后重新核对完整片和受影响镜头。终版必须通过本片技术校验及原有独立 final-qa 才能完成并记录交付。历史任务沿用其固定版本。 [制作契约](../production-contract.md) · [Video Review Skill](../../.agents/skills/video-review/SKILL.md)

## 开源资料

重读了本地保存的固定提交源码、脚本、示例、许可证及依赖。采用方法由项目独立实现。第三方安装与脚本执行次数为零。 [固定提交和归属](../director-skill-audit.md)

| 候选 | 核查和取舍 |
| --- | --- |
| AustinZ21/cinematic-skills | MIT。核对 shot-director 的 review.md 和时空指南。采用全段复核、切点方向、共同参照和给接触结果留观察时间。 |
| wjq616919/codex-skills | 核对 storyboard-director 的状态、动作时间、样例和 Python 评分。所查提交无明确复制许可。独立实现机械端点和事件顺序检查。 |
| salomonMuriel/media-production-skills | MIT。核对 qa.md、qa_video.py、_qa_video_motion.py 和模板。采用低清真动稿、按帧定位视觉异常和复述故事的方法，执行使用项目已有的 FFmpeg 与 Pillow。 |
| cajias/agentic-video-skills | 核对 cinematic-director 的 MIT、NOTICE、continuity-bible 和 QC。采用跨切点检查状态和空间参照的方法。 |
| Vincentwei1021/video-shotcraft | Apache-2.0。核对 Remotion 推进、停留和转场示例。检查观众是否能在切点两侧认出同一零件及其状态。 |

## 门锁案例

原片 59.133333 秒，1,774 帧。原始 Blender 场景逐帧求值与实际帧序列核对后，自动发现 37.200–37.267 秒门角跳变 7.6°、40.667 秒及 53.700 秒斜舌单帧突缩 0.242708 和 0.245720 场景单位。原片技术门禁拒绝。完整 18 句 Neil 和画面帧数均通过。历史正式 Director 编译交接缺失，其 time_map 使用状态 UNKNOWN。独立盲审先发现拨轮接触被遮、回位弹簧两端难辨、扣孔不清及片尾回位总结偏弱。随后按完整扣合循环范围复核，发现缺少反拉时斜舌平面受挡以及再次按压脱扣。 [实际门禁验证](../../output/tasks/door-handle-return-20261121/video-review/actual-media-gates.json) · [原片盲审](../../output/tasks/door-handle-return-20261121/video-review-original-independent.md)

复用了同任务已有的校正机构和补齐叙事的原生镜头，新增原生按压与回位特写、去除剖切残片，并在 45.567 秒讲解斜舌弹簧时回到同一机械帧的宽景。新版 97.666667 秒，共 2,930 帧、23 句 Neil。中间修订版也用现有 Remotion 完成全片重放并核对全部帧和音轨。 [修订动稿](../../output/tasks/door-handle-return-20261121/video-review-delivery-check/door-handle-workprint.mp4) · [技术复审](../../output/tasks/door-handle-return-20261121/video-review-delivery-check/technical-review.json) · [最新独立复审](../../output/tasks/door-handle-return-20261121/video-review-delivery-check/independent-review.md) · [Remotion 重放](../../output/tasks/door-handle-return-20261121/video-review-closeup/remotion-replay-verification.json)

当前会话支持按时间码查看图像，FFmpeg 能连续解码和逐帧比较，Blender 可测求值对象，ffprobe 可测帧时戳。独立 QA 的观察来自定点样本。连续观看、听感、实际接触及音画理解仍为 UNKNOWN。该历史任务的正式台账未推进到交付，高清及正式独立验收保留待审。

全量测试 524 项，其中 518 通过、6 跳过。包含反向、丢事件、压缩、跨切点跳变、末句截断、错误音轨、知识点缺失、结尾提前、可解码画面与源片段不同和 UNKNOWN 拦截。现有生产契约测试用可解码媒体验证交接登记、技术审片及独立 QA 门禁。Remotion TypeScript 检查和 Skill 验证通过。
