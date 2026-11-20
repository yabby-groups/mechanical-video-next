# Effective production contract

This is the single entry point for future production. Explicit user instructions
take precedence. Task creation pins the policy versions; resume never migrates a
historical task. The existing native Producer, handoffs, state machine, role model
routing and tools remain the only workflow.

## Policy resolution

New tasks default to `presentation_style: natural_science`. Lead with a familiar
question and use visible motion to explain its cause. Introduce technical terms
after the everyday explanation. Keep optional titles in the first three seconds
and tie labels to the relevant action. Use subtitles for narration and leave
generic production badges and chapter cards out of the default presentation.
Explain consequential model boundaries in plain language. Keep the evidence,
scope and simulation status in the existing internal records. Independent QA
checks the actual rendered words, obstructions, continuity and narration.
Use explicit `presentation_style: legacy` to reproduce older display conventions.

| Task | Effective rules |
| --- | --- |
| `production_contract_version=3` | Default for new topic-only mixed production. `science-story-v3`, media 1, visual 2, knowledge progression 1 and joint timeline 1 |
| `production_contract_version=2` | `creative-first-v2`, media 1, visual 2, knowledge progression 1 |
| `production_contract_version=1` | `production_contract=mixed-original-v1`, media 1, visual 2, knowledge progression 1, historical 120–300 s |
| Existing `media_policy_version=1` | Asset-first hybrid v1, with its own complete media manifest |
| Visual policy 2 without media policy | Native 3D core with licensed supporting footage/information animation |
| Historical 3D-only | Whole timeline native 3D and original 3D provenance; no implicit migration |

The literal route `3d` remains the compatible tool entry point. It does not label
a mixed film as 3D-only. Each native 3D shot keeps inspectable geometry, spatial
motion, camera, scene and render provenance. Licensed real mechanism footage may
support a core action only with independent exact-source continuous observation.
Information graphics, AI imagery and prescribed trajectories cannot prove a real
mechanism or a physical simulation.

Superseded rules: mandatory third-party video viewing before any work; global
blocking from a local UNKNOWN; copying a reference's full narrative/shot order;
fixed repair-round limits; automatic three-route/comparison output; static boards
passing dynamic QA; one identical studio composition for every shot. Historic
records and original policies remain available for their tasks. The 10–15 s
mechanism diagnostic is an internal checkpoint, never project acceptance.

## Science stories for new topics

The series explores everyday science, nature, materials and inventions. The
Producer owns the audience question, visual discovery, picture structure and
decision to proceed. Research owns factual support and identifies what changes
the viewer's understanding. For v3, `research.audience_decision.visual_approach`
explains the chosen visual language, a credible alternative and the reason for
the choice. Use the same question in Blueprint and bind its opening and payoff.
Color, scale, setting and media follow each subject. Preserve the protected
historical style reference and reuse a visual technique when it serves the scene.

Register a complete low-cost moving edit in the existing `diagnostic-animatic`
handoff against research. Verify by playing the edit and examining the changes
that carry the story, including alternative shots where a mechanism is difficult
to see. The draft may use representative footage, graphics, rough animation,
temporary sound or deliberate silence. Its bytes and directions precede asset
selection. The Producer owns the final Blueprint, with Editor shaping the joint
picture, action and audio timeline. Asset checks feasibility and rights. CAD and
Animation solve the spatial or mechanical problems called for by the picture.
Research remains scientific evidence. Comparative media research can inform
direction when it has a specific question to answer.

Author audience copy explicitly. Keep patent and paper IDs, product matching,
engineering parameters, evidence, debug marks and QA in production records by
default. Add a source, standard or invention name when it contributes to the story.
Explain any limitation that could change the conclusion and show credits required
by the license. A spoken line can cross cuts. Reserve time for an observation
that works through picture or sound. Use measured Neil for authored speech and
let the edit determine the duration.

