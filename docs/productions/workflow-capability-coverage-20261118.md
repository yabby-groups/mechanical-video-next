# Scene and camera capability coverage — 2026-11-18

This is a bounded capability audit of the current shared engine, its tests and
located media. It does not change research, geometry, configuration or acceptance.
“Implemented” means a parameter reaches production code; “tested” identifies
the actual test scope; “rendered” requires a located media file. None of these
alone means scientific, perceptual or delivery acceptance. No continuous viewing
or listening was performed for this audit.

The sixteen requested features are mapped below. All have an implementation
path for a stated scope; several still lack a bound rendered regression, and
none establishes a general physical simulation capability.

## Subsequent real render regressions

After the initial audit below, the Producer ran the existing fixed-ring teaching
fixture through the same asset/shot adapters and global production lock. The
[inputs and runner](../../output/regressions/science-capabilities-20261118/run.py)
and [bound receipt](../../output/regressions/science-capabilities-20261118/receipt.probed.v2.json)
record five actual 1120×720/30 clips, 30frames each: Boolean cutaway,
camera_follow, field_visualization, flow_visualization, and state_transition
with animated opacity plus a shared nonuniform time_map. Each encoded clip
completed the normal decode check; ffprobe independently confirmed its format
and frame count. The legacy panel default determines this test format because
`framing` was omitted; it is separate from the fullframe 1080p production.
The receipt binds actual clips and Blender checks/scene source.

These close the initial table's missing **basic rendered execution** for those
adapter paths. They do not establish optical/field/force simulation, continuous
watching, arbitrary-asset reliability or scientific/perceptual acceptance. The
table's original M1–M3 coverage remains a dated audit snapshot, and its broader
limitations remain applicable. These short regression clips are not the
147-second acceptance film and are never substituted for it.

