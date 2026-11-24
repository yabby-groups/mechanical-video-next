# 3D-only production contract (2026-11-16)

Archived instructions for existing 3D-only ledgers. New episodes use the [production contract](production-contract.md). The topic command below records the former entry point.

New tasks always use `three_d_policy_version=1`, `requested_routes=["3d"]`,
`render_route="3d"`. `produce`, `select-route`, `extend-routes`, blueprint compilation,
`stage`, the renderer and route-plan execution reject retired representations.
`2d`, `2.5d`, `all`, illustrated subjects and layered image mechanics cannot be
production fallbacks. Existing historical ledgers, media and cache data remain readable.
`multiroute` is a historical module name, not permission to make other routes.

```sh
uv run python -m mechanical_video_next produce --topic 机械名称
uv run python -m mechanical_video_next migrate-3d TASK --reason 'Explicit user-authorized 3D-only migration'
```

Migration is explicit and idempotent, refuses completed/delivered history, and saves
previous scope/route records before changing the undelivered task in place. It retains
research, paid Neil audio, CAD, logs, hashes and valid caches. Retired route records
have `schedule_production=false` and `retired_from_delivery=true`.

Prefer lawful, matching 3D assemblies; when unavailable, use reliable product and
mechanism sources to make a scoped teaching model. Do not infer internals from an
appearance photo. Patents establish particular embodiments, not retail-brand identity.
Real product appearance/use and internal correspondence remain separate evidence gates.

## Actual render provenance

`scripts/produce.py` uses `blender/render_with_provenance.py`, a thin wrapper around
the existing locked `blender/scene.py`. It saves the fully prepared camera, geometry,
materials and keyframed scene in each shot cache as `frames/scene.blend`. It does not
change the visual/geometry implementation to satisfy a hash test. Existing asset caches
retain their keys; new shot keys bind the provenance wrapper. Historical caches remain
intact and can be explicitly audited against reconstructed scenes.

`3d-provenance.json` records every included shot's saved scene binding, model asset
bindings/origins, product/mechanical references, motion configuration, render engine,
frame range, raw rendered output and witness frames. Its `build` holds a contiguous
frame-based timeline of those rendered outputs, exact Neil WAV, ASS subtitles and fonts.
Its `media` binds the actual complete final MP4. Camera and evaluated spatial-motion
measurements are produced from the saved scenes by the verifier and retained in its report.

```sh
uv run python -m mechanical_video_next.provenance TASK/3d-provenance.json \
  --report TASK/qa/3d-provenance.actual-render.json
```

The verifier holds the global production lock. It opens actual scenes in Blender,
checks the visible `Assembly` collection and camera, rejects wholly planar mechanical
subjects and image-textured mechanical planes, and measures geometry and evaluated
motion. Thin real sheet parts are allowed within real assemblies; affine geometry,
not a guessed minimum thickness, determines spatial structure. Structural detail shots
may be static; action shots must show measured spatial motion. Structural details do
not establish deformation, force, or contact simulation.

It rerenders at least three witness frames per shot and compares the mechanical
region against the raw encoded clip, then replays the complete restricted composition
and compares all decoded video/audio against the actual MP4. Only verified rendered
segments plus subtitle text/fonts and narration enter this build; arbitrary commands,
image mechanics and unbound replacement clips are not executed. This proves sampled
scene-to-render consistency and full raw-to-final build consistency, not every-frame
physical truth or independently observed comprehension.

A model file, extension, `3d` field, screenshot, ffprobe result or successful render
alone cannot pass delivery. Source/model mechanical correctness, product identity,
continuous viewing/listening, phone subtitles, approved style, and the five growth
objectives remain independent exact-media QA requirements. FAIL/UNKNOWN cannot be
converted to acceptance. A 3D failure triggers scoped diagnosis/repair, never fallback.

## Delivery and tests

Deliver one complete 1920×1080/30fps 3D MP4 with Neil, both 3:4 and 4:3 covers,
real-product/mechanical references, provenance, mechanical authenticity and viewer
comprehension QA, and retention/like/save/comment/follow report. Comparison, 2D and
2.5D movies are not delivery dependencies. Files precede `record-delivery`; no upload,
publication or platform draft is authorized.

```sh
uv run python -m unittest tests.test_three_d_only -v
RUN_BLENDER_TESTS=1 uv run python -m unittest tests.test_three_d_only.ThreeDOnlyTests.test_blender -v
uv run python -m unittest discover -s tests
```

The Blender integration creates actual solid/moving and perspective-plane scenes,
renders and encodes both, adds a subtitle overlay to the genuine 3D film, reopens and
rerenders the saved scene, and rejects both the planar scene and a substituted final
film. `MVN_BLENDER_FIXTURE_DIR` can retain those exact artifacts for audit. Run Blender
serially with production. No fake reviewer, semantic acceptance, growth metric or
measured savings may be inferred from these engineering tests.
