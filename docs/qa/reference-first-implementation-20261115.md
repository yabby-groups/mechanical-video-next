# Reference-First 实施与轻量验证

日期：2026-11-15。范围：未来新建 protocol-v2 任务；未启动选题制作、回力车重做、历史失败恢复、历史 CAD 生成或已有完整视频重渲染。工作区已有的策略改动保留并补齐，未提交 Git。

## 代码与策略

- `mechanical_video_next/reference_policy.py`：来源查阅、机构一致性、合法素材优先选择、文件哈希、模型来源、修复归因、evidence_map、内容时长、前置独立 QA、执行计划及最终报告验证。
- `mechanical_video_next/workflow.py`：新任务默认 reference-first/reference_policy_version=1；复用原 handoff/DAG、状态和制作门禁。策略选择后才允许 CAD 生成。历史无标志任务沿原策略，不迁移。
- `mechanical_video_next/blueprint.py`：将证据映射、内容时长与镜头知识绑定传入实际配置。
- `mechanical_video_next/multiroute.py`：执行前核对任务、独立 QA 的计划哈希及外部输入；公开入口也受门禁。无任务的历史计划必须显式 --legacy-workprint。
- 测试新增 `tests/test_reference_policy.py`、`tests/test_reference_workflow.py`；旧 CAD、增长、分层、多路线及参考工作流测试显式区分历史账本。
- 既有 AGENTS、README、CAD/Asset/MechanicalResearch/ViralResearch Skills 和七个既有角色配置使用统一契约，未增加 Agent 类型或生产系统。

旧默认：自主 CAD 优先。新默认：本地已验证参考优先；合法且匹配的现成媒体 → 经检查装配 → 依据可靠资料的参数化教学模型。外观图片、标题封面、热度不能支持内部机构。许可未知不能直接复用。现有 Neil、画幅、视觉、字幕、封面、增长、压缩核查及缓存规范保留。

## 证据与制作前检查

映射链：具体结论 → 来源及实际位置 → 零件 → 动作 → 可用素材 → 双向镜头 knowledge_ids → 验证方法。契约及明确标注的示例见 `docs/reference-first-contract.md`。

独立前置 QA 核查九项：可靠来源、具体机构、型号不混用、知识有依据、动作可证明、模型匹配、内容时长、不编造零件、镜头可执行。必须全部 PASS 且无阻断缺陷；报告绑定精确 research/asset/blueprint 摘要，过期依赖拒绝。动态分镜和视听验收仍独立执行。

独立代码 QA 两轮发现并推动修复：候选模型与实际模型脱节、分层路线旧策略冲突、阻断问题被忽略、执行计划与输入未绑定，以及公开入口/依赖顺序绕过。最后一轮对剩余两项修复复核 PASS；范围仅代码门禁，不是实际媒体验收。QA 原生任务：`/root/reference_qa`。

## 内容与时长

先定义核心问题、已核实知识、可见动作与章节新增信息；再以实测旁白决定120～300秒。未实测、内容不足、重复章节知识、断裂时间轴或时长不一致均拒绝。真实信息密度、语义重复、旁白与画面同步由独立 QA 判断，不能由一个 PASS 字段证明。

测试中的120秒/两齿轮是合成契约夹具，不是对真实两分钟内容充分性的认可；所有素材和观看声明均明确为测试数据。

## 自动化结果

统一通过 uv 执行，UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache。

- `uv run python -m unittest tests.test_reference_policy tests.test_reference_workflow -q`：26项通过；覆盖合格现成模型、合法媒体优先、有依据参数模型、证据不足拒绝，以及过期/缺失证据、类型混用、未批准图层、模型替换、时长不足、阻断 QA 和计划绕过。
- `uv run python -m unittest discover -s tests -q`：253项，251通过，2失败，0错误。完整输出：`/private/tmp/reference-first-tests-final.log`（临时日志）。
- `git diff --check`：通过。

两项全套失败为 `test_housekeeping_change_preserves_scene_cache_identity` 与 `test_protected_actual_reference_and_scene`。现有 blender/scene.py 和 blender/studio_style.py 与风格/缓存记录的哈希不一致。通过 git show HEAD 逐字节比较确认这两个源码及两份锁记录都与 HEAD 完全一致；本次未修改或放宽它们。原始 approved-original.png 哈希仍匹配。未来生产仍需处理现有风格锁差异，不能把本报告作为风格验收。

## 能力限制与报告

确定性工具检查记录及文件绑定；不会自动证明机械科学、许可授权、实看、连续运动或听感。缺能力仍 UNKNOWN，不能完成验收。外部输入必须完整声明，未声明命令副作用需要 QA 审核。没有新视频，也没有真实复用比例、返工改善、节省时间/Token 的观测，均不作数值承诺。

成片报告继续绑定实际媒体版本、来源、复用比例及口径、有依据知识数、教学近似、未验证结论、有效新增知识、删除的重复镜头、错误结构重建和人工干预；无计量填 null。未验证机械结论阻止最终验收。