| # | Feature | Actual reusable parameters and code | Tested / actual media evidence / limit |
| --- | --- | --- | --- |
| 1 | Overall view | `template: overall`; `camera_direction`, `camera_roll`, `camera_view`; `frame_camera` fits evaluated assembly bounds. Policy-2 `camera.preset: establish` configures the same renderer. | Existing renderer and pipeline tests; M2/M3 contain overall views through `state_transition` and authored camera paths. An overall composition is not proof of hidden geometry. Cameras are currently orthographic. |
| 2 | Exploded view | EAS `explode`/`exploded`; generic imported assets use `exploded_view`, `science.driver: data_tracks` and authored object `tracks`. | `test_demo_configuration_and_all_template_contracts` validates the generic contract. M1 has an editorial cover separation, not full disassembly. EAS checks still hardcode planetary part names and axial pairs; arbitrary asset separation paths require source-reviewed poses. No automatic safe disassembly planner. |
| 3 | Reassembly | EAS `assemble`; generic source-reviewed reverse/reassembly poses through `exploded_view` or `state_transition` tracks. | EAS checks reassembly matrix residual against original transforms. No bound general imported-assembly reassembly MP4 was identified in this audit. Returning to a pose does not prove insertion clearance, contact or assembly feasibility. |
| 4 | Section / cutaway | `template: cutaway`, `section_plane: {axis,side,offset,parts}`; Boolean difference after deformation in `render_shot`. Policy-2 `camera.preset: cutaway` requires the plane. | Schema tested; actual Boolean implementation exists. Neither M1’s lifted cover nor M3’s transparent core is a Boolean-cutaway regression. No corresponding rendered regression is asserted here. Cutter/manifold/cap appearance and mechanism occlusion require per-asset checks. |
| 5 | Transparency | `science.opacity_tracks: [{object,keys:[[progress,opacity],…]}]`; `opacity_tracks` copies object materials and wraps the original connected surface shader after studio styling. | Bounds and object scoping tested. M3/C2 render opacity0.18 on the supply core/rim. Those keys are constant: actual changing-opacity/fade behavior has code/contract coverage, not a bound animated-fade regression here. This is editorial transparency, not optical transmission. |
| 6 | Isolation | `visible_parts`; policy-2 `camera.preset: isolate`; existing controlled studio-light adjustments. | Part references validated; M2/M3 isolate the drive interface and spring macro. Hiding a part does not prove removal, a legal disassembly path or its mechanical absence. Retained constraints/guides must address visible parts. |
| 7 | Micro / close view | `micro_zoom` or policy-2 `closeup`/`macro`; `camera_focus_region`; `science.camera_path` keys `{progress,target,direction,width}`. | Focus requirement and ordered camera keys tested; M2/M3 render close views and changing orthographic width. Focus-box checks deliberately do not validate the surrounding full assembly; no autofocus, depth-of-field model or microscopic material solver is supplied. |
| 8 | Follow camera | `template: camera_follow`, motion driver and `science.follow: object`; `follow_camera` translates the existing camera with the evaluated object origin. | Template/required target contract tested. No bound follow-camera rendered regression was identified here. It retains camera orientation; it is not a camera orbit, deforming-vertex tracker, collision avoidance or automatic occlusion solver. |
| 9 | Trajectory / path | `motion_trace` + `science.anchors`, `trace`, `radius`, `color`; `add_curves` samples evaluated poses. `science.guides` supports object/vertex-bound markers, arrows and dashed spans. | M1 renders a moving-part trace; M2/M3 render source-bound direction guides/witnesses. Anchor and projection receipts are tested. A curve or arrow is a visualization of supplied motion, not an independently integrated trajectory or measured force vector. Occlusion and temporal readability remain perceptual checks. |
| 10 | Fast / slow motion | Normalized `tracks`/`mesh_tracks` with `seconds`; nonuniform changes use the shared monotone `science.time_map`. | Pure numerical composition and actual retime adapter logic are tested, including holds, source corners and layered F-curves. M2/M3 use retimed/prescribed poses, not the new `science.time_map` field. Do not equate changing a procedural shot’s duration with a playback-rate change: `asset_motion` is sampled at actual FPS/time. |
| 11 | Flexible material / winding | Prescribed `mesh_tracks` with stable pose topology; `centerline_strip(points,width,normal)` authors consistent ribbon vertices/faces. Source assets stay independently inspectable. | Strip width/topology tests; M2/M3 render winding and ribbon shape keys. C1/C2 evaluate fixed-hub spring fingers and loop geometry. These are source-bounded teaching deformations; no tension, contact, volume/length conservation, material stiffness, fatigue or winding solver is established. |
| 12 | Constraints | Registered asset controls; existing mesh-pose alignment; optional `check_pairs`; `science.constraints` currently supports evaluated point-distance ranges/tolerances. | Failure detection is tested. C1 checks all four phases in Blender; C2 records218 rendered output frames, zero hub error and tip/core errors≤1.87e-9m under unchanged1e-8m tolerance. This is an assertion system, not a general joint/contact/dynamics solver or continuous subframe proof. |
| 13 | Field / flow depiction | `field_visualization` / `flow_visualization`; `science.paths` world-space polylines, `radius`, `color`; flow markers move along supplied paths at constant geometric speed. | Bounded nondegenerate path contracts tested; 3D curve/marker implementation exists. No bound field/flow rendered regression was identified here. No automatic field integration, physical flux/magnitude, turbulence, particles, thermal/pressure/electromagnetic solver or solver-import validation. |
| 14 | State change | `state_transition`, `science.driver: data_tracks`, explicit rigid/mesh endpoints and intermediate poses; policy-2 progression records distinct observable states. | M2/M3 render coating use, radius change, interface slip and radial load/hold/release; state/progression contracts tested. Prescribed endpoints do not establish material transfer, fracture, phase change, adhesion or spontaneous physical state evolution. |
| 15 | Comparison / split-screen | Original Remotion `comparison`, `angular_comparison`, `dual_reel_speed`, `data_animation`; two-source `split_screen.sources` for licensed supporting footage; `SplitScreen` renders both sources with credit. | M3 renders equal-arc, changing-radius, nominal-ratio and force comparisons; their data/text contracts are tested. Two-footage split-screen has implementation/provenance checks, but no dedicated test or bound rendered split-screen regression was located. It is restricted to supporting footage; no automatic two-model native-3D duplication, matched camera rig or claim of native-core proof through that footage path. |
| 16 | Time compression | `science.time_map: [[screen_progress,source_progress],…]` shared by all rigid and mesh channels; endpoints0→0 and1→1, increasing screen clock, nondecreasing bounded source clock. Alternatively preauthor a verified monotone pose remap. | Tests prove piecewise-linear F-curve composition preserves source corners and holds across101 samples and rigid/mesh channels. M2 has a separate, bound preauthored retime audit; M3 reuses that bounded motion. The new generic time-map field itself has no bound rendered regression here. Reversal, extrapolation, EAS/procedural retiming and independent per-contact clocks are not supported by this field. |

