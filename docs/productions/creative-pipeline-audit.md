# 创意制作流水线现状审计

审计以当前工作树的 README、生产契约、角色配置、制作 Skills、源码及修正带 V7 实际文件为依据。抽样只用于判断对应瞬间的画面。A 采用保存完整的 V7，SHA256 `fc23c9d7d9f9f1bfcfa2993cace91f04ce31897cbbd05ccdf2702a894526111a`。

| 范围 | 代码与实际证据 | 差距和影响 |
| --- | --- | --- |
| Producer、路由、创意 | `.codex/config.toml` 和 `.codex/agents/` 配置 8 个既有个体角色。`workflow.continue_production` 执行已授权命令，缺少执行命令时交回 native Producer。`creative_selection.validate_competition` 提供历史显式 v6 路线。 | 新任务走 `producer-directed`，所以历史候选选择不会进入默认路径。旧比赛还需要独立竞争流程。复用 Producer 和 Blueprint 增加三种具体表达及择案依据。配置模型与一次实际派工的遥测分别记录。 |
| Storyboard 与镜头 | `production_contract.validate_story_moments` 已绑定四个体验节点。`blueprint.compile_config` 将基础镜头、时间范围、相机和视觉字段组合进同一配置。`visual_narrative.configure_blender` 已执行固定观察机位和风格灯光。 | 现有 `direction` 的说明和渲染能力间只有局部连接。导演需要明确每镜新增信息和执行策略，并检查策略是否真的落到画面参数或已验证素材。 |
| Blender、CAD、Remotion、FFmpeg | `scripts/produce.py` 的 `asset`、`make_shot`、`compose` 已支持原有几何、工作片与合成。`scripts/cad_generate.py` 使用 build123d/Open CASCADE。修正带保留 STEP 及装配见证、Blender 动画、Remotion props、编码及可重放收据。 | CAD 是结构资产来源。逐镜头路线已经存在，但执行选择依赖作者填写的媒体类别，缺少候选可行性及成本比较。继续使用已有渲染适配器。 |
| 剪辑 | `joint_timeline.validate` 与 `measure` 已让画面、动作和 Neil 分轨，支持一句跨画面切点，并验证动作相位。V7 实际 57 秒仍在预设对比条件，64.85 秒回到整体，69 秒才看到相邻标记和下方两层文字。 | V7 有明确机械内容。该段的现象入口较晚，局部依赖说明文字，能用现象先行、相位连续和独立声画点来做对照。样本无法判断实际完播。 |
| 动态预演 | `blueprint.animatic` 仍是静态诊断入口。`workflow.require_animatic` 与 `require_animatic_diagnostic` 已支持真实动态低清路径。V7 曾先生成动态 Animatic，并在投影和字幕复查后才修改对应合成段。 | 需要显式验证整条预演的移动内容、制作输入与高清授权。工具不能把静态诊断误认为动态。现有正式独立 QA 检查保持生效。 |
| 参考与复用 | `viral.py` 已记录实际观看区间和证据，`reference_library.py` 保存可迁移技巧，`media_policy.py` 管理素材选择和许可。现有 `output/producer-direction-validation` 有参考样帧和播放记录。 | 样帧与页面记录只支持有限观察。已观察技巧需能定位到执行镜头及制作后对照。此轮优先使用项目自有 V7 和原生局部试镜作参考。 |
| 运动与 QA | `science_shots.py`、`blender/scene.py` 和 `science_scene.py` 已区分 tracks、mesh_tracks、相机路径、投影锚点与时间重映射。V7 记录真实源轨迹，使用 Sanford US8746316B2 图 1–4C。 | 镜头配置仍可混入运动字段。需要约束策略编辑的边界。以教学运动的相位、路线、接触和标记求值为范围，实际摩擦、张力与商用品型号未验证。 |
| 声音 | `scripts/narration.py` 负责 audiogen Neil 及缓存，`audio_timeline.py` 测量排布，`audio_acceptance.verify_mix` 验证静态增益和遮蔽。V7 的纸面拟音由一次性 `reedit.py` 生成。 | 主流程可以验证混音，但任意片的机械事件尚不能通过同一时间线生成拟音摆放。复用已有音频证明和增益边界。 |
| 创意验收 | `production_contract.validate_creative_review` 已按精确媒体哈希验证六个问题。V7 的最终独立复查为抽帧加解码，连续视听与观众理解 UNKNOWN。 | 已有正式技术与创意结论的接口，需补充按镜头对照和实际可观察的变更，并保留感知与增长结果的限制。 |
