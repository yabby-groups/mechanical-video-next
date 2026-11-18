# Workflow engineering upgrade and independent review · 2026-11-18

The user explicitly chose to retain the other active task as the sole Producer
and assign this session engineering upgrades and independent review. This report
records that scope. The existing production task, stages, media, native roles,
model routing, handoffs and acceptance state remain authoritative. No second
Producer, scheduler, QA service or publication flow was introduced.

## Actual changes

| Module | Result |
| --- | --- |
| `production_contract.py` | Formal mixed-original acceptance requires actual-media observations bound to the current Blueprint shot and knowledge IDs, one dimension per record, independent reviewer, method, interval, conclusion and capability boundary. Each dimension cites its own covered shot records. Listening binds decoded PCM plus sample rate/channels. Missing intervals, stale identity, sampled-only evidence, generic shared conclusions and applicable FAIL/UNKNOWN cannot grant final acceptance. |
| `workflow.py` | Passes the existing immutable Blueprint to that acceptance check and preserves the declared comparison region when checking actual revision evidence. No new task state source. |
| `media_revision.py` | Supports a declared normalized content region, so a caption edit outside the subject region fails that claim. Uses the global 30 fps grid for fractional intervals and rejects matching early decoder EOF. Region changes cannot silently differ from the original repair request. |
| `science_shots.py` | Extends existing `science.constraints` with bounded rotation-ratio, polyline-length, travel/step and event-window declarations. Refuses vacuous positive-travel tolerances. |
| `blender/science_scene.py` | Checks those declared quantities on every evaluated output frame, including shape-key points; records compact extrema, excursions, residuals, travel and event frames. Refuses unresolved follower motion. Receipts explicitly state `KINEMATIC_ONLY`. |
| Existing tests and docs | Adds injected failures, real synthetic AV/FFmpeg comparisons, workflow integration checks and a durable native Blender regression. Updates the single production contract and science interface documentation. |

The first committed stage is `65ebc26` (QA/revision traceability). The motion
stage and this report are saved in the subsequent scoped commit. Other active
Producer changes to cache/export handling are separate work and are not credited
to this session. Historical models, films, failed evidence and the protected
style reference were preserved. Python stays on uv/3.14.2; Blender uses its own
embedded Python. The existing Sol/Terra/Luna configuration was not changed.

## Motion and physics actually checked

`rotation_ratio` checks signed increments in two unparented, unconstrained local
Euler channels. It requires driver travel and expected/observed follower
excursions resolvable above tolerance. It rejects wrong sign/ratio, stationary
followers and unsupported parent, constraint or quaternion interpretations.
This does not prove tooth geometry, axis alignment, contact, torque or energy.

`distance` retains evaluated joint/point bounds. `path_length` checks the declared
ordered anchor/vertex polyline, including interior deformation; it is not exact
curved-strip length, material conservation or tension. `motion` checks accumulated
anchor travel and each output-frame displacement, so a closed cycle can pass
without requiring nonzero endpoint displacement. Positive travel cannot pass by
enlarging tolerance. Event windows require actual sampled scalar states at the
declared output-clock interval.

These assertions are opt-in: planning still has to select source-supported
quantities and meaningful limits. They do not automatically validate an arbitrary
mechanism. Every output frame is tested, but no continuous subframe collision or
contact detection is claimed. Existing BVH `check_pairs` records source-surface
overlap candidates and is not a general penetration validator. General force,
friction, fluid, thermal and electromagnetic solver correctness remains outside
this change; science paths remain explicitly bounded teaching depictions.

## Actual validation

The [final source-bound receipt](../../output/engineering-upgrade-20261118/verification.json)
records **447 tests: 442 passed, 5 skipped**, 26.785 seconds, exit 0. All enumerated
source/test/configuration hashes were identical before and after the run. This
is the shared checkout including the original Producer's cache/export changes;
it is not a claim that every change was authored here or an isolated clean-tree
test of only this session's commits.

The five skips are the pre-existing historical delivery/media, teaching evidence,
frozen style inputs, opt-in full 3D-render integration, and task-local media
checks. They remain skipped; no new result was substituted for those historical
tests. TypeScript typecheck passed earlier in this session; no Remotion source
was edited here. This session did not render a new Remotion film.

