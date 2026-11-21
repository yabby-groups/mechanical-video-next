# Effective production contract

Mechanical Video Next is the production system for the single Douyin account
「君哥拆机器」.

> 从生活中有意思的机械问题出发，用真实运动、三维拆解和有设计感的镜头，让观众亲眼看到机械原理是怎样发生的。

This contract governs future production. Explicit user instructions take precedence.
Task creation pins the policy versions and resume retains the historical policy.
The existing native Producer, handoffs, state machine, role routing and tools serve
the account directly.

## Policy resolution

New tasks default to `presentation_style: natural_science`. Let the subject
determine the opening. Use ordinary language and tie labels to the relevant
action. Reserve subtitles for narration and keep production notes in the ledger.
Explain consequential model boundaries in plain language. Keep the evidence,
scope and simulation status in the existing internal records. Independent QA
checks the actual rendered words, obstructions, continuity and narration.
Use explicit `presentation_style: legacy` to reproduce older display conventions.

### Film integrity on new Producer-directed tasks

The task pins `film_integrity_version: 1` and requires that version in the
Blueprint's existing `timeline`. Historical task ledgers retain their pinned
rules. Keep source and output ranges in half-open 30 fps frames. Each necessary
mechanical event uses an existing `timeline.actions` ID and output window.
Add `source_end_frame` alongside `source_start_frame`. Record `input`,
`direction`, `transmission`, `intermediate_state` and `contact` alongside the
existing endpoints, curve and constraints. Bind `evidence` with path, SHA-256
and source position. Use `knowledge_id` to connect the event to the shot and its
verified explanation. A core mechanical shot carries one or more `action_views`.

For Blender views, record `director.action_program_digest(base_shot)` in the
event's `shot_programs` keyed by shot ID. It binds the driver, tracks, contact
constraints, rotation interpolation and native frame count. Use a single action
ID and the same native program and source clock for cuts that continue one motion. For an observed footage
event, bind the exact `footage` record and the matching source bytes. A locked
action preserves its source span at 1:1 in the edit. Use camera and visual
changes that preserve the action and keep decisive contact and state changes
visible. Explicitly cue any replay or change of example in the actual film.

In `narrative.moments` also bind `scientific_explanation` and `action_result`.
Each moment carries `knowledge_id` and one or more of `mechanical_event_id`,
`narration_segment_id` or `visual_evidence`. The causal reveal and action result
of a mechanical film use a mechanical event. The same beat or shot may carry
several moments. Measure Neil PCM, then revise the timing until all utterances
fit. Author the required action and story before deciding the film's duration.

The existing composition and QA gate check the full decoded frame count, picture timestamps and
compare the encoded audio with the measured PCM or verified mix, including the
last utterance. Low-resolution mechanical previews preserve 30 fps. Existing
continuous final QA observations use `mechanical_event_ids` with a concrete
`source_comparison`, and `story_moment_ids` for narrative observations. Together
they cover each bound event and moment on the exact MP4. The independent workprint
review uses those same event and story observation fields before full-resolution rendering.
Timecode and waveform
checks establish technical coverage. Motion, contact visibility and the clarity
of the final explanation require actual review. Record unavailable sensory
observations as UNKNOWN.

| Task | Effective rules |
| --- | --- |
| `production_contract_version=6`, `production_method=producer-directed`, `producer_direction_version=1` | Default for new topic-only mixed production. Use the audience premise, shot direction and moving workprint review below |
| Earlier `production_method=producer-directed` tasks | Resume from the recorded preview and reference workflow |
| Other `production_contract_version=6` tasks | Original `mechanical-story-v6` candidate workflow. `--production-contract 6` explicitly selects this path |
| `production_contract_version=5` | `mechanical-story-v5` applies Science Discovery to the account's mechanical stories and retains v4's timeline, media, visual and evidence capabilities |
| `production_contract_version=4` | `science-discovery-v4` preserves the original story exploration and documented technology subject scope, with media 1, visual 2, knowledge progression 1 and joint timeline 1 |
| `production_contract_version=3` | `science-story-v3`, media 1, visual 2, knowledge progression 1 and joint timeline 1 |
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

## Producer-directed production

New topic-only tasks start with `research/search-plan.json` and the
`viral-analysis` continuation action. Check the existing library for matching
viewing evidence first. Reuse sufficient, relevant observations with current
hashes. Cached engagement is historical. When there are gaps, look for the
same machine on Douyin, Xiaohongshu, Bilibili and YouTube, then consider similar
mechanisms or visual techniques. If playback is unavailable, switch sources.
Choose a small useful set based on observed clarity, visual interest, progression
and Blender/EAS feasibility. Use verified public engagement as one signal and
evaluate retention only from retention data.

