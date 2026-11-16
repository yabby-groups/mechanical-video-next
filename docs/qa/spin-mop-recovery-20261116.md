# Spin mop recovery: stopping and delivery boundaries

The existing task is `output/tasks/spin-mop-20261115`; no replacement task was
created. Its recovery inventory preserves 695 pre-existing files, their hashes,
and the original task ledger before the scope expansion authorized on November 16.
The existing Neil recording is reused; recovery must not resubmit paid requests.

## Confirmed stopping causes

The original ledger never marked the entire task completed: it remained
`RESEARCHING`. `native-agents.v2.json` marked individual research, asset, CAD,
script, and animation assignments `COMPLETE`, while task events ended after
diagnostic rendering and an asset handoff. Those assignments did not produce a
complete film. The old `produce --resume` branch only appended `producer_resumed`
and printed a path. It neither reconciled available artifacts nor dispatched a
next command. The external `--codex` branch treated a successful subprocess exit
as its own successful return without checking delivery. Stage and child-run
records did not maintain a global next action. Consequently ending the native
Producer turn left no executable continuation contract.

There was also a real integration dead end: an independent configuration review
could authorize a full low-cost dynamic animatic while the CLI only allowed
short diagnostics during `RESEARCHING`; full local production required a later
state. Changing the state without completing its handoffs would conceal this
gap. Recovery instead needs an explicitly reviewed low-cost diagnostic boundary,
with exact configuration/dependency hashes and the regular production lock and
resource checks. This permission must never authorize expensive final rendering.

## Mechanical and editorial findings

US20120233794A1 and WO2012051780A1 describe the same patent-family embodiment.
The current v5 model is a bounded teaching model of that embodiment, not an
identified retail product. The part-level audit is preserved under
`mechanical-research/reference-to-model.v1.json` and `.md` and an immutable
`reference-to-model` handoff. It covers 15 part groups, their source positions,
connections, constraints, approximations, and verification limits.

The upper sleeve/tube torque-reaction interface remains undocumented (SQ01).
An explicit external teaching boundary cannot establish that manufacturing
connection. Spring deformation, cloth dynamics, basket support, contact forces,
and inertia are not solved. The existing validated core must not be rebuilt for
missing editorial annotations. The original complete plan has ten chapters,
33 measured utterances, and a 149.0667-second frame-aligned timeline.

The previous preproduction review identified executable-expression defects:
static spring/stop chapters, missing rotation witness and spatial context, and
late reaction-boundary labels. Recovery implements and independently rechecks
those changes. The layered conversion must preserve intermediate poses, not
only the start/end poses of a pivot/return/detachment sequence.

## Regression and acceptance scope

`reference_policy.validate_reference_model` checks part-level audit fields,
source/model/animation bindings, explicit teaching approximations, and unresolved
core issues. It does not perform the visual or mechanical audit itself.
Continuation and delivery regressions are in `tests/test_producer_continuation.py`;
reference-to-model regressions are in `tests/test_reference_model.py`.

Actual task outputs and current test results belong to the version-bound task
reports, not this static note. No subprocess exit, local diagnostic, child
completion, or successful regression suite establishes final acceptance.
Continuous viewing and listening require actual review capability and remain
UNKNOWN when unavailable. A resumable action is not a background execution
promise. Unrelated historical videos and user changes remain outside this repair.