The existing final preproduction `animatic-qa` reviews the exact measured dynamic
edit before formal render. V3 requires all six creative judgments to pass,
with pace, visual work and voice/sound reviewed across the whole edit. A failure
returns to visual direction. Missing sensory evidence leaves scope for draft
experiments. Scientific accuracy and source limits remain separate from creative
quality throughout. Final delivery still requires independent science, audience,
rights and audiovisual review of the exact film.

## Existing records, no duplicate truth

`task.json` owns identity/topic, policy versions, handoff pointers, stage/repair/
agent events and delivery receipt. Research owns located source records and the
concise `science.facts` ledger. Blueprint owns original narration, ordered shots,
evidence_map, knowledge progression and `direction`. The compiled configuration
is derived, hash-bound to Blueprint; measured audio determines the single time
axis. Handoffs are immutable envelopes. Animation/timeline manifests own actual
assets, rendered clips, projection tracks and audio. Full media provenance owns
the final build and lawful source intervals. QA owns independent observations;
it never changes production outputs or invents senses. References, scripts and
manifests are not parallel schedulers.

Each fact records its ID, claim, VERIFIED/UNKNOWN status, located source bindings,
scope and assumptions. Facts distinguish observed statements, derivations,
teaching approximations and unverified hypotheses. Mechanical subjects identify
one actual product/model or one specific implementation. Pure phenomena identify
their bounded mathematical/teaching model; retail identity is not fabricated.
Unknown facts restrict dependent shots only. Research covers use/context,
questions/background, mechanism variants, misconceptions, visual causality,
scientific/engineering evidence, reusable assets, and useful comparisons.

Each shot states its knowledge goal, incremental knowledge, actual observable
action, expression rationale, scale/composition/camera/light, transition link,
reuse/generation decision, narration and measured duration. `direction` adds
`why_visual`, `composition`, `lighting`, `continuity`, and `sound_intent` to the
existing visual fields. Seven suggested narrative functions (phenomenon,
contradiction, structure, mechanism, test, misconception, answer) are adaptable;
they are not a forced seven-chapter template. Repeated angles, arrows or label
reveals do not establish new knowledge.

For v2, research starts with the familiar phenomenon, the question and the visible
surprise. Select the scientific discovery and takeaway, determine what requires
3D, consider how other visuals serve the story, check material feasibility and
explain the proposed length. Record the result in research's `audience_decision`.
If the result is a parts list, change the question before CAD. Transfer the
selected question into `narrative.audience_decision` and bind distinct
`opening_shot_id` and `payoff_shot_id` in the Blueprint. Outline the visual story
before locking the dialogue and choose materials for each visual task. An
uninterrupted run of three or more interior mechanical views requires a concrete
director rationale on the first shot's `direction.continuous_mechanism_reason`.
The audience decision remains optional for v1. For
comparisons that depend on history, `data_animation` supports
`presentation: trace` with two series, a hash-bound located `basis` and a visible
model or measurement boundary in `formula`. Use the existing shot-local
keyframes. Feedback cohorts can use `feedback.comparable_observations` on imported
records with explicit duration, publication-window and observation-age tolerances
(seconds). Review the matched observations alongside their Blueprint bindings.

## Stages and recovery

For `timeline_policy_version=1`, Blueprint owns a joint `timeline`. Its
picture track uses contiguous, half-open 30 fps output intervals and source
offsets. Its action track binds native source clocks, start/end states, motion
curves and constraints. Cuts within an active action carry the same source clock.
Speech slots have a start and deadline on the output clock. Measured Neil starts
and ends are verified at 48 kHz. An overrun calls for revised wording or an
explicit edit. A silent shot states its visual purpose. Subtitle cues derive
from measured speech and can continue across a cut.

Use the existing audio_timeline entry with the topic's joint Blueprint to
prepare the continuous narration WAV and timing receipt. Bind its SHA-256 as
`measured_timeline` for compilation. Render the full dynamic animatic, review it,
then freeze the timing. The Remotion build binds the complete WAV once and each
visual source range separately. A change to words or subtitle layout invalidates
composition while keeping matching source render keys. A cut within an existing
render range may reuse its frames. A changed source clock, authored action or
required source render length needs a new motion/visual validation.

