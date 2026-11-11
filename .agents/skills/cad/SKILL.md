---
name: cad
description: STEP-first parameterized build123d/OpenCASCADE mechanical solids and measured CAD validation.
---

# CAD generation

User-requested origin: https://github.com/yabby-groups/mechanical-video/tree/main/.agents/skills/cad . The retrieved upstream SKILL.md matches the legacy local version, SHA256 da533e7b5ac1b8e8d5e2616f5e8e52e2b95b7099984adf0831c2f1f7e46d9d6b. This focused adapter retains STEP-first principles without migrating its architecture.

Read config/zipper-cad-parameters.json. Generate via scripts/cad_generate.py using a Python environment with build123d and trimesh. Source is mechanical_video_next/cad.py. Edit source or parameters, never derived STEP/GLB/meshes. CAD uses mm; rendering uses explicit mm-to-m conversion. Keep labeled independent solids, local frames, named attachment datums, and STEP as the primary artifact.

Require positive-volume valid solids, STEP roundtrip count, initial and sampled dynamic native solid intersections, and a closed transverse retaining probe. Mesh screenshots do not prove clearance. Preserve failed evidence and persistent defect keys. At most two measured repair rounds per issue; stop without measurable improvement. Do not infer physics, manufacturability, scientific, listening, or visual acceptance from technical checks. Missing z-retention wings remain UNKNOWN.

Blender runs belong to Producer's globally serialized stage. Report units, assumptions, exact checks and integration files. Do not upload or publish.
