## CodeGraph

若当前会话暴露 `codegraph_*`，结构问题优先 `codegraph_context`，再一次 `codegraph_explore`；符号定义用 `codegraph_search`，调用、影响、文件结构分别用相应图工具。不重复 grep 已由图确认的结构。字面文本用 rg。服务器返回 not initialized 时，询问用户是否运行 `codegraph init -i`。当前创建会话未提供该 MCP 的调用工具，不假装已检索或初始化。

## ego-browser execution

使用 ego-browser 前阅读其 Skill；执行路径 `/Users/lmj/.local/bin/ego-browser`，JavaScript 使用 `nodejs -e`。不使用 heredoc、herestring、bash -lc 或 zsh -lc 包装，不改 Codex 沙箱配置。现有 ExecPolicy 已允许时不额外请求提权。


--- project-doc ---

# Effective production instructions

Mechanical Video Next serves the single Douyin account 「君哥拆机器」.
「拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。」

Read [docs/production-contract.md](docs/production-contract.md) first. It is the
single effective entry point for future mixed-original production; explicit user
instructions take precedence. Policy versions in task.json determine the contract.
Historical 3D-only tasks retain their original rules and are never auto-migrated.
The pre-consolidation instructions are archived in docs/history/production-instructions-20261118/AGENTS.md.

Use the existing sole native Producer, role agents, task ledger, Blueprint,
immutable hash-bound handoffs, advance/stage/continue, source manifests and QA.
Do not add a second scheduler, new management UI, extra roles or pseudo-agents.
Read docs/agent-dispatch-efficiency.md before every spawn; preserve configured
Sol/Terra/Luna routing, default two children, compact fork_turns=none assignments.
QA is independent and only writes reports. Record actual native identity and
available telemetry; unknown tokens, costs and interventions are null.

For new topic-only mixed tasks the Producer researches and directs the complete
film. Keep the mechanical object and core question requested by the user.
Verify the specific implementation, key parts, contacts and continuous cycle
from input through transmission, output and reset. Use native 3D disassembly,
cutaways, close-ups and motion to show how it works. History, footage, everyday
scenes and graphics support that explanation. Direct the complete Treatment
before formal asset work. Existing independent QA reviews scope and the evidence
for the mechanical cause. Only exact-media mechanical and visual PASS authorizes
formal production. Follow the pinned workflow for existing tasks.
The effective contract also governs role Skills and their historical examples.
Verify the concrete implementation, never mix models or guess hidden mechanics.
Unknown evidence blocks only dependent shots. Keep original narration/visual design,
prefer matching owned assets, verify external rights; other creators default to
REFERENCE_ONLY. Core motion in new tasks requires inspectable native 3D. Mixed output has complete independent media
provenance and cannot claim historical 3D-only acceptance.

Keep measured Neil speech where authored, 1920×1080/30 and phone-readable
single-line subtitles. The Producer reviews the low-cost full edit and directs
the final composition. Full film/audio review
and continuous key actions are required; images/tests/ASR/loudness do not replace
watching/listening. Deliver actual MP4, both covers, sources/provenance, independent
QA and production/growth reports before record-delivery. No publication or drafts.

All Python commands use uv run (CAD: uv run --extra cad). Use project Python
3.14.2, uv.lock, build123d/Open CASCADE; Blender uses its embedded Python.
Set UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache when needed.
Blender runs serially through existing stage lock; inspect lsof work/production.lock.
Keep work <=2 GiB and disk free >=3 GiB, content caches and chunk encoding.
Clean only verified regenerable intermediates with scripts/clean.py; preserve
assets/output, historical models/media and all failed evidence. Subtitle/chart
changes only recompose; a wrong mechanism is rejected, not endlessly patched.

Before image inspection use uv run python -m mechanical_video_next.qa_images SOURCE
(video: --times T1 T2 T3 T4). Read returned qa_path WebP/JPEG only; at most four
frames and one contact sheet per round. Use prepare_crop when needed. record_reads
only after real reads; no base64 handoffs, no invented token savings. Static images
never prove continuous motion or listening. Preserve the protected style reference.

Use CodeGraph for structure/source before edits; literal searches use rg.
Use ego-browser only after its Skill, with absolute /Users/lmj/.local/bin/ego-browser
and nodejs -e. No heredoc, herestring, shell-login wrapper or sandbox changes.

New formal Producer tasks pin the 120–300-second policy for a Full Animatic and
Final Film. Apply the task's policy to the actual MP4 and Joint Timeline. Director
uses the approved Treatment's five growth decisions, and manual Audience Review
works from exact media. Use the Douyin post-review template for recorded platform data.
