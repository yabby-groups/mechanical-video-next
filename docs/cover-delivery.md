# 必交封面

当前任务按账本中实际请求的路线生成封面。新制作只有兼容入口 `3d`，混合媒体身份由生产契约决定；下文旧三路线示例只解释历史任务。完整视频落盘后，Producer 先确定编辑推荐版本（不等于批准发布），在任务目录写 `cover-plan.json`，再运行：

```sh
uv run python -m mechanical_video_next.covers output/tasks/<task>
uv run python -m mechanical_video_next.growth_report output/tasks/<task>
```

route-run 会在视频与对比片落盘、路线登记完成后调用增长报告和封面生成。缺少封面方案明确报错，可补方案后单独运行以上入口，无需重新运行视频生产。历史任务不会在加载时自动重制。

方案示例（内容必须据本集实际脚本与媒体填写）：

```json
{
  "topic": "手摇打蛋器",
  "recommended_route": "3d",
  "recommendation_reason": "本版清晰展示手柄、齿轮与搅拌轴之间的关系；仍须独立QA",
  "route_analysis": {
    "2d": {"suitability": "UNKNOWN", "reason": "待核对传动关系画面"},
    "2.5d": {"suitability": "UNKNOWN", "reason": "待核对剖面遮挡"},
    "3d": {"suitability": "UNKNOWN", "reason": "候选含输入与输出，待视觉检查"}
  },
  "series": "拆开机器，看懂原理",
  "title": ["一摇为什么转得快？"],
  "copy_rationale": "文案对应本集解释的齿轮传动问题",
  "frame_rationale": "同一画面展示手柄、传动与搅拌轴",
  "selected_candidate": "transmission",
  "candidates": [{
    "id": "transmission", "route": "3d", "seconds": 12,
    "shot_id": "transmission-closeup",
    "mechanical_moment": "手柄带动齿轮与搅拌轴",
    "subject_box": [0.1, 0.1, 0.9, 0.9]
  }]
}
```

`subject_box` 是原始帧中必须保留的重要机械结构外框，归一化 `[left, top, right, bottom]`。候选只能来自当前三版实际视频，时间点须在实际时长内。标题限1～2行、每行最多24字符，并检查实际字体像素宽度。可以指定 `font_path`，默认使用系统中文字体。

输出在任务最终交付根目录的 `cover/`：`portrait_cover_3x4.png`（1080×1440）、`landscape_cover_4x3.png`（1440×1080）、`cover-report.md`、`cover-report.json` 和 `candidates/`。两个版式均完整保留来源帧并按比例居中缩放，标题使用独立色带，避免遮挡机械。报告记录各比例主体占比、布局、候选、标题理由、推荐依据、来源视频及哈希。不能用导出成功证明语义或视觉合格。

新方案可显式设置 `image_alignment: {"portrait":"top","landscape":"center"}`。
竖版可用 `portrait_detail_candidate` 指向同一方案中已验证的实际候选，配合
`portrait_detail_label` 显示相关局部；仍从候选绑定的视频、时间点和裁区取帧，
保留主体边界，不生成虚构细节。横版继续单图。省略时保持历史布局。
输入和产物哈希不变时重复生成复用原报告，避免无关缓存计时使独立 QA 过期。

独立 QA 写 `cover/cover-qa.json`，必须提供 `independent_reviewer: true`、真实 `reviewer_thread_id`、当前 `cover-report.json` 的 `report_sha256`，以及 `cover_checks` 对象。检查键：

- `mechanical_subject`、`topic_recognition`、`copy_consistency`、`text_readability`
- `portrait_composition`、`landscape_composition`、`structure_unobscured`
- `series_consistency`、`non_misleading`、`recommended_version_consistency`

每项含 `status`（PASS/FAIL/UNKNOWN）、`evidence`、`visual_inspection: true`，以及 `artifacts`（两张正式PNG的绝对 `path` 与 `sha256`）。自动构图FAIL不能用手填PASS覆盖；调整方案后重新生成并复审。

```sh
uv run python -m mechanical_video_next.covers output/tasks/<task> --require-pass
```

增长报告绑定封面报告；最终 COMPLETED 门禁验证封面独立QA和增长报告时效。更换推荐版本、源视频、文案、字体或生成器会使旧封面/QA过期。重新生成封面后须重新审查并生成增长报告。该入口仅执行 ffprobe、单帧 ffmpeg 和 Pillow 排版，不调用CAD、动画、配音或视频合成。

候选可设置 `source_crop: [left, top, right, bottom]` 从来源帧裁去旧字幕与空白；坐标归一化，必须完整包含 `subject_box`，越界或裁掉重要结构会被阻止。报告记录实际裁区。历史任务的 `outputs.candidate.path` 可作为封面来源，视频仍保留候选状态；封面生成不把候选升级为已验收成片。

历史 `source-supported-film` 任务的默认入口优先选择当前配置的有效成片。当前配置尚无 final 阶段时，入口验证候选的路径、哈希、章节及当前来源，并要求候选与同一配置成功生成的 preview 阶段一致。封面报告在实际使用的候选来源上标记 `candidate: true`。增长报告与交付仍要求当前有效成片。
