# Configuration boundary

Git tracks shared narration profiles and `visual-reference.json` here. All other
files in this directory are local video-production inputs by default, including
shot plans and diagnostic parameters.

Per-video CAD scripts, parameters, exports, inventories, provenance and validation
records in `assets/assemblies/`, and source media in `assets/media/`, stay local.
Index-only removal keeps local files and does not rewrite historical commits.
Back up production inputs separately: a fresh clone contains tools, not previous
video projects.

For new videos, keep inputs under `output/tasks/<task-id>/` and pass explicit
configuration/assembly/plan paths. Existing local paths remain usable. Historical
commands in the main README require their corresponding local inputs. The default
nail-clipper plan is a historical local adapter, not a bundled general-purpose plan.

`tests/fixtures/production/` contains regression snapshots only, not production
plans or accepted scientific/media evidence. The acceptance regression harness
uses these snapshots. Real production requires task-specific research, assets,
configuration and exact-media QA.
