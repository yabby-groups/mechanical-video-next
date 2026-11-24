# Reference-First 历史账本契约

下文适用于固定 `reference_policy_version=1` 的旧账本任务。时长、多路线及锁定摄影棚要求按任务历史版本执行。新片使用[制作契约](production-contract.md)。

2026-11-15 用户要求。只对新建 `reference_policy_version=1` 任务启用；旧任务不迁移、不重制、不自动修复。回力车已完成，保持原样。复用现有 protocol-v2、不可变 handoff、三路线、QA、缓存及渲染入口，不增加 Agent、服务或 CAD 内核。

## 研究先于素材与建模

先用 reference_library 检索本地已验证资料，再补网络缺口。优先真实拆解与工作过程、制造商技术/维修手册、可靠结构图、专利具体实施例、来源可信装配CAD及经过核实的动画。ViralResearch 研究表达、节奏及兴趣；MechanicalResearch 独立确认机械事实。热度不是真实性证据，标题与封面不算完成研究。

research 的 `mechanism_id` 固定具体型号/机构。`references` 每条包含 `id`、`location`（URL或本地路径）、`source_name`、`author`、`type`、`acquired_at`、`viewed_scope`、`structure_evidence`、`motion_evidence`、`license`、`usable_content`、`mechanism_id`、`unknowns`、`conflicts`、`unresolved_core_conflict`。核心冲突必须解决并记为 false；不能混合型号。

`viewed_scope` 写实际 `status` 与 `evidence`。视频用 VIDEO_INSPECTED 并记录真实 `time_ranges` 和 `confirmed_actions`；图纸用 DRAWING_INSPECTED 并记 `drawing_numbers`、`parts`、`connections`、`dimensions`；专利用 DOCUMENT_READ，记 `embodiment` 和 `figure_numbers`；模型用 MODEL_INSPECTED。片段观察只支持片段结论，禁止伪造连续观看。尺寸未测明确 UNKNOWN/教学近似，不用猜测填值。图片查阅遵循 qa_images 压缩路径规则。

## 优先复用正确且可合法使用的内容

资产候选优先级：`existing-media` → `verified-existing` → `autonomous-cad`。依次记录搜索结果；找到合格现成内容时不能跳过它直接重建。每条候选含 `strategy`、`qualified`、`reason`；合格项另有 `id`、`source_ids`、`mechanism_id`、`validation_evidence`、`legal_use=true`、`content_match=true`，现成内容附 `source_files`。来源可信不等于已获素材使用权；许可未知不合格。实际文件还受既有 SHA256/装配/机械检查约束。

asset-plan 的 `strategy`、`selected_candidate_id` 必须匹配优先选择结果，附 `mechanism_id`、`model_source`、`substantive_repairs`。装配模型先检查独立零件、连接与动作，必要时用现有 CAD Skill 转换；缺现成内容但有可靠技术资料才创建教学模型。只有外观照片不得编造内部机械。找不到足够依据时继续研究或缩小范围，不生成冒称真实产品的自创模型。

修复先归因 reference/model/assembly/animation；`substantive_repairs` 每次记录 cause、evidence、changed_assumption、result。原始结构理解错先修机构定义，不继续微调错误外观。保留持久缺陷历史；无改善换策略，不重复相同错误假设。机构已验证时普通相机、字幕调整不重建 CAD。

## 蓝图证据映射与时长

蓝图 `core_question` 定义本集问题；`evidence_map` 每条含 `knowledge_id`、`conclusion`、`source_ids`、`reference_locations`（source_id/position）、`parts`、`actions`、`usable_material`、`shot_ids`、`verification_method`、`verified=true`。每个来源必须有具体定位，每个解说镜头的 `knowledge_ids` 必须与映射双向关联。没有证据的重要结论不得进入解说。

例：某型号手摇打蛋器的手柄通过指定齿轮驱动双搅拌轴，必须定位到其手册图号/视频实看时间码，列出参与齿轮、轴、可见动作及展示该传动的 shot_id；不能套用另一型号的传动结构。

先列已核实知识、可展示动作与章节新增信息，再结合实测 Neil 配音锁定120～300秒。`content_timing` 包含 status、basis、measured_narration_seconds、chapters；各章含 id、knowledge_ids、new_information、duration_reason，知识点不重复充数。研究不足先补同机构的真实细节、剖面/对比或使用场景，删重复镜头，再计算时长。仍不足则记录不匹配、保留研究，不冻结虚假蓝图。禁止降速、重复拆解、反复预告、无意义零件介绍或无关知识凑时长。形式验证不取代 QA 对语义重复和真实观看的判断。

