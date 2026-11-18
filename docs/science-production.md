# Configuration-driven 3D science shots

Current production rules are in [production-contract.md](production-contract.md).
The initial increment and its measured demo below are historical evidence, not
the latest acceptance result. This upgrade also adds shared monotone time maps,
animated opacity, evaluated geometric constraints and flexible strip geometry;
the current capability audit and full-film evidence are linked from
[the upgrade report](productions/workflow-upgrade-20261118.md). These remain
prescribed teaching animations, not contact, material or field simulations.

This is an opt-in extension of the current Producer, asset builder, EAS/Blender,
Remotion, provenance verifier and shot cache. No alternate route, scheduler,
solver or acceptance system is involved. The first regression uses the existing
fixed-ring teaching rig; it does not identify a commercial gearbox.

The initial audit at `9c5dc5c` found working EAS explode/assemble, data tracks,
camera framing, shot caches and staged QA. The missing pieces were a reusable
configuration contract for non-mechanical phenomena, a Blender-to-Remotion
projection channel and provenance for that composition. The implementation
adds these at `science_shots.py`, `blender/science_scene.py`, and
`remotion/src/ShotInformation.tsx` without replacing the render or QA entrypoints.

## From topic to workprint

1. Start with `uv run python -m mechanical_video_next produce --topic '选题' --routes 3d`.
   The current Codex Producer performs research and creative decisions; the CLI
   creates a task, not an unattended intelligence service. For an existing task,
   resume it instead of recreating its assets or dispatching duplicate agents.
2. Query the local reference library and matching assets before searching or
   building. Bind each claim to a located primary source or justified derivation.
   Distinguish real product identity, abstract teaching model, and unknowns.
   Record a knowledge goal and the moving, exposed or measured evidence for each
   shot before allocating time to narration. Do not combine product editions.
3. In the executable base JSON, choose the asset and templates below. Keep the
   existing blueprint `evidence_map`, original narration and measured Neil
   timing. An `existing_shot` in a blueprint must use the same template/asset.
   Use one authored local time interval per annotation. For a short preview and
   separately evidenced shots, use the existing `stage ... keys/checks/local`.
4. Record unknowns as `RESEARCH_REQUIRED` on only the dependent shots. Keep the
   existing `VERIFIED`, `RENDER_READY`, `RENDERED` and `QA_PENDING` evidence flow.
   Optional `final-qa.shot_acceptance[shot_id]` binds the exact scoped `media` and
   separate `scientific`, `visual`, `comprehension`, `continuous_viewing` results.
   Only existing `advance ... COMPLETED`, after full independent QA and route
   checks, can promote a matching rendered shot to `ACCEPTED`. A successful
   run, encoded file, sampled frame or `PASS` as producer does not grant it.
5. Render fullframe 1920x1080/30 with Neil after the applicable gates. Bind the
   generated `*-final.3d-provenance.json` to the task's `3d-provenance.json`.
   Keep the existing checks for product correspondence, comprehension,
   full watching/listening, covers and five-goal report. A fixture's technical
   delivery is not production or publication approval.

## Blender shot recipes

Each added template takes `science.version: 1`, `mode`, `scope`, and `basis`
(`path`, `sha256`, `position` for each source). Choose `conceptual` (原理示意)
or `mathematical` (数学模型); the existing player visibly labels the mode.
`physical_simulation` is reserved and rejected: no solver-output validation is
implemented. A sampled curve does not establish field magnitude, a path does
not establish real flow, and algebra does not establish contact or forces.

The optional `driver` is `static`, `data_tracks` (existing `tracks` /
`mesh_tracks` with normalized `progress`), or `asset_motion` (a named registered
`control` on an existing compatible procedural assembly). Time uses `seconds`
and the real render FPS. Existing EAS `explode`, `assemble` and `exploded`, and
`overall`, `detail`, `motion` stay available. Add science metadata with a static
driver to legacy shots if they need to join a science composition/proof; their
own built-in motion, if any, still runs. Keep `visual_profile` at the approved
studio preset and inspect keyframes before native rendering.

