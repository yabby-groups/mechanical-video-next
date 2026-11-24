# Configuration boundary

Git tracks shared narration profiles and `visual-reference.json` here. All other
files in this directory are local video-production inputs by default, including
shot plans and diagnostic parameters.

Per-video CAD scripts, parameters, exports, inventories, provenance and validation
records in `assets/assemblies/`, and source media in `assets/media/`, stay local.
Index-only removal keeps local files and does not rewrite historical commits.
Back up production inputs separately: a fresh clone contains tools, not previous
video projects.

For new videos, keep authored inputs with the episode and run the entry point
documented in the [project README](../README.md). Historical ledger tasks retain
their local configuration, assembly and plan paths. The nail-clipper adapter uses
its corresponding historical local inputs.

`tests/fixtures/production/` contains regression snapshots only, not production
plans or accepted scientific/media evidence. The acceptance regression harness
uses these snapshots. Real production requires task-specific research, assets,
and actual review of the rendered film.