## 独立制作前与成片检查

昂贵正式3D渲染前，现有独立 QA 交付前置报告。`reviewer_role=QA`、`independent=true`，`plan_sha256` 由 reference_policy.plan_digest 对精确 blueprint/research/asset 计算。`content_checks` 的 reliable_sources、specific_mechanism、no_model_mixing、supported_knowledge、demonstrable_motion、model_matches、content_duration、no_invented_parts、executable_shots 各含 status/evidence，全部 PASS 才通过。FAIL/UNKNOWN 优先补证据，不能靠多生成完整CAD绕过。已有动态分镜、核心动作、媒体哈希与听审门禁继续有效。

最终 reference report 绑定实际 `media` 版本，记录 `primary_references`、`model_material_sources`、`actual_reuse_ratio`（有值须 `reuse_measurement_basis`）、`supported_knowledge_count`、`teaching_approximations`、`unverified_conclusions`、`duration_added_knowledge`、`removed_repetition`、`wrong_structure_rebuilds`、`human_interventions`。未知计量填 null，不能假定零或虚构节省。未验证机械结论阻止验收。现有增长目标及报告继续保留，不预测完播/点赞/吸粉。

## 不变规范与能力边界

保留浅灰摄影棚、原相机与运动、金属材质、Neil、1920×1080/30fps、2D/2.5D/3D、单行大字幕与手机可读性、3:4/4:3封面、压缩图片核查、安全缓存清理和原始资产。参考及现成素材不得覆盖已锁定风格；采用原创解说与视觉编排，不复制未经授权的完整视频、配乐或独创表达。发布仍由用户执行。

确定性校验验证记录完整性和绑定，不会自动证明作者许可、机械科学正确性、连续观看或听感。QA 缺能力继续 UNKNOWN。轻量测试只验证选择与拒绝分支，不制作完整视频，也不证明未来返工量已下降。

## 执行绑定补充

新蓝图必须显式携带 `reference_policy_version=1`，编译后的配置保留 evidence_map、content_timing 和逐镜头 knowledge_ids。映射必须双向一致。参考类型 video/drawing/patent/manual/document/cad 必须对应实际查阅状态；仅外观照片不能成为内部机构依据。

装配转换后，把原文件及获批转换产物都加入候选 `source_files`，实际 `asset-plan.model` 必须精确匹配其中一项；转换与装配检查写入 validation_evidence，不能用另一个模型替换获批候选。生成 CAD 前先提交有依据的资产选择，再提交实际模型版本。二维/分层合法图片使用 existing-media 策略和 render_route=2d/2.5d，图层必须来自所选候选文件；素材策略与表达路线分别核对。

多路线计划执行前，content-qa 额外包含 `route_plan={path, sha256, input_hashes}`。QA 核对实际命令、逐路线配置、素材与共享时轴；input_hashes 使用外部输入的绝对规范路径及 SHA256，包含 prerequisite_inputs，以及各步骤首次读取前尚未由前序步骤生成的 steps.inputs。计划、配置或外部素材变化必须重新审核，旧批准不再放行。公开 multiroute run 使用 --task 或计划 task/evidence 绑定任务，无任务历史计划须显式 --legacy-workprint。各步骤须完整声明输入输出，不能把外部输入冒充计划输出。前置 QA 即使九项均 PASS，存在 blocking/critical/major/error 缺陷仍拒绝制作。

证据映射示例（示例结构，不是已核实产品资料）：

```json
{
  "knowledge_id": "drive-01",
  "conclusion": "指定型号的手柄通过已核对的齿轮驱动搅拌轴",
  "source_ids": ["manufacturer-manual"],
  "reference_locations": [{"source_id": "manufacturer-manual", "position": "维修手册图3，零件4/5啮合位置"}],
  "parts": ["手柄轴", "主动齿轮", "从动齿轮", "搅拌轴"],
  "actions": ["手柄转动", "齿轮啮合传递旋转"],
  "usable_material": ["许可合格的装配文件及其来源哈希"],
  "shot_ids": ["drive-closeup"],
  "verification_method": "对照实际手册、装配连接与短动作诊断，独立QA检查传动方向",
  "verified": true
}
```

该示例必须替换为真实型号、来源及实看位置后才能交接；不能直接作为制作证据。