Play the reference where possible. Describe what first earns attention, how new
discoveries and the payoff arrive, and how framing, camera motion, teardown,
cutaways, scale and narration support them. Examine relevant history, uses and
design choices where observed. Record what transfers, what the current tools can
execute, what requires original production, and any limits on lawful reuse.
Write original scripts and direct original shot sequences. Treat public footage
and music as `REFERENCE_ONLY` by default and verify rights for any media reuse.

The Producer can do this work directly or ask the existing ViralResearch role to
investigate a specific viewing gap after checking the cache and active assignments.
Either role can register `viral-analysis`. A valid handoff completes this step
on resume. Register a dated limitation and proceed to the story when accessible
sources are exhausted. Record reusable public observations in the existing
library with `uv run python -m mechanical_video_next.reference_library ingest`.

- The handoff takes `task_id`, `topic`, ISO `observed_at` with timezone,
  `candidates` and `selected_ids`. If selection is empty, `limitation` records
  the source attempts and why they yielded no applicable observation.
- Each candidate takes an `id`, `observed_at`, original `url` or hashed
  `source_files`, and `viewing.status`. Use `FULL_VIDEO_VIEWED` with
  `duration_seconds`, `viewing.continuous_visual=true` and equal
  `viewing.covered_seconds` for actual continuous start-to-finish observation.
  Use `PARTIAL_VIDEO_VIEWED` with `viewing.time_ranges` in seconds for actual
  observed segments. Both take `viewing.evidence` entries with `path` and
  `sha256` for the dated viewing record. Use `SCREENSHOTS_ONLY`, `PAGE_ONLY` or
  `VIDEO_NOT_VIEWED` for those access levels. Supply `viewing.limitation` for
  incomplete viewing. Record audio and other unobserved details as unknown.
- Selected videos need timecoded `observations` strings and a
  `transfer_rationale`. Record public counts only with the matching fields in
  `metrics_evidence` and a hashed page capture in candidate `evidence`. Missing
  counts can be null. Media rights follow the existing asset workflow.
- The Producer implements useful techniques from the selection in the actual Blueprint
  shots, for example a camera move or a staged reveal suited to this machine.
  Each existing `reference_principles` row uses `reference_id`, `principle`,
  `production_requirement` for the original execution decision, and `shot_ids`.
  The Blueprint declares `viral-analysis` alongside `research` and `asset-plan`
  as immutable handoff dependencies. The principles may be empty when the
  research records a limitation. Existing tasks without a search plan resume
  with their recorded dependencies.
- For direction version 1, observed candidates may add `techniques`. Each row has
  `id`, `source_range` in seconds inside one actually viewed span, `visual_method`,
  `use_condition`, `viewer_effect` and `implementation`. Applied
  `reference_principles` add `technique_id` and `expected_observable_effect`.
  The existing library preserves these records and the handoff verifies the
  source-to-shot link. Choose methods that serve a concrete observation.

Research the real machine and choose a complete story before matching assets.
Follow the history, use, people and design choices that matter to that story.
The Producer owns the visual story, narration and edit. The existing roles
provide evidence, modeling, animation and editing help.
Build the recognizable 君哥拆机器 identity around teardown and mechanical discovery.
Connect episodes when the machines share a question or design choice. Give viewers
a reason to return through what each episode reveals. Keep actual viewing,
likes and follows as separate measures in later post-publication review.

For direction version 1, use `research.audience_decision` to record
`question`, `daily_context`, `design_tension`, `visible_test`,
`viewer_takeaway` and `selection_rationale`. Consider the apparently simpler
design and make a separate feasibility judgment. In `narrative.moments` bind
`opening`, `first_discovery`, `causal_reveal` and `payoff` to a `shot_id`,
absolute 30 fps half-open `start_frame` and `end_frame`, and a concrete
`observable`. A shot may carry several moments. Choose the story structure
and length for the subject. Each shot's `direction` states `why_visual`,
`composition`, `lighting`, `continuity` and `sound_intent`. Merge repetition,
leave inspection time for mechanical changes, and cue narration and lawful
sound to observed action. Use the existing visual direction and camera notes.