## Source and test pointers

- [Existing scene adapter](../../blender/scene.py): `render_shot`, `frame_camera`,
  `prepare_data_tracks`, `verify_mesh_tracks`, `configure_explosion`.
- [Science adapter](../../blender/science_scene.py): `add_curves`,
  `follow_camera`, `project`, `retime_data`, `opacity_tracks`, `check_constraints`.
- [Camera and guides](../../blender/science_guides.py): `camera_motion`, `point`,
  `add_guides`; local points use native object coordinates and evaluated transforms.
- [Parameter validation/math](../../mechanical_video_next/science_shots.py):
  `validate`, `validate_motion_program`, `source_progress`,
  `retimed_progress_keys`, `centerline_strip`.
- [Visual plan/compiler interfaces](../../mechanical_video_next/visual_narrative.py):
  `validate_execution`, `configure_blender`, `validate_graphic`;
  [comparison renderer](../../remotion/src/VisualNarrative.tsx):
  `SplitScreen`, `DataAnimation`.
- [Science tests](../../tests/test_science_shots.py),
  [motion tests](../../tests/test_science_motion.py),
  [visual tests](../../tests/test_visual_narrative.py), and
  [contract tests](../../tests/test_production_contract.py): **26 tests passed**
  in this audit via `uv run python -m unittest tests.test_science_motion
  tests.test_science_shots tests.test_visual_narrative tests.test_production_contract`.
  Template-contract tests instantiate examples; they do not execute every template
  in Blender. The retime adapter test uses F-curve stand-ins; C1/C2 are separate
  actual Blender evidence for spring mesh/constraints.

## Located media and numerical evidence

These are evidence bindings checked during this audit, not a new acceptance ledger.

| ID | Actual artifact | Binding and scope |
| --- | --- | --- |
| M1 | [Science template film](../../output/science-template-demo-final.mp4) | SHA256 `a324f20b6c16b51e377c14c062481194245b605643ea1be6b1b34f1779552f9b`; ffprobe1920×1080/30,330frames,11s. [Existing verification](../../output/science-template-demo-provenance-verification.json) is technical replay; no human acceptance implied. Cover separation and trace are not proof that all science templates rendered. |
| M2 | [Prior correction-tape v6](../../output/tasks/production-1794969915231117000/preview-v6/correction-tape-3d-preview.mp4) | SHA256 `9170060695c1ab3aa9e4906e79354fa8e860b46d63d7c717107aab5e31d18aef`. [Receipt](../../output/tasks/production-1794969915231117000/preview-v6/preview-receipt.json) binds clips/config/provenance. Its15s prescribed mechanism workprint remains distinct from a full film; spring radial deformation was not proved by that old rigid track. |
| M3 | [Completed earlier full acceptance-topic preview](../../output/workflow-acceptance-20261118-blueprint-f1aa05cdc653e7c9-preview.mp4) | SHA256 `d1c221785531534438e2d2cc90590c2908e2e7df72421bedab397caf9871b707`; ffprobe960×540/30,4,417frames,147.233333s. [Manifest v2](../../output/tasks/workflow-acceptance-20261118/handoffs/animatic-manifest.v2.json) binds config hash `5c56706cdd2593461e38d7af0caee69fd14685b07dc5410075f767eddc0b8036`. [Sampled QA](../../output/tasks/workflow-acceptance-20261118/qa/animatic-qa.repaired.v2.json) leaves listening/continuity/occlusion and other perception UNKNOWN. |
| C1 | [Actual Blender coordinate/phase inspection](../../output/tasks/workflow-acceptance-20261118/asset/spring-coordinate-inspection.v1.json) | SHA256 `240e050430642b9b0eefd9c9cea095cec834c553610fad44dfe1ac437875a3bb`. Exact194-frame failed shot passes after native-unit anchor correction; all four phases pass evaluated mesh/constraint checks. Inspect-only, no rendered quality inference. |
| C2 | [Rendered spring/loop clip](../../work/cache/shots/1965e88c4c33c6b83198b1a2b0628375c20bb3295eea9dd9a497d24d2a6e1b41/media.mp4) and [checks](../../work/cache/shots/1965e88c4c33c6b83198b1a2b0628375c20bb3295eea9dd9a497d24d2a6e1b41/checks.json) | Clip SHA256 `723899e40f445aaa7f76ca42cc427a4ad77b1874e1d593d99efc1b0e23b2ac99`; opacity0.18 and218 evaluated-frame distance checks are recorded. Cache artifacts are regenerable; their presence is technical render evidence, not permanent QA acceptance. |

