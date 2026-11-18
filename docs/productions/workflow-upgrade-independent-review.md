# Workflow upgrade independent review — 2026-11-18

Scope: integration audit of the current working tree, including production policy,
workflow and handoffs, scientific shots, Remotion and media provenance. This is
an interim code review, not acceptance of a film. Requested QA role/model: `qa`,
`gpt-6.1-terra/high`; actual runtime identity and usage telemetry are unavailable
and therefore null. No continuous video or audio review has been performed.

## Findings reported to Producer

1. **High — production policy binding prevents final route validation.**
   `provenance.write_remotion_proof` writes visual, media and progression policy
   fields into the build but omits `production_contract_version` and
   `production_contract`. `workflow.check_requested_routes` calls
   `visual_narrative.match_policy` on the task and that build, which rejects the
   missing policy for a new `mixed-original-v1` task. Propagate and validate the
   fields through build and Remotion props, with a full new-policy route regression.
   Status: code repair verified. `write_remotion_proof` now copies both policy
   fields into the build; its verifier compares build, props and config policy.
   A complete new-contract build-to-delivery execution has not been verified.
2. **High — incomplete split-screen source manifest.** `media_policy.write_manifest`
   records the primary selected asset and render output, but does not list the
   second visible split-screen source, its source interval and rights. The build
   proof records supplemental bindings, but `validate_manifest` does not compare
   a complete explicit source list against it. Record both sources and their
   rights/interval/credit, and reject omissions or mismatches. Status: reported;
   code repair verified. `supplemental_sources` records both sources and their
   rights and time ranges; `validate_manifest` compares this list with the
   executable configuration. Real split-screen end-to-end replay is pending.

## Checks and limits

Focused `unittest` suite: 18 tests passed (`test_production_contract`,
`test_media_revision`, `test_science_motion`, `test_remotion_editorial`,
`test_visual_narrative`). These passing tests do not cover the two integration
failures above and do not establish baseline-wide regression status. The initial
`uv run pytest` attempt could not start because pytest is not installed; the
repository's unittest runner was used instead. No movie was supplied for the
initial review; six final dimensions, listening, full-timeline viewing, blind
comprehension and delivery remain UNKNOWN.

Follow-up: 15 tests passed across `test_production_contract`,
`test_remotion_editorial` and `test_media_policy`. Two further focused tests in
`test_hybrid_build_bindings` passed on independent rerun: they exercise actual
proof writing and verification, policy omission/tampering, manifest writing and
validation, and omission, rights or interval tampering for split sources.
They use temporary placeholder media and mocked probe results; they do not
render or verify an actual complete film or its delivery route. These tests do
not establish perceptual acceptance.

The current 147-second workprint SHA256 `6ee8fa3adb8b7573d550249ffd9ee6728dd0745bedbc48e82d9f4c5803132e8f`
was independently sampled at 72 and 96 seconds. Both earlier chart-label
overlaps are absent in those frames. Its decoded audio matches the preceding
workprint, but its decoded video differs; the workprints are not claimed to be
visually identical. The full decode and format check passed. Dynamic motion,
full-timeline vision, listening and phone-size readability remain UNKNOWN; see
the task's `qa/animatic-qa.current.v1.json` and `qa/preview-qa.current.v1.json`.