| Stage | Inputs | Existing authoritative output / next dependency |
| --- | --- | --- |
| 1 Feasibility | Question, local references/assets, resource inventory | Task + research scope, explicit unknowns |
| 2 Research | Located evidence and a consequential audience discovery | research handoff; concise facts and visual approach |
| 3 Direction | Facts, question, intended visual payoff | v3 research-bound diagnostic-animatic |
| 4 Assets and edit | Draft edit, science and lawful materials | asset-plan, optional CAD/model/motion; creative-blueprint, script, compiled config and content-qa |
| 5 Audio/animatic | Original script, supported assets | Neil measured audio/timeline, full moving animatic and independent QA |
| 6 Shots | Exact supported config, applicable production QA | Locked serial Blender stages, per-shot hashes/checks/cache |
| 7 Composition | Actual clips, projections, audio, graphics, captions | Full MP4 + source/build manifests |
| 8 Review | Exact MP4/audio, original inputs, manifests | Independent six-dimension QA + defects, covers/growth/reference reports |
| 9 Delivery | All accepted mandatory files | Actual files provided to user, then record-delivery receipt |

`continue` reconciles these existing artifacts and their dependency hashes.
Missing inputs return work to the current Producer, not a promise of unattended
background AI. UNKNOWN perception permits technically supported workprints;
it never authorizes QA_ACCEPTED or DELIVERED. Scientific/model uncertainty still
blocks the dependent depiction. Full dynamics with audio precede costly final
rendering. The original source-supported diagnostic paths remain scoped.

## Review and revisions

V2 and v3 animatic and final QA review the opening, visual tasks, pace, everyday
connection, voice and sound, and payoff. Each question has a concrete
`creative_review` observation tied to the actual film hash and interval.
Identify a replacement shot, cut or soundtrack treatment for each failure.
Continuous video or audio is required for the corresponding PASS. The existing
independent reviewer and unresolved-major-defect checks still govern HD work.
Whole-film sensory coverage remains required for final acceptance.

Six separate final dimensions: scientific accuracy; mechanical motion; visual
expression; narrative/comprehension; originality/copyright; audio/video/delivery.
Each binds exact media and located observations. Full timeline coverage and
continuous key-action viewing/listening are required. Sampled frames, ASR,
loudness, unit tests and full decode do not grant sensory acceptance. Existing
separate copyright/original-expression reports and comprehension/growth gates
remain required. All unknown capabilities remain UNKNOWN.

For formal new-contract acceptance, the same immutable QA handoff contains
`review_observations`: unique `id`, exact `media_sha256`, `reviewer_thread_id`,
one `dimension`, the current Blueprint `shot_id` and matching `knowledge_ids`,
`time_range` in seconds, `method`, `status`, concrete `observation` and
`capability_boundary`. Each dimension covers every current shot through its own
records, rather than citing one generic all-film observation for six conclusions.
Continuous methods are `continuous_video`,
`continuous_audio` or `continuous_audiovisual`; sampled frames, technical decode
and document review do not fill sensory coverage. Listening rows also bind
`audio_pcm_sha256` and `audio_pcm_format`, obtained from
`production_contract.review_media_identity` for that exact film. The format is
decoded s16le at the actual stream sample rate/channel count, not a copied AAC
container. Coverage must include the entire actual video and audio timeline,
without gaps beyond 1 ms timestamp rounding. Each quality dimension references
its records via `observation_ids`; scientific, narrative and AV conclusions
require full audiovisual coverage, mechanical/visual conclusions full video.
Copyright/originality may reference located document review in addition to the
existing separate rights checks. These records improve traceability, never prove
that someone actually watched/listened. Unsupported workprints retain UNKNOWN
and need not fabricate these acceptance records. Historical 3D-only policies are
unchanged.

