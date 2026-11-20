# Real product and viewer comprehension contract

New protocol-v2 tasks use `product_policy_version=1` and
`growth_policy_version=2`. Historical tasks keep their own contract. The existing
spin-mop task is explicitly upgraded at the user's request; its audio, CAD and
failure history are preserved.

`comprehension.validate_product_plan` requires a named real product, model scope,
observed source files with hashes, and a confirmed product/source relationship.
Patent-only or CAD-only evidence cannot establish a retail product. Appearance
photographs cannot establish hidden transmission. Each shot binds its input,
transmission and output claims to located observations, explains new knowledge
and necessity, and preserves the product-to-mechanism-to-function relationship.
The opening identifies the product/action/question/payoff within five seconds.
Creative-first v2 establishes the familiar observation and question through the
opening action and shows the scientific payoff in a distinct shot. Acceptable
product/source correspondence still depends on the actual depicted implementation.
The v2 running time follows the measured story; earlier policy versions retain
their original duration rules.

Blueprint compilation preserves these decisions. Producer checks them at
handoff and before production; current exact-media QA checks all three of product
recognition, mechanism comprehension and viewer comprehension independently.
The 3D film and every shot require actual encoded audio/video, exact hashes, duration,
observed actions, heard narration, eight comprehension answers and reviewer
identity. Blind observations must precede explanatory-script review. These are
independent-reviewer proxies, never a claim that real audiences must understand.
Static sampling cannot grant continuous-video or listening acceptance.

The existing growth contract separately binds retention, like, save, comment and
follow to knowledge, source, shot, action, narration and planned time. Exact-media
review receipts must cover every goal in the 3D film, including the complete
planned action interval. No evidence, stale evidence, mismatched narration,
irrelevant comments or answer-withholding cannot pass. Honest missing discussion
opportunities remain UNKNOWN. Rates remain null until actual platform data arrive.

Independent content failures recorded in `content_repairs` take priority over old
render approvals and generic missing-handoff scheduling. Producer continues with
the specific repair; unresolved content defects block production acceptance.
Subtask success, preview creation and code tests do not mark a task delivered.
The current ledger requires one complete 1920×1080/30fps 3D MP4 with Neil,
3:4 and 4:3 covers, references, actual-render 3D provenance and reports,
independent final QA and an actual user delivery receipt.

Tests in `test_comprehension.py`, `test_growth_objectives_v2.py` and
`test_content_repair_priority.py` include deliberate counterexamples. Generated
grey-video fixtures exercise actual MP4 probing and evidence bindings only.
The real spin-mop media inspection is separately recorded under
`output/tasks/spin-mop-20261115/qa/product-comprehension-audit.v1.json`; it failed,
and no synthetic fixture result supersedes that finding.

## Existing production checkpoints

1. Research handoff: `validate_product_research` checks real product identity and
   observed product sources before CAD. Video records actual `viewed_ranges`,
   `key_timecodes`, `viewing_method`, `confirmed_actions` and explicit unknowns.
   Static sources record inspected regions. Unobserved motion stays UNKNOWN.
2. Blueprint and production: `validate_product_plan`, independent content QA and
   `reference-model-qa` bind implementation, appearance, parts, connections,
   located input/transmission/output claims, work/reset and exploded relationships.
   Product-to-parts-to-function continuity and executable shots are required.
3. Animatic/preview/final QA: `validate_media_qa` binds encoded MP4/audio, complete
   action intervals, heard narration, reviewer and capability. Blind answers cover
   product, operation, core parts, power source, transmission, output, new knowledge
   and narration match before script review. This is a reviewer proxy, not measured
   public comprehension. Static frames cannot establish listening or continuous motion.
4. Growth: existing `growth_policy_version=2` separately checks retention, like,
   save, comment and follow against exact media/version, source, knowledge, shot,
   complete action interval and narration. Record payoff and gaps; actual platform
   performance stays null until platform evidence exists.
5. Completion: existing workflow requires mechanical/content/final QA, both covers,
   actual-render provenance, reports and a user delivery receipt. UNKNOWN cannot
   become PASS by renaming, compilation or successful tests.

These checkpoints use existing roles, immutable handoffs and the task ledger.
They do not authorize a second orchestrator, comparison video, retired 2D/2.5D
production or automatic rebuilding of historical products.