| Template | Example configuration, in addition to `science` metadata |
|---|---|
| `exploded_view` | `driver: data_tracks`, with vertical separation or reassembly poses authored per object; conceptual only |
| `cutaway` | `section_plane: {"axis":"x","side":"positive","offset":0,"parts":["Body"]}`; explicit Boolean section, not transparency |
| `micro_zoom` | `camera_focus_region` authored in asset coordinates, same existing camera interface |
| `motion_trace` | `anchors` and `trace: "tip"`, `radius: 0.02`, `color: [0.1,0.5,0.8]`; samples the real evaluated pose |
| `field_visualization` | `paths: [[[0,0,0],[0,1,0],[1,1,1]]]`, `radius`, `color`; world-space provided curves |
| `flow_visualization` | Same curves as field; a marker traverses each path at constant scene-space speed |
| `state_transition` | `driver: data_tracks`, with explicit poses from progress 0 to 1; no state solver |
| `measurement` | Frame a physical part with the standard camera and provide `information` values with evidence |
| `camera_follow` | `follow: "Follower"` and a motion driver; translate the existing camera with the authored object, retaining its orientation |

Use `visible_parts` to isolate inspected components. Animated transparency,
separate comparison layouts, automatic vector-field integration, particles,
material/thermal simulation and solver import are not validated in this first
increment. Compose an evidenced teaching depiction rather than selecting an
unsupported mode. Full abstract topics still have to satisfy the applicable
existing task and QA gates; no arbitrary-topic capability is claimed.

## Reusable assets and information overlays

Add `reuse` version 1 to an existing assembly config: exact `mechanism_id`,
`units`, `license`, `scope`, bound `sources`, optional bound `generator`,
`limitations`, and `parts` with each part's name, parent and material. `controls`
declare supported driver, affected `parts`, degrees of freedom and constraint.
These are verified interface descriptions, not a generic joint solver. Existing
source-mesh assets retain file hashes, independent inventory and data tracks.
Use the normal reference and asset workflow to find models; there is no new
catalog database or claim of automatic mechanical matching.

An anchor `{ "object": "Lever", "local": [0, 0, 0.3] }` refers to an asset's
local point. Blender exports per-frame normalized screen coordinates using
the final camera. Projection alone does not prove lack of occlusion. In a
`storyboard` row, `information` uses local `time: [start,end]` and `box` in
1920x1080 pixels: `label` with `anchor` and `text`; `note` with `text`; `value`
with `prefix`, `digits`, `unit`, located `basis`, and `[progress,value]` samples;
or `inset` with a normalized `crop` of the same 3D render. Keep labels and
explanations inside the existing text safe boxes. Validate lines/insets against
critical action by observing the video: rectangle tests only cover text/inset
boxes, not all label leaders or occlusion.

For an in-scene macro, `science.camera_path` accepts ordered keys with
`progress` (0 through 1), world `target`, viewing `direction` and orthographic
`width` in scene units. Set `studio_lighting.camera_push: false` when supplying
this path. Moving close-ups deliberately crop the surroundings, so inspect crop
and occlusion in the preview instead of treating assembly bounds as a QA pass.
`science.stage_rotation` rotates the shot as a unit without editing the CAD.
For thin overlapping surfaces, opt in to `science.camera_clip: [near, far]`
using positive increasing distances in scene units. Bound the entire animated
subject between those planes; a tighter depth range can prevent render depth
conflicts without changing the geometry. The distances are recorded in shot
checks. Historical shots without this option retain their original clipping.

`science.guides` supports `arrow`, `dashed` and `marker`, with a linear RGB
`color`, scene-unit `width`, an optional normalized `window`, and one or two
`points`. Points bind a visible assembly `object` to its `local` offset; a
`vertex` index optionally tracks the object's evaluated, deforming mesh. Use
these guides for measured spans, fixed baselines and real relative motion,
and keep direction graphics separate from claims about force or torque.
`science.print_marks` attaches editorial text to a visible surface using local
placement, `rotation_euler` (radians) and `size`. These additions are staged 3D
guides, not source CAD or new physical properties. Melting, transfer, contact,
or other material effects still require explicit evidence and must not be
inferred from guide motion. For time compression apply one monotone time map
to all interacting tracks without widening their validated geometry range.

