# 可执行长视频契约

新任务沿用 protocol_version=2，增加 content_policy_version=1。创建时 duration=null 表示待知识研究与 Neil 实测配音决定，不是零秒或90秒。冻结蓝图 duration_seconds 必须为120～300，指定时长须匹配。历史任务不迁移。

blueprint 保留已有 time_range、knowledge_goal、模板、相机、旁白数组、字幕数组和可行性证据；增加 duration_reason，以及每镜头 section_id、start_time、end_time、teaching_goal、new_information、visual_proof、audience_takeaway、duration_reason、related_growth_goal（retention/engagement/following 数组）。start/end 必须与 time_range 完全相同。重复 new_information 拒绝；语义重复仍须实际媒体独立 QA。

增长字段见 mechanical_video_next/growth.py 的 GOALS。每个字段为对象：text、shot_id、knowledge_point、mechanical_action、narration（镜头中的一句原文）、observable、verification_method。information_progression 为上述对象数组并覆盖全部镜头。first_answer_time 为答案镜头内实际秒数。next_episode_bridge 额外包含 plan_evidence（真实计划文件引用）；series_value.text 推荐“拆开机器，看懂工作原理”。编译器将增长目标和教学要求写入实际配置与 binding.shot_requirements，不另建第二份时轴。

QA 的 retention_checks / engagement_checks / following_checks 为数组，每项含 goal（该组字段名）、shot_id、status、time_range、media_sha256、evidence、continuous_viewing、listening。全部必须关联报告中实际已核验媒体，时间码在目标镜头内；能力缺失填写 UNKNOWN，不允许 PASS。现有独立 reviewer、媒体哈希、制作依赖及机械 QA 门禁继续有效。开场、第一答案时机、中段空转与语义重复须按实际媒体判断，不靠关键词证明。

可选发布反馈：`uv run python -m mechanical_video_next.feedback --input observation.json --output output/feedback/new-observation.json`。
输入包含 video_id/platform/account_id/published_at/observed_at/topic/traffic_source/duration_seconds；blueprint 和 timeline 均为 path/sha256 绑定。未知流量来源可明确写 unknown，不推断。views、retention_3s、retention_5s、average_watch_seconds、completion_rate、likes、comments、saves、shares、new_followers 缺失保持 null；比例用0～1。自动计算点赞、收藏、新增关注/千次播放，零播放或未知分母结果为 null。此接口仅本地导入，不读取平台、不发布。比较时按同平台账号、相近长度主题、发布时间与流量来源人工筛选，不合并平台，不做因果预测。

当前 CLI 只负责确定性契约和门禁；Producer 仍负责研究、决定时长、真实运动分镜和调用现有三路线。静态占位 animatic 没有升级成运动生成器。新契约不是已完成长视频制作的证明。

## 最新运营输入（2026-11-13）

制作前读取[双平台数据对应的制作优化要求](plans/operations-growth-optimization-20261113.md)：首2秒展示变化，5秒内开始因果解释，优先检查首轮动作之后的知识推进、关键接触可见性和结尾兑现。沿本契约既有镜头与增长字段记录，用实际媒体SHA256及时间码独立验证；小样本指标仅支持检查假设，不证明镜头原因或预测增长。同期复盘与9份页面原文见[证据目录](plans/evidence/operations-20261113/)。
