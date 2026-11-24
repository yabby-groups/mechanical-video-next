# 原创科普与素材复用策略 v1

本文供恢复已固定 v1 策略的账本任务查阅，命令示例记录当时的入口。新片适用[制作契约](production-contract.md)。

核心原则：**原创内容优先，自有素材复用优先，外部素材作为辅助。** 每条正式视频都要有本任务独立的研究判断、原创解说、知识结构、分镜和视觉编排。已核实的事实和自有资产可以复用，但不能把另一条作品的整体脚本与镜头组织换个包装当成新原创。

优先复用项目自己生成的 3D 动画、模型、信息动画与实拍。重要科学原理优先用自主制作或具备使用权的可验证动画解释。外部片段帮助展示实物、现象与必要证据，不作为省去原创设计的捷径；也不为强调全自主生成而重复单调的 CAD 视角。

其他创作者的作品默认只供研究科学原理、镜头和通用表现技法。即使授权允许复用，也要独立检查表达边界：不得照搬独创性脚本、完整镜头组织或特色画面；裁切、翻转、变速、去水印、重新配音都不能作为原创依据。合理引用/合理使用须针对当前具体用途单独判断，系统没有默认成立或自动解锁的分支。

仅未来新任务使用 `media_policy_version=1`，同时绑定 `visual_policy_version=2`。仅输入选题的 `produce` 默认创建该策略；`--media-policy 0` 保留原视觉策略，`--visual-policy 1` 保留全时间线 3D-only。带旧配置创建或 `--resume` 不自动升级，不迁移旧媒体、失败历史或缓存身份。入口仍为原来的 `--routes 3d`，这是兼容的执行路径；混合影片的媒体契约明确是 `asset-first-hybrid-v1`，不能声称通过原版全时间线 3D-only 验收。

Producer 先用研究和知识递进形成视觉分镜，再逐镜头匹配素材。沿用 Research/Asset/CAD/Animation/Editor/QA、模型路由、Neil、Blender 全局锁、工作盘预算、缓存清理与不可变 handoff；没有新增角色、服务或审批系统。

## 匹配顺序与执行

优先级依次为：1 当前项目通过检查的自有片段/资产；2 自有历史视频、模型、信息动画与实拍；3 明确授权的外部辅助素材；4 Pexels/Pixabay/Wikimedia Commons 等许可允许的辅助素材；5 合法的外部 3D 模型和动画。第三方文件即使缓存在本地、登记为当前项目，也不能提升为自有优先级。找不到能服务原创知识设计的内容时，使用现有 Blender/Remotion 工具生成，不以渲染节省压倒原创表达和画面质量。每次匹配记录拒绝理由和未搜索的渠道；`NOT_SEARCHED` 不等于没有素材。原生 Producer 使用当前浏览器/提供方工具补齐有必要的外部缺口，不由 Python 模拟搜索或观看。

```sh
uv run python -m mechanical_video_next produce --topic '机械名称' --routes 3d
uv run python -m mechanical_video_next.reference_library media-ingest --input media.json --path clip.mp4
uv run python -m mechanical_video_next.blueprint match-media --blueprint visual-plan.json --output media-matches.json
uv run python -m mechanical_video_next.reference_library media-match --input shot-query.json
```

`match-media` 是现有 Blueprint 的确定性扩展。输入是待冻结的原创视觉计划，镜头可提供 `media_query` 的 tags、mechanism_knowledge、usage_scope、accepted_types、project_id 等约束；默认用 visual_type、knowledge_ids 和 commercial-video。它按整个时间线防止相同源区间反复填充，输出匹配回执，保留 Blueprint 不变。Producer 核对实际画面、同型号机构及许可，采用匹配结果写入新 Blueprint 版本，再编译。型号或证据不一致时拒绝；不能把词标签匹配当作机械验证。

视频入库实测宽高、帧率、时长；3D 模型需独立检查的 inventory 及证明。`references/media/blobs/<sha256>/source.ext` 存储唯一字节内容，`media/records/<record-hash>.json` 保存独立许可与观察记录。同一字节的研究记录、不同授权范围可共存，不相互提升权限。匹配重新校验素材及许可证明哈希，并检查内容、画质、使用范围、时长和重复使用。未获完整外部检索的无匹配结果为 `reuse_decision=RESEARCH_REQUIRED`、`generation_required=false`；历史兼容的 `decision` 字段不能单独授权生成。

该版本的 Asset handoff 也写入 `media_policy_version=1`、`visual_policy_version=2`，防止将新版许可例外注入旧任务。纯真实机构视频方案可在现有 existing-media candidate 登记 `mechanism_shots`，必须逐条通过核心视频的独立观察检查，来源文件与具体研究机构一致；reference-model-qa 使用 `depicted_type=licensed-real-mechanism` 和带源位置的 visible_parts，不伪造 CAD 零件。涉及原生 Blender 的方案仍保留全部模型与运动验证。