Names, cue text, formulas written as notes, and overlay timing stay in the
editorial layer. Adding or moving an anchor changes Blender's export and shot
key; edits to a label that uses the same anchor, formatting, subtitles or
same-length audio only recompose. Changed shot geometry, verified trajectories,
frame count or camera invalidate only affected clips. The same lock, work/disk
budget and chunk encoding remain in place.

With an explicit `scene_artifact_dir`, compact executable shot inputs are
archived beside the scenes and remain immutable. Cache checks verify their
hashes as well as rendered outputs. New mixed-original production also rejects
constant data tracks for a planned core mechanical shot before full rendering;
camera movement and opacity changes alone do not establish mechanism motion.
This preflight is necessary validation, not independent motion acceptance.

## Reproduce the regression

`tests/fixtures/production/science-demo.json` combines an editorial cutaway-like
reveal (moving the cover, not cutting it), an ideal motion trace, tracked label,
two angle readouts and the approved Neil profile. It does not bypass production
gates for arbitrary input: the fixed demo script only renders this fixture.

```sh
uv sync --locked
npm --prefix remotion ci
uv run python scripts/science_demo.py preview --env-file .env.local
uv run python scripts/science_demo.py final
uv run python -m mechanical_video_next.provenance output/science-template-demo-final.3d-provenance.json --report output/science-template-demo-provenance-verification.json
```

The env file is needed only for cache misses unless credentials are already
exported. The final and replay require local Blender, Chrome, FFmpeg, the
approved font and Remotion dependencies. Replay compares sampled Blender render
witnesses and the full decoded Remotion video/audio against the original (exact
audio and format, exact video when possible, otherwise every frame at least
45 dB PSNR to account for browser/encoder nondeterminism); it
does not prove scientific accuracy or human comprehension. Save the bound
composition, public inputs and reusable scenes while they are needed for replay.

## Measured regression

Final artifact: `output/science-template-demo-final.mp4`, 11 s, 330 frames,
1920×1080/30, H.264/AAC, approved Neil with utterance-aligned single-line
subtitles. SHA256 `a324f20b6c16b51e377c14c062481194245b605643ea1be6b1b34f1779552f9b`.
The verification JSON reports all 330 decoded replay frames, minimum 48.62 dB
PSNR, exact decoded audio, and six independent Blender render witnesses with
maximum RGB MAE 1.84. This is technical replay, not a subjective QA pass.

| Run (same machine) | Total | Cache hits | Sampled work peak |
|---|---:|---:|---:|
| First 1080p render, model/narration already cached | 420.222 s | 3/6 | 31,599,771 B |
| Same clips/audio, no tracked labels or angle readouts | 31.191 s | 5/6 | 29,442,078 B |
| Updated label and angle overlays, no rerender or synthesis | 30.768 s | 5/6 | 35,539,376 B |
| Identical final configuration, warm rerun | 0.552 s | 6/6 | 35,585,162 B |

The render used Blender 5.2.3 and Remotion 4.0.542; the cold 1080p run removed
360 verified transient files. Work peaks include caches retained by that point
and are not incremental disk deltas. The overlay control isolates composition
on matching input geometry and audio; these one-off timings are not a causal
speedup claim versus the old commit. Two Neil requests were observed in the
initial preview; provider bills, native agent usage and GPU energy cost were
not measured. See immutable per-run metrics under `output/runs/`.

Full clean-checkout comparison: HEAD ran 359 tests with 5 failures, 11 errors
and 4 skips; the upgraded tree ran 366 with 4 failures, 11 errors and 4 skips.
The remaining failures also occur at HEAD: ignored legacy media/configuration
is absent, and the historical style-lock files do not all match the recorded
hashes. The demo uses the explicitly unaccepted pipeline-test path and does not
replace the approved screenshot or unlock a formal task. The native QA role
reviewed sampled frames and recorded the follow-up in
`output/science-template-demo-independent-qa-v2.json`. The labels identify
the trajectory and 4:1 angle ratio at those frames; the height offset and
derivation are documented in the fixture source but not fully explained on
screen. Continuous viewing, listening and formal acceptance remain UNKNOWN.
The only end-to-end rendering evidence here is this teaching fixture, not a
claim of arbitrary scientific-topic automation.