Include the task's `production_method` and contract in research and Blueprint.
Use `science.facts` and the reference records for evidence. Where the machine
appears in motion, verify the exact implementation and depicted constraints.
Bind the question, answer, shots, measured Neil Joint Timeline and compiled
config in the Blueprint. Use `asset-plan`, the applicable mechanical and
reference checks, `content-qa` and feasibility to establish render readiness.
Use `advance` and `stage`, verify key actions and watch the low-cost full
preview before composing the final MP4. `animation-manifest` binds the preview
and `timeline` binds the final edit.

New tasks with `creative_direction_version=1` record three editorial treatments in
the research handoff and carry the chosen treatment into the Blueprint. Shot
strategy and audio decisions compile into the existing renderer and joint timeline.
See [Creative direction](creative-direction.md). The Producer reviews the whole
moving workprint with Neil audio before final rendering.
Use the existing `preview-qa` handoff for independent timecoded
`creative_review` before the final stage. Report opening, visual tasks, pace,
everyday connection, voice and sound, and payoff. For each applied reference
and shot, add `reference_effects` with `reference_id`, `technique_id`,
`shot_id`, `time_range` in the edited shot, `media_sha256`, `status`,
`method` and `observation`. Explain UNKNOWN in `limitation`. Reserve PASS
for the corresponding continuous observation. Use existing defects for
actionable issues and limit renders to affected shots. Creative
UNKNOWN can accompany a technically and scientifically sound workprint.
`audience-review` remains a manual review of a finished film.
Independent `final-qa` reviews the exact film. New
Producer-directed tasks pin the verified Neil audio policy at creation.
The existing quality dimensions cover advice on the story as well as science,
motion and audiovisual quality. Preserve separate rights checks and record
unavailable sensory evidence as UNKNOWN. Deliver the film, both covers,
provenance and the existing QA and production reports.

## Historical story discovery and creative review

Use the original pinned workflows for the discovery and preproduction approval
steps below. Producer-directed tasks use the section above.

For v6, compare distinct stories on the same everyday object before investigating
specific production paths. Describe who would care in actual use, which effect
or design choice creates tension, what viewers could see, what they would learn,
and whether the case earns an episode. Explain what the leading story offers
over its strongest creative alternative. A well-evidenced detail can support
another story. It can lead its own episode when its use, tension and visible
discovery sustain one.

The Producer registers this order in the existing `research` handoff with
`story_exploration.phase=EDITORIAL` and no selection. Limited source reading
can establish that a premise is worth investigating. Technical dispositions
belong in the next immutable research revision, `phase=DECISION`. Give the
scientific and production checks their own findings and located sources.
Investigate a plausible source, controlled observation, asset or low-cost
depiction before passing over a stronger candidate. Missing local CAD is a
reason to investigate, while concrete production gaps can defer an otherwise
promising story. The recorded order is an initial editorial judgment. The
Producer compares the findings and gives the final reason for selecting an
evidenced, realizable standalone story or deferring the topic. Document which
ideas serve as supporting scenes.

Register the complete moving edit in `diagnostic-animatic`. The existing QA
reviewer evaluates the exact edit, including whether the audience question,
design discovery and payoff survive the transition from research to picture.
Compare with the strongest alternative. Tie a creative failure to an observed
section and a concrete change. An isolated obstruction or confusing cut goes
to its production owner. A failed premise or failed progression returns to
the current story shortlist. The ledger preserves the prior media and review
and retires dependent approvals. Independent continuous viewing is required
for a creative PASS. Sampled frames may support specific findings, and the
remaining sensory judgment stays UNKNOWN.

From v5, start with machines, tools, mechanical devices, structures and everyday objects
with a consequential mechanical design. A bare topic is enough to begin. Discover
what people needed, which choice solved it, what it cost, how it was used and why
someone might change it. A law of optics, chemistry or astronomy may explain a
machine, measuring instrument or application. Standalone phenomena fall outside
the default editorial scope. For an off-domain prompt, pursue a faithful, sourced
mechanical question when one exists. Otherwise record the scope mismatch.

Research makes a low-cost pass through relevant angles: documented stories,
original needs, design constraints and materials, working science, clever
details, tradeoffs, alternatives, uses, cross-domain connections, evolution,
failures, counterfactuals or experiments, and future directions. Seek the people
and conditions behind a design. Prefer archival and museum records for history,
experiments and peer-reviewed work for science, and original product or
engineering documentation for scope. Record where the evidence comes from.