`record_media_use` 将实际成片、任务/镜头、知识与源时间段登记到同一参考库的 `media/uses`，幂等保留使用历史。`search_media` 返回实际使用记录。混合 manifest 写入后自动记录，使用记录本身不表示接受该影片。

`prepare_media_clip(record, root, start_sec, end_sec)` 沿用 FFmpeg 将授权片段转为 1920×1080、30fps、BT.709、yuv420p，默认删除源音频；按源哈希、起止秒数、变换和 FFmpeg 版本缓存，命中时重新核对输出哈希。保留原始源与片段范围，导出片段不获得额外授权。`budget()` 在编码前后检查现有工作盘 2 GiB/剩余空间 3 GiB 约束。不自动删除原始素材或 output。

## 素材与逐镜头字段

`source_type` 仅有 `REFERENCE_ONLY`、`LICENSED_REUSE`、`OWNED`、`GENERATED`。未经授权的第三方内容默认 REFERENCE_ONLY；可用于拆镜、动作/结构、景别、运动、表达与适用时段研究，不能剪入。公开可访问、可下载、取用几秒以及缓存命中都不是许可。项目原有原创渲染允许作为已有素材复用；应说明是原创 3D，不标成实拍。

在原有 knowledge_goal、visual_type、render_engine、机械角色、知识/来源映射之外，每个镜头明确记录 source_type、source_url、source_time_range（源视频秒数）、license_status、usage_restrictions、selected_asset（实际本地文件与 SHA256）、reuse_decision（REUSE/GENERATE）、generation_required、credit、content_verified、license 和 matching。GENERATE 使用 GENERATED，selected_asset 和 source_time_range 为 null，记录各层不适用/未找到合格内容的依据及 generation_reason。不能伪造外部检索完成。

许可必须含真实权利人、许可名称、商业剪辑分发权限、使用范围、署名、限制，以及本地 proof 的路径、SHA256、实际检查位置。NC/ND 或未验证许可被拒绝。项目原创视听素材的来源链声明只证明该视听素材，不能顺带声称专利、商标或零售产品身份已获确认。任何不确定权利保留 UNKNOWN；独立 QA 检查实际使用条件、署名和限制是否满足。

REUSE 视频的时段必须匹配镜头秒数，不循环、不降速填充。同一长视频的不同有效片段可分别复用；同一区间不能反复填充。原生 Blender 复用需要完整原片、checks、scene、模型和实际渲染来源链，无法匹配的部分使用已有生成工具补齐。既有 Remotion 信息动画也可复用其原生 graphic JSON 定义，须实际入库、许可合格并与执行定义完全相同，source_time_range 为 null；不把原生定义误记为源视频。信息图只解释知识，不能冒充真实结构。核心动作继续使用可验证原生 3D；只有对同一真实机构、同一源视频哈希和完整时间区间完成独立连续观察，并逐项确认知识的合规素材，才可作为核心 footage。实景环境、文字、流程图、AI 图像都不能替代这个证据。

## 合成、来源与 QA

继续使用现有 Remotion/FFmpeg 合成与字幕安全盒；输入视频在 Remotion 中静音，由实测 Neil 音频控制时轴。默认没有第三方原声启用分支。所有镜头服务真实使用、结构/动作、因果、对比、微观或新知识之一。保留既有知识递进和视觉多样性检查，不以素材数量判质量。

正式输出另存 `.hybrid-build.json` 与 `.media-provenance.json`，后者覆盖每一帧时间线、每个源片段/许可/哈希/生成方式、实际配音及合成构建。原生 3D 段仍走原有场景/空间运动/见证渲染及整片回放；来源清单校验本身不替代渲染回放或感知检查。未包含 Blender 的合规核心视频方案，仍须通过对应的真实机构连续观察与完整混合合成来源验证。

独立 final-qa 的 hybrid_media_review 绑定精确 manifest 与 MP4、每镜头的 license_compliance、source_correspondence、knowledge_service、mechanical_evidence、continuity、visual_quality、narration_alignment 及实际观察。最终验收要求连续观看与听审；技术通过、抽样画质合格及子任务完成均不授予验收。沿用现有内容、机械、产品、字幕、理解、封面、增长与交付要求；本次短片是升级集成验证，不免除正式长片门禁。

现有独立 QA 另外分别提交 `copyright_review` 与 `original_expression_review`，不是新增角色或管理系统。前者检查权利链、当前用途范围、署名、研究素材未进入成片；后者检查独立研究、原创旁白、知识结构、分镜、视觉编排、与参考的独创表达边界、不能靠简单变换宣称原创，以及科学解释的真实性。两份结论分别绑定精确影片和 manifest，原创审查还必须绑定本任务 research、script、creative-blueprint 的实际不可变交接；缺失证据或 UNKNOWN 阻止正式验收。复用比例只作素材/成本描述，绝不作为原创性判定。