An improvement claim binds previous/current actual media, technical specs,
old/new shot intervals and assets, defect/knowledge target and decoded frame
differences over the claimed interval. Different filenames, containers, hashes,
metadata or encoding alone prove no visual improvement. Deterministic comparison
can prove observable pixel change, never semantic quality; independent QA decides
whether the intended defect improved. Changes outside a declared interval do not
satisfy that interval. Reports are immutable and hash-bound to current media.
For a subject/action claim, `comparison_region: [x,y,width,height]` optionally
selects the same normalized image region in both versions, excluding caption or
credit bands. The region is recorded and revalidated; a caption-only edit outside
it fails that claim. QA must verify that the selected region contains the intended
action; the region must also match the original revision request. Full-frame
comparison remains compatible and does not distinguish text,
camera, color or geometry changes by itself. Both decoders must supply every
expected frame in the half-open interval on the normalized 30 fps clock;
fractional timestamps preserve that grid, and matching early EOF cannot establish
complete-action change.

Repair categories map to existing owners/dependencies: source/product selection
→ research; geometry → CAD; assembly/motion → CAD/Animation; camera → Animation;
graphics/captions → Editor; synchronization → Editor; render/cache → Producer;
narrative → Research/Producer; rights → Asset/Research. Wrong mechanism selection
is rejected and replaced with evidence, not endlessly patched. Preserve defect
IDs and history; unchanged failed inputs require a changed diagnostic strategy.

## Resources, style and delivery

Use existing Sol/Terra/Luna roles and at most two children by default. Dispatch
instructions: [agent-dispatch-efficiency.md](agent-dispatch-efficiency.md).
No new agents/services, no duplicate research, compact hash-bound handoffs.
Use uv, EAS/Blender, Remotion, Neil, content caches, global lock, chunk encoding,
work ≤2 GiB and free disk ≥3 GiB. Clean only verified regenerable intermediates
through existing tools. Preserve historical assets/output and failed evidence.
Keep readable single-line subtitles and shot-specific composition. Existing tasks
retain their applicable style policy. Preserve the protected reference screenshot.

V2 and v3 tasks with `timeline_policy_version=1` derive running time from the joint story
edit, with no fixed editorial floor or ceiling. Already created v2 tasks without
that field keep their original duration policy. Production disk and cache
budgets apply to all versions.
Explicit v1 and historical task instructions retain their time policies. Deliver 1920×1080/30,
H.264/AAC, both 3:4/4:3 covers, references/materials/provenance, independent QA and
production/growth reports. No padding, forced speed changes or invented metrics.
No uploads, publication or platform drafts. Level 1 = regression; Level 2 = real
topic-to-QA execution; Level 3 = actual full accepted film/package. Report each
level independently. Documentation, JSON or a short demo cannot pass Levels 2/3.

Implementation details: [science shots](science-production.md), [visual plan](visual-narrative.md),
[lawful mixed media](asset-first-media.md), [reference evidence](reference-first-contract.md),
[comprehension](product-comprehension-contract.md), [audio/length](longform-contract.md),
[covers](cover-delivery.md). This entry point resolves conflicting historical prose;
it does not weaken the executable checks for historical tasks.

## Non-mechanical scientific subjects

For `science.subject_kind=physical_phenomenon`, research identifies a bounded
`science.subject` (`id`, `name`, `scope`, `model_kind=conceptual|mathematical`).
It does not invent a retail product. Located `subject_references` bind inspected
sources and supported claims. The existing compatibility `mechanism_id` names
that specific teaching implementation, never a claim of a retail mechanism.
Blueprint derives `subject_kind`, `subject_identity`, `subject_references` and
`subject_opening` from that research. Its existing comprehension rows connect
phenomenon, conditions, model, causal test and return to the opening question.
The compiled config/build/manifest preserve the subject identity and policy.
Source/model/motion and full sensory acceptance stay strict; a named conceptual
subject is not evidence of a physical simulation. Legacy product tasks retain
their original product checks. This adds no second scheduler or fact database.
