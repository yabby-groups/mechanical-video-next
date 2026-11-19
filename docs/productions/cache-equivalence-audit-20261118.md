# Legacy scene cache identity audit

The prior exact-current-source allowance had drifted before this upgrade. It
therefore failed closed and invalidated ordinary legacy scene cache identities.
The pinned media-equivalent source is commit
`86bd9b60771afaef5fe440f4bce9de3d23413ae8`, SHA256
`5cedf85ee1a03567b94ee2a18f8ac1836b16b9aeb6d40e39cc66421478603faa`.

AST comparison found only three changed existing functions: `verify_mesh_tracks`,
`prepare_data_tracks`, `render_shot`; no existing function was removed. The new
writing-desk helper is opt-in. Reviewed default-path differences:

- Retiming and its report field execute only with `science.time_map`.
- Science preparation, motion, opacity, constraints, camera paths, guides and
  projections execute only when `science` is present.
- The subsequent `science.camera_clip` repair is inside that same guarded
  branch and requires the explicit option. It changes no legacy path; science
  source hashes still invalidate affected render keys. A real saved operation
  scene at frame 106 reproduced coating/text depth conflicts with clipping
  0.1–1000 and removed them at 29–31 without altering geometry. This frame is
  diagnostic evidence, not acceptance of a film.
- Context props execute only with an explicit `context` declaration.
- Legacy section cutting retains cube size 1; adaptive cutting is science-only.
- The extra camera branch names the new `camera_follow` template; prior templates
  retain their original frame samples, camera, geometry and render behavior.
- Conditional motion/projection report values retain the old values when the
  science/context options are absent.

The exact current source hash is now pinned in the existing equivalence file.
Any subsequent edit fails closed again. Science shot keys already additionally
hash actual scene/science sources with `equivalents=False`; new fields and actual
asset configuration remain in each content key. No cache blob or historical
asset/media was rewritten or deleted by this update.

This is a source-path/cache audit, not continuous visual acceptance. Historical
stapler-specific frozen configuration/assembly are absent in this tools checkout;
its frozen style integration cannot be rerun here. The approved screenshot and
immutable source reference remain separately hash-checked. Do not update the
historical style-lock hashes to manufacture a PASS for the new renderer.

The producer also has a separate storage-only equivalence pin. The exact
pre-change producer source was reconstructed and verified against the hash
recorded when the completed MP4 exceeded the work budget. Props construction,
Remotion sources and render flags are unchanged; only the output destination
and verified cache retention differ. Versioned mixed-original exports stay
under output with hash-bound cache references. The existing cleaner removes a
cache duplicate only after its completion hash equals the protected export and
the export fully decodes. Historical tasks retain the original destination.
This preserves composition identity without treating encoding or metadata as
a visual improvement.
