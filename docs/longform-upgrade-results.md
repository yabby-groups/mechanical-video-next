# 长视频增长契约改造验证（2026-11-12）

## 已实施

- 新 protocol-v2 任务使用 content_policy_version=1，120～300秒；未指定时 duration=null，由 Producer 按可靠知识和 Neil 实测旁白确定。无固定90秒，旧任务不迁移。
- growth.py 提供可执行蓝图/镜头/增长目标校验；workflow 在交接、配置复核、动态分镜、预览及最终 QA 门禁接入。blueprint 编译保留教学要求与增长目标，原动画镜头缓存不混入旁白字幕。
- 每个增长决定绑定知识点、镜头、动作、旁白、可观察效果、检查方法。新增信息精确重复拒绝，语义重复仍需独立媒体审核。下一集必须绑定本地真实计划证据与哈希。
- QA 增加 retention_checks / engagement_checks / following_checks，要求全部目标与镜头覆盖、实际媒体哈希、镜头内时间码和明确观看/听审能力；UNKNOWN不能推进。实际MP4通过ffprobe核对时长与蓝图，最终三路线分别检查。
- feedback.py 提供本地可选数据导入 CLI，缺失指标null，0播放不除零，计算点赞/收藏/新增关注每千次播放，绑定蓝图和时轴哈希。平台与账号维度保留，不自动混比或预测。
- 更新 AGENTS、README 和 Viral Research Skill，不新增 Agent、数据库、后台或渲染引擎。

## 自动化验证

执行：`UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python -m unittest discover -s tests`

结果：169 tests，2.670秒，OK。`git diff --check` 通过。日志：`output/longform-upgrade/tests.log`。

覆盖120、180、240、300秒，拒绝119以下与301以上；保留显式历史协议、38.2/90秒加载状态；增长目标编译、信息重复、首答案时间、媒体哈希/时间码/能力、实际媒体时长、发布缺失指标；现有共享音频/时轴、缓存恢复和字幕不重渲染3D测试继续通过。

## 当前鸡蛋搅拌器

只读核对 task.json、CAD交接、latest production-status.v3.json、shared/timeline.json、Neil音频和三版成片。ledger仍为RESEARCHING，但最新交付记录已是 TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO，不能只凭ledger推断尚未制作。

三版ffprobe实测均96.3秒，文件SHA256全部匹配既有交付记录，未覆盖任何任务资产。详细只读快照：`output/longform-upgrade/eggbeater-impact.json`。

脚本规划0秒开始输入输出运动；首段齿轮传动答案在6.866667秒开始的S02。后续解释齿数与转速、方向和转矩代价，末段回扣慢摇快转。以上是脚本/时轴证据，动作可见性、同步、顿悟清晰度、连续视觉、听感和科学接触仍UNKNOWN。本集旁白未发现具体下一集承接；因已有正式候选，本次不自动改稿重做。后续获选版本可局部修订，不能自动迁移新时长。

## 验收边界及下一步

本次完成工程契约及回归，未生成120～300秒完整三路线视频。静态blueprint animatic仍是诊断占位，不具备完整动态演示能力，不得据此通过QA。Producer仍需为新题研究可靠知识、选择合理长度、制作真实低成本运动分镜并独立审核，再调用现有生产工具完成三版。

保留现有按镜头增量缓存、共享CAD/配音、Blender串行锁、分块编码、work和磁盘门禁；未进行长片资源峰值或新引擎性能实测。下一次新题需做实际资源预算和端到端120～300秒生产验证，不在已完成鸡蛋搅拌器切引擎。

发布数据接口是导入及算术，尚无真实发布数据输入、可比样本筛选自动化或有效表达方式自动推荐；优先复用策略仍需Producer阅读同平台可比实绩。没有平台数据证明完播、点赞或关注得到提升。

保留本轮开始前已有运营文档、蓝图和测试改动；没有提交Git或发布任何内容。
