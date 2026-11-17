# Native Producer dispatch contract

This contract governs the existing sole native Producer and its role agents; it does not introduce a dispatch service. Role configuration and session settings determine what can actually start. Configuration semantics: [OpenAI subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## Routing and concurrency

| Responsibility | Model | Reasoning effort |
| --- | --- | --- |
| Producer | gpt-6.1-sol | high |
| mechanical_research, cad | gpt-6.1-sol | high |
| qa | gpt-6.1-terra | high |
| animation, editor, research | gpt-6.1-terra | medium |
| viral_research, asset | gpt-6-luna | medium |

Only these three models are in scope. Do not silently substitute a model or reasoning level if a role cannot start: record the actual error and resolve the configuration or availability issue. The default is at most two concurrent subagents. A session may explicitly override this to at most three when independent research or verification justifies the additional concurrency; record the reason. The root remains the sole Producer, and agents do not delegate further.

## Before each spawn

1. Check whether a deterministic existing tool can perform the work, and whether existing evidence or output already answers it with matching content hashes and versions. Check what inputs actually changed.
2. Batch compatible work, check active assignments for duplication, and use parallelism only for independent work. Preserve independent QA rather than combining it with production.
3. Specify responsibility, exact input paths and hashes, relevant timecodes, owned output path, and verification method. Supply compact context and the relevant immutable handoff, not the full conversation history; use `fork_turns="none"` when supported.
4. Reuse research only when topic, concrete mechanism, source content hashes and research versions match; retain timestamps and freshness limits. An input change invalidates affected evidence and dependent QA. Repair only the affected delta and preserve prior results and defect history.

Luna collects bounded source or asset evidence and reports unknowns; complex conflicting mechanical evidence goes to Sol for resolution. After repeated Terra failure, submit the evidence, attempted strategies and relevant diff to Sol for diagnosis; do not repeat an unchanged failure or lower acceptance requirements.

Record assignments, starts, completions, errors and measured counters through existing `agent_runs` and event mechanisms. Use available actual telemetry; token and cost values are `null` when unavailable. Bind outputs through existing versioned, hash-checked handoffs. A successful start or technical check does not itself establish perceptual or mechanical acceptance.

## Production invariants

Keep the current 3D-only scene, spatial motion and render provenance requirements, source and product correspondence, independent QA, locked studio style, Neil narration, subtitles, both cover ratios, safe cleanup and five-goal growth evidence. Preserve historical assets and failures. No fallback to another visual route, no fabricated observation or acceptance, and no publication. Follow existing `AGENTS.md` and production gates when applying this contract.
