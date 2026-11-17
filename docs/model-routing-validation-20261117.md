# Three-model routing validation — 2026-11-17

Changed only the existing project configuration, role instructions, native
Producer guidance, and existing telemetry/export paths. No new agents, dispatch
service, cost service, provider, credentials or approval changes were introduced.

## Configuration and actual execution

CLI: `codex-cli 0.169.0`. Configured and observed provider: `huabot`, Responses,
`https://api.huabot.com/v1`. Provider settings were read without exporting secrets.

| Role | Project model / effort | Actual new native execution |
| --- | --- | --- |
| Producer | gpt-6.1-sol / high | Existing open root remains Sol / low |
| mechanical_research | gpt-6.1-sol / high | Sol / high, completed mechanical source review |
| cad | gpt-6.1-sol / high | Parsed explicit configuration; not separately spawned |
| qa | gpt-6.1-terra / high | Terra / high, completed scoped v9 QA |
| animation | gpt-6.1-terra / medium | Parsed explicit configuration; not separately spawned |
| editor | gpt-6.1-terra / medium | Terra / medium, authored dispatch contract |
| research | gpt-6.1-terra / medium | Parsed explicit configuration; not separately spawned |
| viral_research | gpt-6-luna / medium | Parsed explicit configuration; not separately spawned |
| asset | gpt-6-luna / medium | Luna / medium, organized existing real source/model inventory |

All eight standalone TOMLs explicitly set both values and retain the original
developer instructions and descriptions. Additional instructions constrain Luna
to collection/classification and route complex mechanical conflicts to Sol.
Project defaults are Sol/high for Producer and Luna/medium for children. The
default concurrency is two children. A justified temporary session override may
allow three; this audit never needed more than two simultaneously running children.

Role TOMLs take precedence over resolved spawn/default/inherited values, per
[official configuration documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents).
The role settings were discovered live by the native spawn tool. Actual child
`turn_context` records, rather than model self-reports, establish the four tested
role assignments. No fourth model or client-side fallback was used.

Changing project TOML does not mutate an already-open root turn. Its recorded
effort remains low; Producer high is therefore configured, **not verified active
in this existing root**. Set high in the client for a subsequent turn or use a new
session loading project defaults; do not launch another Producer for this task.
Provider-internal upstream routing cannot be independently proven from native
logs. Untested roles and a fresh-root high startup remain compatibility limits.

## Verification and observed reuse

`uv run python -m unittest tests.test_workflow tests.test_codex_usage
tests.test_three_d_only tests.test_producer_continuation -q`: 44 tests, OK, one
skip. This covers 3D-only enforcement, continuation, legacy telemetry compatibility,
new runtime metadata and null billing. Scoped whitespace validation passed.

Actual native starts used `fork_turns=none`, compact assignments and existing
roles. Luna organized real sources; Terra edited an actual file; Sol reviewed
the current concrete mechanism; Terra/high independently checked v9 bindings.
No full production was launched for testing. Roles not needed for these tasks
were deliberately not started merely to exercise each name.

Python/ffprobe checked the existing v9 hash and 1920x1080/30 streams without an
Agent call. Existing sources/models were reused without another full search or
download. Sol found no new source/mechanical conflict requiring CAD/render repair;
the old stop-visible-v3 render suggestion was superseded for this native
continuation by the existing v9 film. No repeated search/download/CAD/render was
started. These are observed skipped operations, not a measured savings ratio.
Cross-session reuse remains an instruction of the sole native Producer using
existing hashes/handoffs; no automatic dispatch interceptor was added or claimed.
Complex-conflict escalation is explicit in QA/Luna/Terra instructions; no new
complex failure occurred in this audit, so a real conflict escalation was not
observed. Sol did perform the actual mechanical review.

## Evidence, usage and production continuation

Local evidence is under
`output/tasks/hand-crank-pencil-sharpener-20261116/`:

- `producer/model-routing-native-usage.json`: native thread IDs, provider,
  observed models/efforts, measured token counters and completion timing.
- `producer/model-probe-luna.json`, `producer/model-probe-sol.json`: source/model
  input hashes and bounded research conclusions.
- `qa/model-routing-v9-scope-review.json`: exact-media independent technical scope.
- `producer/model-routing-reuse-check.json`: deterministic checks and skipped calls.
- `producer/model-routing-production-continuation.json`: resumed production decision.

Existing `agent_runs`/events accept model, effort, task type, input version,
outputs, cache hit, duplicate, cost, success and retries. Unknown observations
remain null. The existing native usage exporter now retains observed model/effort
and provider without exporting conversation contents. Token counters include
repeated cached context and are not unique source bytes or money. Actual price,
billable cost and a comparable before/after baseline are unavailable; monetary
cost and savings percentage remain null. This run does not prove lower total cost.

Completed child counters for this audit (native telemetry, not billing):

| Role | Total tokens | Cached input tokens |
| --- | ---: | ---: |
| asset | 623165 | 550784 |
| editor | 177567 | 139904 |
| mechanical_research | 482593 | 407296 |
| qa | 261158 | 224384 |
| Total | 1544483 | 1322368 |

The repeated system/project/tool context remains substantial even with
`fork_turns=none`. No claim of reduced token consumption follows from using
cheaper models. These probes also performed actual source organization,
documentation editing and production review rather than an additional full film.

Production was resumed, and actual Sol review plus independent Terra QA advanced
the existing v9 film without remaking assets. Media SHA256:
`d9edb4615f81d835e2e1989ad50eba85473f9d397b3e4499f4b88c3233ea37ec`,
duration 120.266667 seconds. Existing Neil, 3D provenance and covers are preserved.
The generic continuation ledger still contains older shot recommendations; the
Producer resolution records why they must not trigger blind repeated work.
Continuous viewing/listening, comprehension and formal mechanical acceptance
remain UNKNOWN. No publication or background production is claimed.
