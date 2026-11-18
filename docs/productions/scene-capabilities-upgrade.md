# Reusable science scene capabilities

2026-11-18. This extends the existing Blender/EAS shot adapter. It adds no
renderer, physics solver, production route or acceptance system. Existing
unstaged work in `blender/scene.py` is retained. Scope: configuration validation,
scene animation and numerical tests; no render or perceptual acceptance is
claimed by these tests.

| Requested view/action | Existing implementation or addition |
| --- | --- |
| Overall / explode / assemble | Existing EAS and `overall`, `explode`, `assemble`; imported mechanisms use explicit source-reviewed `exploded_view` poses |
| Section | Existing `cutaway` + Boolean `section_plane`, applied after deformation |
| Transparency | Added per-object `science.opacity_tracks`, preserving the underlying approved shader and copying material slots |
| Isolation / micro | Existing `visible_parts`, `micro_zoom`, focus boxes and authored camera path |
| Follow / trajectory | Existing `camera_follow`, evaluated-anchor `motion_trace`, vertex-following guides and final-camera label projection |
| Speed / time compression | Added one monotone `science.time_map` shared by every rigid and mesh channel in a data-driven shot; supports holds and speed changes |
| Flexible winding | Existing prescribed `mesh_tracks`; added `centerline_strip` authoring helper for consistent ribbon vertices and faces from supplied winding paths |
| Constraints | Existing registered mechanism controls and per-frame mesh alignment; added evaluated distance-range assertions, never a generic joint solver |
| Fields / state | Existing authored 3D field/flow curves and data-driven `state_transition`; no field integration or material solver |
| Comparison | Existing authored paired scenes, same-reference camera poses and Remotion comparison graphics; no new split-screen engine or automatic mechanism duplication |

## Parameter additions

Use these fields within a shot's existing `science` version 1 block, alongside
its located, hash-bound `basis`, `scope`, and conceptual/mathematical mode.
Time mapping requires `driver: data_tracks` and the existing source-reviewed
`tracks` / `mesh_tracks`.

```json
{
  "driver": "data_tracks",
  "time_map": [[0, 0], [0.25, 0.5], [0.5, 0.5], [1, 1]],
  "opacity_tracks": [
    {"object": "Cover", "keys": [[0, 1], [0.5, 0.15], [1, 1]]}
  ],
  "constraints": [
    {
      "kind": "distance",
      "points": [
        {"object": "Pivot", "local": [0, 0, 0]},
        {"object": "Arm", "local": [0, 0, 0]}
      ],
      "range": [0.02, 0.02],
      "tolerance": 0.000001
    }
  ]
}
```

`time_map` pairs mean `[screen_progress, source_progress]`, both normalized.
Screen time strictly increases; source time never decreases and remains in the
original validated interval. Both endpoints are mandatory. One map composes
with every existing rigid channel and mesh shape-key weight, preserving source
corners and raw quaternion component interpolation. This is exact piecewise
linear F-curve composition, not interpolating a new guessed pose. Narration,
camera, guides and opacity retain their screen clock; a guide that follows an
object reads its evaluated retimed pose. This clock does not retime EAS or the
built-in procedural `asset_motion` driver. Configure those using their existing
controls or use evidence-backed data tracks.

Opacity keys use `[screen_progress, opacity]`. Values are bounded 0–1 and have
ordered endpoints. Each addressed object must remain in the visible assembly
inventory and have connected node-based surface materials. Materials are copied
per object; a transparent-shader mix wraps the existing material after the
approved studio style is applied. Opaque value 1 retains its surface shader;
no global material or style preset is edited. Transparency remains editorial,
not measured optical transmission. Occlusion, shadows and readability still
need actual preview QA.

Distance constraints accept two evaluated local point references, optionally
with source mesh `vertex` indices, a nonnegative inclusive range and tolerance
in scene units. All output frames are checked and failure raises before render.
Vertex references require stable topology without modifiers; local object
points remain usable after a section modifier. `checks.json` records frame
coverage and observed extrema. This does not establish contact, force,
continuous subframe safety or physical feasibility.

For flexible material authoring:

```python
from mechanical_video_next.science_shots import centerline_strip

mesh = centerline_strip(source_centerline, width=0.01, normal=[0, 0, 1])
# mesh['vertices'] and mesh['faces'] use the existing source-mesh asset format.
# Repeated source poses with identical sample order/count provide mesh_tracks.
```

This helper creates a zero-thickness, constant-width strip around supplied 3D
centerline samples. It rejects degenerate samples or a tangent parallel to the
reference normal. It does not enforce length, tension, thickness, contact,
collision or winding conservation. Such claims need source evidence and
separate numeric/visual verification; a supplied path is not a simulation.

## Validation and boundaries

`uv run python -m unittest tests.test_science_motion tests.test_science_shots`
passes 14 tests. New tests cover shared-clock numerical equivalence at 101
samples, preserved corners and holds, real retime adapter behavior with legacy
and layered F-curves, simultaneous rigid/mesh timing, malformed maps and
opacity, part scoping, ribbon winding width/topology, and evaluated-frame
distance checks including a failing sixth frame. Scene modules compile.

The added features are opt-in. Geometry, materials, cameras, asset source files
and key computation for existing shots are not rewritten. Existing science
source hashes invalidate affected cached scenes; editorial labels/audio remain
outside 3D shot keys. The legacy scene-source equivalence allowance must remain
an exact hash match and must not bless science paths as visually equivalent.

Blender API execution and rendered appearance require Producer validation under
the existing global lock. Tests with import stubs validate adapter logic, not
Blender availability, shader enum compatibility or rendered quality. Full
continuous viewing/listening, independent science/comprehension QA and formal
film delivery remain separate. Requested agent routing was `gpt-6.1-sol/high`;
observed model, effort, token and cost telemetry were unavailable (`null`).
