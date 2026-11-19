# Cinematic camera study

The existing Blueprint `camera.settings.science` passes the optional `camera_rig`
to the existing shot producer, scene builder, provenance saver and chunk encoder.
`science.camera_path` still owns target, view direction, aim-plane width and time.
No new director schema, renderer or scheduler is introduced. Without `camera_rig`,
the original orthographic camera implementation runs unchanged.

The pinned official Add Camera Rigs 1.9.2 extension is unmodified and licensed
GPL-3.0-or-later. `blender/vendor/add_camera_rigs/SOURCE.json` binds its official
archive. Actual background Dolly and Crane probes are in
`output/camera-study/rig-probe.json` with inspectable animated scenes. The adapter
uses the official Camera and Aim bones and target constraint; two Empty controls
receive evaluated trajectories. Lens is fixed, perspective distance changes, and
both contacting surfaces stay sharp. No unsupported disassembly or shell crossing
is added. A/C retain the baseline open housing; B reveals the same static cover
with the existing native Boolean section, advancing its Y plane from -14 mm to
40 mm during the first 22% of the shot. The lower contact arc starts exposed.
The cover never receives an invented mechanical movement. The cut is editorial,
not a claim that the retail shell opens or disappears that way. A tested noisy
transparent-shell attempt is retained in `output/camera-study/b-opacity-failure`.

`config/cinematic-shots.json` has **no validated entries**. Dolly Push-in/Macro
Reveal and Tracking Follow/Contact Focus are experiments. Exploded Reveal,
Cutaway Reveal, and Orbit + Match Cut remain untested candidates with no defaults.
Existing mechanical data tracks, native model, base light/materials and action clock
remain identical. B's cover visibility/section and C's data are explicit permitted
visualization variables. The C overlay reports evaluated painted mesh centroid travel,
not measured physical slip or a solved friction state.

Select a stable overview for whole-mechanism relationships; use a closer moving
view only when it reveals a specific contact or internal relationship. Preserve
screen direction, scale context and enough time to see the complete action.
Continuous movement without a knowledge purpose is a defect. An independent
exact-video comparison may prefer the old camera. UNKNOWN sensory review cannot
promote an experiment, select a winner or replace an accepted production default.

An entry can enter `validated` only after independent dynamic review binds the
exact sample and covers the intended action. Record knowledge goal, objects and
control points, rig, actions/times, optics, visibility/occlusion conditions, visual
rules, executable adaptation, sample, limitations and located review results.
Do not broaden the tested scope to unrelated mechanisms or unknown geometry.

Recovery commands (project uv environment; Blender/Chrome need local GPU access):

```
uv run python scripts/camera_study.py prepare
uv run python scripts/camera_study.py full-plan
uv run python scripts/camera_study.py preview --version B
uv run python scripts/camera_study.py preview --version C
uv run python scripts/camera_study.py animatic
uv run python scripts/camera_study.py final --version B
uv run python scripts/camera_study.py final --version C
uv run python scripts/camera_study.py compare
uv run python scripts/camera_study.py film
```

Set `UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache` when needed. The
recipe calls existing `make_shot`, `production_lock` and Remotion render tools.
It does not change task acceptance or publish anything. Draft full-film C is a
context-review workprint, not a chosen winner. Keep the baseline as production
reference until actual continuous audiovisual review resolves the experiment.