From v4, use the existing research handoff's `story_exploration.angles` for
findings and evidence gaps and `candidates` for a bounded set of plausible audience
questions. V4 and v5 retain the four-candidate limit. Each candidate has an ID, angle, visible test, decision reason and
fact IDs where available. A single viable candidate includes a shortlist limit.
In v5, each candidate's `mechanical_focus` names the device and the design choice
or behavior the story explains. V5 research accepts `mechanical_implementation`
or mechanically anchored `documented_technology` as the subject. Facts may use
any relevant science. Evidence and editorial judgment establish actual relevance.
Deepen only the promising directions. Compare curiosity, story and knowledge
value, design insight, visual payoff, difficulty, daily relevance, originality,
source confidence and cost. The Producer selects one direction, records why
the others are deferred and keeps promising questions for later episodes. Identify
the exact implementation, production assets, shots and measured voice from the
selected story. Existing models can then be checked for a genuine match.
Judgment and evidence decide. The selected ID links the research, the moving
draft's `story_id`, and Blueprint's `narrative.story_id`.

A story may center on a phenomenon, invention, design choice, tradeoff,
technical change, experiment, real application, failure, surprising finding
or a combination. Keep one main line. Compare alternatives under stated
conditions. Distinguish shared principles, similar methods, visual analogy
and documented lineage. Separate deployed technology, research and future
hypotheses. V4 adds historical and scientific fact kinds plus unverified
story leads and legends to the existing ledger. Derivations and approximations
retain assumptions. A patent alone cannot establish sole invention or its date.

Three-dimensional disassembly, cutaways and motion are the account's core visual
techniques. Use them to reveal the consequential design where they earn the shot.
Real use, archives and original graphics can carry context, history and comparisons.
The Producer owns the audience question, visual discovery, picture structure and
decision to proceed. Research owns factual support and identifies what changes
the viewer's understanding. ViralResearch investigates audience interest when
it informs a concrete direction choice. For v3 and later,
`research.audience_decision.visual_approach`
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

### Picture direction before production

Discovery tasks from v4 pin `visual_direction_version=1` at creation. The existing
diagnostic edit plan records the main scenes across the whole picture. A story
scene shows an event, person, setting or phenomenon. An explanatory scene
reveals the process or comparison necessary to understand that observation.
When moving between them, preserve something the audience can recognize, such
as an object, viewpoint, motion, result or the conditions of an experiment.
The length and mix of these scenes follow the individual story.

Record each scene's event, subject, setting, visible change or meaningful hold,
point of attention, camera, transition, purpose and located source. Choose the
visual treatment before testing tool availability. Record the intended and
realized medium. If a renderer or asset path fails, try a treatment that can
show the intended observation. Give the reason for a substitution and record a
`capability_gap` when an intended action or real observation is missing.
Historic reconstructions and modeled observations carry their actual provenance.

Use the existing `diagnostic-qa` handoff to assess the exact low-cost picture
before formal Neil measurement, Blueprint freeze or formal rendering. Look for
shots that rely on subtitles to advance, repeated viewpoints without new
meaning, missing real-world context and explanations that break the viewer's
connection to an observed result. A static hold can provide useful observation
time. Keep `visual_story_review` UNKNOWN when continuous viewing is unavailable
and identify a concrete scene or edit change on FAIL. Formal production requires
continuous picture review and resolution of visual capability gaps. Diagnostic
experiments can proceed with an unresolved review. The later measured animatic
retains its full picture and sound checks.

Author audience copy explicitly. Keep patent and paper IDs, product matching,
engineering parameters, evidence, debug marks and QA in production records by
default. Add a source, standard or invention name when it contributes to the story.
Explain any limitation that could change the conclusion and show credits required
by the license. A spoken line can cross cuts. Reserve time for an observation
that works through picture or sound. Use measured Neil for authored speech and
let the edit determine the duration.

The existing final preproduction `animatic-qa` reviews the exact measured dynamic
edit before formal render. V3 and later require all six creative judgments to pass,
with pace, visual work and voice/sound reviewed across the whole edit. A failure
returns to visual direction. Missing sensory evidence leaves scope for draft
experiments. Scientific accuracy and source limits remain separate from creative
quality throughout. Creative review checks how the chosen direction earns its
runtime, what discovery the pictures carry and where an explanation stalls.
Final delivery still requires independent science, audience,
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
`measured_timeline` for compilation. Producer direction version 1 compiles the
measured edit and reviews the full moving preview before HD. Historical
workflows review the dynamic animatic at their pinned stage. The Remotion build
binds the complete WAV once and each
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
Whole-film continuous viewing remains required for final acceptance.