The [native Blender receipt](../../output/engineering-upgrade-20261118/blender-motion-constraints.v2.json)
and [process log](../../output/engineering-upgrade-20261118/blender-motion-constraints.v2.log)
record Blender **5.2.3 LTS**, embedded Python **3.13.13**, exit 0 and **20/20
expected results**: five valid cases plus fifteen deliberately rejected cases.
Actual meshes, F-curves, evaluated transforms and shape keys are used. Cases
cover wrong direction/ratio, middle-cycle joint separation and path stretching,
static channels, jumps, missed/mistimed states, unsupported rotation scope and
overly permissive tolerances. No film frames were rendered by this test.

The initial restricted Blender process exited 139 during Metal initialization,
before Python execution. Its crash is retained in
`output/engineering-upgrade-20261118/blender-sandbox-startup-failure.txt`.
Authorized native execution succeeded without changing sandbox configuration.
The initial broad suite also retained 12 failures/errors caused by the existing
over-budget work directory; see the preserved initial log. A targeted command
once included a nonexistent test module; the corrected 22-test command passed.
The final regression and v2 Blender receipt supersede none of this failed history.

Independent QA found three traceability/integration defects and two tolerance
counterexamples during implementation. All five were fixed and checked in
follow-up review; findings and limits remain in the
[independent report](workflow-upgrade-independent-qa-current.md). That reviewer
did not independently run native Blender v2 and did not continuously watch/listen
to the film. Technical integration results are not independent film acceptance.

## Actual media and remaining acceptance

The existing Producer recovered its real task to `FINAL_CHECKING` and owns the
final delivery index. This session independently checked the current
[candidate identity](../../output/engineering-upgrade-20261118/candidate-media-identity.json):

- [Actual MP4](../../output/workflow-acceptance-20261118-mechanical-repair-v6-blueprint-c7af25f27960e62b-final.mp4):
  1920×1080, 16:9, 30 fps, 4,417 video frames, H.264/AAC.
- Video 147.233333 seconds; audio/container 147.243 seconds.
- MP4 SHA256 `12481b6874b5418e6f0888dd70f7e57fcb076b8160a659a86d4cbba1c1d2b5b0`.
- Decoded s16le audio SHA256
  `d754c08b1595bd4a4de8bfeb1d3b967af3e3a0df4bfcfed1d6aa0bb0ddedbf80`,
  48 kHz stereo. This hash identifies sound; it is not a listening result.

The other Producer reported complete provenance replay after recovery. This
session did not rerender or claim authorship of that film/replay. Its production
task, covers, source manifest, build provenance, full production metrics and
delivery index remain under `output/tasks/workflow-acceptance-20261118` and the
existing [production report](workflow-upgrade-20261118.md).

Full continuous viewing/listening, independent scientific/mechanical conclusions,
visual understanding, originality/rights and applicable formal acceptance remain
**UNKNOWN**. No review records were fabricated to satisfy the new gate. These
engineering results cannot mark the overall topic-to-accepted-video objective
COMPLETED. Arbitrary-topic autonomous accepted production remains unproven.

## Observed improvements and measurements

The demonstrated improvement is stricter detection and traceability: generic
review flags and one all-purpose record fail; each current shot/dimension has a
located record; stale sound and coverage gaps fail; caption-only changes outside
the requested region and incomplete decoded intervals fail; numerical motion
defects and loose-tolerance static cases are rejected. No audience-comprehension
gain or new visual-narrative improvement of the film is claimed from these tests.

| Measurement | Actual scope/value |
| --- | --- |
| Agent use | Two native children; eight recorded starts including scoped follow-ups. Requested routing Sol/high and Terra/high; actual runtime model/usage telemetry unavailable. |
| Input/cached/output tokens and cost | `null`; no savings percentage claimed. |
| Formal film render time here | No new film render. Original Producer's measured render/cache report remains separate. |
| Native regression | 20 expected-result cases; zero rendered frames; v2 execution details and hashes in its receipt. |
| Shared work peak during final tests | 2,103,583,515 bytes, sampled every second; not incremental test disk use or a continuous peak guarantee. |
| Minimum sampled free space | 16,711,680,000 bytes on the shared filesystem during that run. |
| Asset reuse/regenerated film shots here | No production assets rebuilt or film shots regenerated by this engineering session. |
| Aggregate repair attempts, failed attempts and manual interventions | `null`; not instrumented as complete counters in this session. Specific observed failures/coordination are disclosed above. |

Raw logs, receipts and exact source hashes are retained under
`output/engineering-upgrade-20261118`. They are verification artifacts, not a
parallel task ledger. No publishing, platform drafts or unattended continuation
was configured or claimed.
