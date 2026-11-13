# Unified visual evidence preprocessing

## Audited paths

| Path | Existing behavior | Integration |
|---|---|---|
| workflow.py / role handoffs | source image paths, immutable JSON | compressed bounded visual_evidence in envelope, production payload untouched; rejects inline image data |
| scripts/produce.py / Blender keys | retained original PNG frames, content caches | qa-images.json for selected existing keyframes, on cache hits too |
| scripts/layered.py | three original key PNGs | shared make_shot wrapper creates compressed evidence |
| scripts/style_preview.py | calls make_shot | inherits shared evidence generation |
| scripts/cad_preview.py / cad.py | geometry/config then existing renderer | numerical geometry unchanged; shared renderer evidence and CLI for external CAD snapshots |
| multiroute.py | comparison preview.jpg | compressed preview in report, corrupt/missing image remains UNKNOWN |
| covers.py | formal PNG candidates and two final PNGs | separate cover previews in report, originals unchanged |
| viral.py / reference_library.py | observations and source bindings | shared CLI for downloaded screenshots/video event frames; role instructions require cache paths |
| .codex/agents and .agents/skills | agent-directed tool reads | all roles use same API and cache; no role-specific compression |

No existing base64 image transport implementation was found in the audited Python entry points. The host image tool is external to this repository: these changes cannot intercept arbitrary manual tool calls or enforce context deduplication across independent host sessions. Handoffs use paths; they do not embed pixels. Cache content deduplication is distinct from actual image-read accounting.

## Usage

`uv run python -m mechanical_video_next.qa_images IMAGE --sheet`

`uv run python -m mechanical_video_next.qa_images VIDEO --times 0 12.5 30 45 --sheet`

`uv run python -m mechanical_video_next.qa_images COVER --cover`

`uv run python -m mechanical_video_next.qa_images IMAGE --crop 100 100 600 450`

Crop coordinates use EXIF-oriented original pixels. The tool never silently substitutes a full-resolution image. Overview maximum 1024px, sheet 1280px, cover 1200px, crop 1600px. Encoding starts at quality 80 and decreases to 35 under a 300000-byte budget; impossible budgets fail and request a crop. This limit is a byte budget, not a guarantee of readable text or contact detail. RGB conversion composites transparency onto white. Production inputs are never overwritten. Crop is explicitly bounded and never stretches geometry.

Every round permits four frames and one sheet; contact sheets contain at most sixteen representative images. For long media the Producer must choose chapter/action events, then make additional bounded rounds as needed. This does not establish continuous review. Deterministic full decode, timing/codec checks and CAD/animation motion checks remain in the existing pipeline. No static-image tool grants PASS.

`record_reads` records successful host reads when called by the consumer, not preparation attempts. Byte totals, dimensions and formats are observable; visual token usage is unavailable. Identical cache paths do not prove the host avoided resending an image.

## Real validation

Run `uv run python scripts/validate_qa_images.py`; detailed source and output hashes, sizes and timings are in work/qa-images/validation.json. The measured run used six existing route/CAD/cover images: 1276147 original bytes, 85308 compressed bytes, 100% repeat-cache hits. Original files unchanged. Initial six-image preparation took approximately 0.385 seconds across cold/warm runs; timings are cache-state dependent; use the JSON for the latest run. No production video rerender, voice change or source resolution change occurred.

Two actual host reads used WebP only (actual-reads.jsonl): overview plus title crop. The Chinese title was legible in the crop; fine mechanical contact remains UNKNOWN. This is not scientific acceptance or comprehensive continuous viewing. The source JPEG/PNG images and final video bytes are preserved. Tests exercise actual project renders and a real final video, not only synthetic fixtures.

## Limits and follow-up

Unreadable-region detection and semantic selection of motion events require agent judgment: the API supplies bounded crops, not a fabricated readability classifier. A future host integration could make successful read logging mandatory and enforce cross-session image deduplication. Missing or insufficient evidence stays UNKNOWN. Existing historical QA is not retroactively rewritten. The shell CLI returns evidence packets; it cannot force external CAD viewers/browser screenshot tools to render compressed pixels before the agent sees them. Export their screenshots and pass through this entry before further review.