Six separate final dimensions: scientific accuracy; mechanical motion; visual
expression; narrative/comprehension; originality/copyright; audio/video/delivery.
Each binds exact media and located observations. Full timeline coverage and
continuous key-action viewing are required. Historically pinned policies and
the listening path require continuous audio coverage. Mixed media
keeps separate copyright and originality reviews. Comprehension and growth
gates follow the pinned task policies. Unknown capabilities stay UNKNOWN.

### Technical audio acceptance for verified Neil narration

New Producer-directed tasks carry `audio_acceptance_policy=verified_neil_technical`
in `task.json`. If the independent reviewer has no full listening record, submit
the normal `final-qa` handoff with real `continuous_video` observations and leave
`checks.listening` absent or `UNKNOWN`. The workflow generates
`audio_acceptance_mode`, `audio_technical_status` and `audio_technical_evidence`.
On this path it records `audio_perceptual_review=NOT_PERFORMED`. The independent
hybrid and route reviews leave listening absent, false or UNKNOWN as appropriate.
Keep the other applicable QA checks and the per-shot visual observations for
the scientific, narrative and AV dimensions. Use actual observations for the
visual timing and narration/action checks together with the verified script and
measured subtitle intervals.

The automatic check verifies the approved Neil profile, sealed request and WAV
cache, expected text, source hashes, exact measured sample intervals, final
composition inputs, and composed caption cues. It decodes the complete AAC
track, records its decoded PCM hash, and compares the audio against the bound
master in short sample-aligned windows through the last utterance. It verifies
per-utterance profile loudness, final loudness against the bound mix or master,
and true peak. It checks sample peaks and flags silence of at
least 0.5 s below −48 dBFS inside a measured utterance. Authored gaps between
utterances are part of the timeline. The caption evidence covers utterance
intervals. Pronunciation, naturalness and word-level alignment require actual
listening when a concern is raised.

An optional `audio_mix` in the bound composition supplies a mono 48 kHz PCM
`master` and its `stems` with `kind` (`bgm` or `sfx`), `source` binding,
`start_sample`, `end_sample`, `source_start_sample`, `gain_db` and the existing
rights fields. The verifier reconstructs the additive mix and checks local
peaks and a 10 dB speech-to-background margin in active speech windows. This
margin detects measurable masking risk. Audible clarity remains a listening
judgment. An unverified mix, narration/source mismatch or failed audio measure
prevents technical acceptance. Register known concerns, including a reported
pronunciation defect, as timecoded QA issues with `requires_audio_review=true`
for targeted resolution. Human speech and unverified external narration use
the existing full listening path. Older task ledgers retain their pinned
strategy. The user-invoked `/audience-review` remains a separate editorial review.

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
container. Coverage must include the entire actual timeline for the required
modalities, with a 1 ms timestamp tolerance. Each quality dimension references
its records via `observation_ids`. Scientific, narrative and AV conclusions
require full audiovisual coverage on the listening path and full video plus
generated audio evidence on the Neil technical path. Mechanical and visual
conclusions require full video coverage.
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

V2 and later tasks with `timeline_policy_version=1` derive running time from the joint story
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

## Bounded subjects for documented technology and legacy science

For legacy tasks using `science.subject_kind=physical_phenomenon`, research identifies a bounded
`science.subject` (`id`, `name`, `scope`, `model_kind=conceptual|mathematical`).
It does not invent a retail product. Located `subject_references` bind inspected
sources and supported claims. The existing compatibility `mechanism_id` names
that specific teaching implementation, never a claim of a retail mechanism.
Blueprint derives `subject_kind`, `subject_identity`, `subject_references` and
`subject_opening` from that research. Its existing comprehension rows connect
phenomenon, conditions, model, causal test and return to the opening question.
From v4, `science.subject_kind=documented_technology` uses
`model_kind=documented` for a named technology, period and historical scope.
V5 keeps this route for mechanical technology stories whose scope spans a design
change or multiple documented implementations. Each depicted mechanism still needs
its own evidence. A fact about shared principles alone cannot establish lineage.
Reference locations bind documented facts, and original reconstructions
disclose their status when viewers might mistake them for archival images.
Comprehension for these bounded subjects follows the selected question and visible
turning point without a prescribed parts or causality sequence. Scoped
mechanical implementations still require matching product and motion evidence.
The compiled config/build/manifest preserve the subject identity and policy.
Source/model/motion and full sensory acceptance stay strict; a named conceptual
subject is not evidence of a physical simulation. Legacy product tasks retain
their original product checks. This adds no second scheduler or fact database.