At this audit snapshot, a newer13-shot configuration totalled147.233333s with
SHA256 `9c6a330f7997cb02f9d010dd87b251016f2f69d217e3a19cae997a64d54bb9c9`;
its complete render was still running. M3 belongs to the earlier bound version
and cannot be relabeled as that newer preview or as a1920×1080 final. The task
ledger remained `ASSET_READY` with successful technical stages and
`quality_accepted:false`. Later Producer stages/QA, not this snapshot, own any
subsequent completion or delivery claim.

## Future-topic support and compatibility risks

Future mechanical subjects can reuse independently identified source assemblies,
arbitrary named-part rigid poses, stable-topology mesh poses, camera paths,
isolation, sections, guides and original information comparisons. Source identity,
the one selected implementation, dimensions/approximations and actual actions
must still be established before invoking those tools. Declarative reusable
`controls` do not automatically add an executor: current procedural
`asset_motion` calls the existing fixed-ring rig; other mechanisms use explicit
verified data tracks or separately implemented/validated controls.

Future physical phenomena can use the contract’s bounded
`subject_kind: physical_phenomenon`, located `science.facts`, conceptual or
mathematical 3D depictions and source-bound data animation without inventing a
retail product. The tested contract permits that subject class. It is not proof
of an end-to-end accepted arbitrary-topic film or of a numerical solver. In
particular `physical_simulation` remains explicitly rejected by science-shot
validation. Chemical/material effects, fluid/thermal/electromagnetic models and
contact-dependent outputs require capabilities/evidence beyond supplied paths.

Important compatibility boundaries:

- Object-local units must follow the actual mesh transform. The encountered STL
  objects store millimetres with scale≈0.001 while explicit meshes store metres
  at scale1. [V3 anchor correction](../../output/tasks/workflow-acceptance-20261118/asset/SPRING-ANCHOR-CORRECTION-v3.md)
  preserves the world-space zero-distance check and original tolerance. Never
  silently normalize anchors or apply the scale twice.
- Mesh/vertex anchors require stable indices and no unsupported topology-changing
  modifiers. Exact explicit meshes avoid relying on STL importer vertex order.
  An arbitrary replacement asset invalidates its dependent pose/anchor evidence.
- Opacity depends on node-based connected surface materials and Blender’s EEVEE
  transparent rendering behavior. Camera/section/transparency may expose holes,
  obscure movement or change apparent shading despite valid numeric bounds.
- The shared retime map changes mechanical data channels; camera, text, guides’
  visibility and opacity use the screen clock. Their alignment must be authored.
  Sampled geometry and clamped source ranges do not establish physical rates.
- Render/source changes participate in existing cache keys; science uses actual
  source hashes. Editorial-only changes reuse geometry when inputs match. A
  shared science-engine source edit can invalidate multiple science shot caches;
  it is not guaranteed to affect just one clip. Legacy source equivalence is
  exact-hash/pinned-review only, not blanket cache approval.
- Keep the existing uv runtime, serial Blender lock, work/disk budgets, chunk
  encoding, gray/metal style, Neil and readable subtitles. Formal six-dimension
  QA, complete viewing/listening, covers, provenance, originality/rights and
  actual delivery remain separate requirements. Unsupported or UNKNOWN physics
  restricts dependent claims/shots rather than manufacturing a global PASS.

Requested role routing: `gpt-6.1-sol/high`. Observed runtime model, effort, token
usage and cost telemetry were unavailable (`null`). No new agents were spawned.
