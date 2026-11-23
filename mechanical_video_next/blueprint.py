"""Compile explicit blueprint mappings and render unapproved static animatics."""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import tempfile
import textwrap
import time

from scripts.common import ROOT, Metrics, budget, filehash, probe, writejson
from .viral import validate_creative_blueprint
from .workflow import lock, digest
from .science_shots import TEMPLATES as SCIENCE_TEMPLATES
from .visual_narrative import FIELD, VERSION, design_fields, match_policy, validate_plan, version

TEMPLATES = {'overall', 'detail', 'motion', 'explode', 'assemble', 'exploded', 'layered'} | SCIENCE_TEMPLATES
CAMERA = {'camera_view', 'camera_direction', 'camera_roll'}


def number(v):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)


def validate_story_preview(data, media, *, treatment=None, task=None):
    """Validate the executable clock of an authored moving draft."""
    from . import joint_timeline as joint

    films = [Path(row['path']) for row in media if Path(row['path']).suffix.lower() == '.mp4']
    if len(films) != 1:
        raise ValueError('Story preview needs one complete MP4')
    plan = data.get('timeline')
    if not isinstance(plan, dict):
        raise ValueError('Story preview needs a joint picture clock')
    joint.validate(plan)
    from .production_contract import validate_formal_duration
    policy = task if task is not None else data
    validate_formal_duration(policy, plan['frame_count'] / joint.FPS)
    from . import pacing
    if pacing.enabled(policy):
        if (not pacing.enabled(data) or not data.get('measured_timeline')
                or (treatment is not None and data.get('pacing_brief') != treatment['pacing_brief'])):
            raise ValueError('Formal draft must carry the pinned pacing policy, brief and measured speech')
        pacing.validate(plan, data.get('pacing'))
        if treatment is not None:
            scenes = {cut.get('scene_id') for cut in plan['shots']}
            if (not scenes <= {scene['id'] for scene in treatment['scenes']}
                    or not set(treatment['pacing_brief']['essential_scenes']) <= scenes):
                raise ValueError('Formal draft cuts must match the Treatment and cover essential scenes')
    if treatment is not None:
        core = {scene['id'] for scene in treatment['scenes'] if scene['mechanical_role'] == 'core'}
        picture = {shot['id'] for shot in plan['shots']}
        bindings = data.get('core_3d')
        if not isinstance(bindings, list) or not bindings:
            raise ValueError('Bind the core preview shots to inspectable native Blender scenes')
        seen = set()
        for row in bindings:
            if row.get('scene_id') not in core or row.get('shot_id') not in picture:
                raise ValueError('The core native scene must map to the Treatment and picture clock')
            if joint.bound(row['source']).suffix.lower() != '.blend':
                raise ValueError('The core preview source must be a Blender scene')
            seen.add(row['scene_id'])
        if seen != core:
            raise ValueError('Core preview bindings must cover the approved mechanism scenes')
    joint.validate_rendered_film(films[0], plan, require_audio=bool(data.get('measured_timeline')))
    if data.get('measured_timeline'):
        measured = joint.receipt(plan, data['measured_timeline'])
        joint.validate_rendered_audio(films[0], plan, measured)


def validate(data):
    """Validate the executable subset; no claim of scientific/media acceptance."""
    from .three_d import validate_config
    validate_config(data)
    from .production_contract import validate_direction, formal_duration_enabled, validate_formal_duration
    from . import joint_timeline as joint
    from . import director
    shared = joint.enabled(data)
    if formal_duration_enabled(data) and not shared:
        raise ValueError('Formal Blueprint needs the Joint Timeline')
    if formal_duration_enabled(data):
        from .growth import validate_growth_design
        validate_growth_design(data.get('growth_design'))
    if shared:
        joint.validate(data['timeline'], data.get('shots'))
        validate_formal_duration(data, data['timeline']['frame_count'] / joint.FPS)
        if data.get('status') == 'FROZEN':
            joint.receipt(data['timeline'], data['measured_timeline'])
    validate_direction(data)
    director.validate(data)
    director.validate_pacing(data)
    from . import director_audio
    if director_audio.enabled(data):
        if not shared:
            raise ValueError('Music direction requires a Joint Timeline')
        director_audio.plan_direction(data)
        director_audio.sound_stems(data['timeline'], data.get('sound_events', []), mechanical=True)
    if director.enabled(data) and data.get('status') == 'FROZEN':
        director.validate_measured_edit(data, joint.receipt(data['timeline'], data['measured_timeline']))
    visual = version(data) == VERSION
    if visual:
        validate_plan(data)
    from .comprehension import enabled, validate_product_plan
    if enabled(data):
        validate_product_plan(data)
    if not isinstance(data.get('shots'), list) or not data['shots']:
        raise ValueError('Nonempty structured shots required')
    if data.get('content_policy_version') == 1:
        from .growth import validate_contract
        validate_contract(data)
    if data.get('reference_policy_version') == 1 and not all(data.get(k) for k in ('evidence_map', 'content_timing')):
        raise ValueError('Reference-first blueprint requires evidence_map and content_timing')
    maximum = data['timeline']['frame_count'] / 30 if shared else 300 if data.get('content_policy_version') == 1 else 120
    end, ids = 0, set()
    for s in data['shots']:
        required = {'shot_id', 'time_range', 'knowledge_goal', 'mechanical_action',
                    'asset', 'template', 'camera', 'narration', 'subtitles', 'overlays'}
        if shared:
            required -= {'narration', 'subtitles'}
        if not isinstance(s, dict) or not required <= s.keys():
            raise ValueError('Shot missing executable fields')
        from .production_contract import NATURAL_SCIENCE, PRESENTATION_STYLE, validate_audience_copy, creative_first
        if data.get(PRESENTATION_STYLE) == NATURAL_SCIENCE:
            validate_audience_copy(s, creative=creative_first(data))
        if any(not isinstance(s[k], str) or not s[k].strip() for k in
               ('shot_id', 'knowledge_goal', 'mechanical_action', 'asset', 'template')):
            raise ValueError('Shot identifiers and decisions must be nonempty strings')
        if s['shot_id'] in ids or s['template'] not in (TEMPLATES | ({'editorial'} if visual else set())):
            raise ValueError('Duplicate shot ID or unknown template mapping')
        ids.add(s['shot_id'])
        if s.get('evidence_status') == 'RESEARCH_REQUIRED':
            raise ValueError('Research-required mechanism must be resolved before full blueprint compilation')
        t = s['time_range']
        if (not isinstance(t, list) or len(t) != 2 or not all(number(x) for x in t)
                or abs(t[0]-end) > 1e-8 or t[1] <= t[0] or t[1] > maximum):
            raise ValueError('Timeline must be contiguous from zero, positive, within the versioned duration limit')
        end = t[1]
        camera = s['camera']
        if visual:
            if abs(s['duration'] - (t[1] - t[0])) > 1e-8:
                raise ValueError('Visual duration differs from Blueprint timeline')
            camera = camera.get('settings', {})
            if s['render_engine'] != 'blender' and s['template'] != 'editorial':
                raise ValueError('Supporting media needs an editorial template')
        allowed = CAMERA | ({'science'} if visual else set())
        if not isinstance(camera, dict) or (not visual and not camera) or not set(camera) <= allowed:
            raise ValueError('Unsupported or empty camera mapping')
        if 'science' in camera:
            science = camera['science']
            camera_fields = {'camera_path', 'camera_rig', 'camera_clip', 'camera_path_follow', 'camera_framing'}
            if not isinstance(science, dict) or not science or not set(science) <= camera_fields:
                raise ValueError('Blueprint camera settings may only change science camera fields')
            from .science_shots import validate_editorial_geometry
            validate_editorial_geometry(science)
        if camera.get('camera_view', 'oblique') not in {'oblique', 'top'}:
            raise ValueError('Unsupported camera_view')
        if 'camera_roll' in camera and not number(camera['camera_roll']):
            raise ValueError('camera_roll must be finite')
        if 'camera_direction' in camera:
            d = camera['camera_direction']
            if not isinstance(d, list) or len(d) != 3 or not all(number(v) for v in d) or not any(d):
                raise ValueError('camera_direction requires a nonzero finite vector')
        for key in (('overlays',) if shared else ('narration', 'subtitles', 'overlays')):
            if not isinstance(s[key], list) or any(not isinstance(v, str) or not v.strip() for v in s[key]):
                raise ValueError(key + ' must be a list of nonempty strings')
        if not shared and (not s['narration'] or len(s['narration']) != len(s['subtitles'])):
            raise ValueError('One subtitle per narration utterance required')
    return end


def compile_config(blueprint, base, output, draft=False):
    blueprint, base, output = map(Path, (blueprint, base, output))
    if {output.resolve(), output.with_suffix('.binding.json').resolve()} & {blueprint.resolve(), base.resolve()}:
        raise ValueError('Output must not overwrite blueprint or base')
    data, cfg = json.loads(blueprint.read_text()), json.loads(base.read_text())
    from .three_d import validate_config
    validate_config(cfg)
    validate(data)
    from . import joint_timeline as joint
    from . import director
    shared = joint.enabled(data)
    picture = {s['id']: s for s in data['timeline']['shots']} if shared else {}
    locked = shared and joint.integrity(data['timeline'])
    visual = version(data) == VERSION
    if FIELD in cfg:
        match_policy(data, cfg)
    if data.get('status') != 'FROZEN' and not draft:
        raise ValueError('FROZEN blueprint required; --draft marks unapproved diagnostic output')
    if not draft:
        validate_creative_blueprint(data)
    result, shots, storyboard, mappings = copy.deepcopy(cfg), {}, [], []
    from .production_contract import PRESENTATION_STYLE, PRODUCER_DIRECTION, directed_story, science_story
    story = science_story(data)
    directed = directed_story(data)
    creative = director.enabled(data)
    if creative and not visual:
        raise ValueError('Creative direction requires the visual Blueprint renderer')
    if PRESENTATION_STYLE in data:
        result[PRESENTATION_STYLE] = data[PRESENTATION_STYLE]
    for s in data['shots']:
        key = s.get('existing_shot')
        editorial = visual and s['render_engine'] != 'blender'
        if not editorial and (not isinstance(key, str) or key not in cfg['shots']):
            raise ValueError('Unknown existing_shot mapping: ' + str(key))
        if not editorial and s['asset'] != cfg['asset']:
            raise ValueError('Blueprint asset does not match base assembly')
        original = {'template': 'editorial', **{k: s[k] for k in ('graphic', 'footage', 'split_screen') if k in s}} if editorial else cfg['shots'][key]
        if original['template'] != s['template']:
            raise ValueError('Template must match existing shot; geometry tracks cannot be repurposed')
        shot = copy.deepcopy(original)
        settings = s['camera'].get('settings', {}) if visual else s['camera']
        shot.update({k: copy.deepcopy(v) for k,v in settings.items() if k != 'science'})
        if settings.get('science'):
            if not shot.get('science'):
                raise ValueError('Camera science settings require an existing science shot')
            shot['science'].update(copy.deepcopy(settings['science']))
            if settings['science'].get('camera_rig'):
                shot['science'].pop('camera_clip', None)  # Rig has its own bounded perspective clip.
        seconds = s['duration'] if visual else s['time_range'][1] - s['time_range'][0]
        shot['seconds'] = seconds
        if shared and not editorial:
            offset = picture[s['shot_id']].get('source_start_frame', 0)
            source_seconds = original.get('seconds', 0)
            if joint.frame_number(source_seconds) >= offset + joint.frame_number(seconds):
                shot['seconds'] = source_seconds
            elif (locked and picture[s['shot_id']].get('action_views')) or (
                    directed and source_seconds and (shot.get('tracks') or shot.get('mesh_tracks') or
                    shot.get('science', {}).get('driver') in {'data_tracks', 'asset_motion'})):
                raise ValueError('Extend the authored motion or re-edit the picture interval: ' + s['shot_id'])
            elif offset:
                raise ValueError('Source render cannot cover the joint picture interval')
        if visual:
            shot['visual'] = copy.deepcopy(design_fields(s))
            if not editorial:
                from .visual_narrative import configure_blender
                configure_blender(shot, directed=directed)
        if creative:
            shot = director.apply_strategy(shot, s['director'], s['render_engine'], source=original)
        sid = s['shot_id']; shots[sid] = shot
        inherited = next((x for x in cfg.get('storyboard', []) if x['shot'] == key), {})
        editor_fields = dict(inherited)
        if story:
            for field in ('formula', 'information'):
                editor_fields.pop(field, None)
        editor_fields.update({k: s[k] for k in ('accent', 'formula', 'information') if visual and k in s})
        row = {k: copy.deepcopy(editor_fields[k]) for k in ('accent', 'formula', 'information') if k in editor_fields}
        words = joint.shot_narration(data, s)
        row.update(id=sid, shot=sid, seconds=seconds, label='' if story else s['knowledge_goal'],
                   note=' / '.join(s['overlays']), narration=words,
                   subtitles=words if shared else s['subtitles'])
        row.setdefault('accent', '#8dc4dc'); storyboard.append(row)
        mappings.append(dict(shot_id=sid, existing_shot=key, time_range=s['time_range'],
                             knowledge_goal=s['knowledge_goal'], mechanical_action=s['mechanical_action'],
                             asset=s['asset'], template=s['template'], camera=s['camera'],
                             overlays=s['overlays'], motion_validation='UNKNOWN'))
        if visual and 'direction' in s:
            mappings[-1]['direction'] = copy.deepcopy(s['direction'])
    result.update(id=cfg.get('id', 'video') + '-blueprint-' + filehash(blueprint)[:16], shots=shots, storyboard=storyboard,
                  blueprint_program_sha256=digest({k: val for k, val in data.items() if k != 'production_config'}),
                  production_status='DRAFT_UNAPPROVED' if draft else 'BLUEPRINT_BOUND_UNVALIDATED')
    if shared:
        for key in (joint.FIELD, 'timeline', 'measured_timeline'):
            if key in data:
                result[key] = copy.deepcopy(data[key])
    else:
        for key in (joint.FIELD, 'timeline', 'measured_timeline'):
            result.pop(key, None)
    from . import director_audio
    for key in director_audio.POLICY_FIELDS:
        result.pop(key, None)
    if director_audio.enabled(data):
        result.update({key: data[key] for key in director_audio.POLICY_FIELDS if key in data})
        result.pop('audio_mix', None)
        result.pop('audio_direction', None)
        if data.get('measured_timeline'):
            measured = joint.receipt(data['timeline'], data['measured_timeline'])
            direction, mixture, _ = director_audio.arrange(data, measured, directory=output.parent / 'audio-direction')
            result['audio_direction'] = direction
            if mixture:
                result['audio_mix'] = mixture
            result['id'] += '-audio-' + direction['sha256'][:16]
    else:
        result.pop('audio_direction', None)
    if creative:
        result[director.FIELD] = director.VERSION
        if not director_audio.enabled(data) and data.get('sound_events') and data.get('measured_timeline'):
            from .director_audio import mix
            measured = joint.receipt(data['timeline'], data['measured_timeline'])
            sound_key = digest([data['timeline'], data['sound_events'], measured['narration_audio']])
            sound_path = output.parent / f'director-mix-{sound_key}.wav'
            result['audio_mix'] = mix(data['timeline'], data['sound_events'],
                                      joint.bound(measured['narration_audio']), sound_path)
    from .production_contract import (
        FIELD as CONTRACT_FIELD, STORY_DEVELOPMENT, enabled as science_contract, mechanism_first,
        flexible_story, producer_directed, FORMAL_DURATION_FIELD,
    )
    for key in (FORMAL_DURATION_FIELD, 'growth_design', 'pacing_brief', 'pacing'):
        if key in data:
            result[key] = copy.deepcopy(data[key])
        else:
            result.pop(key, None)
    if science_contract(data):
        for key in (CONTRACT_FIELD, 'production_contract', 'narrative'):
            result[key] = copy.deepcopy(data[key])
        if STORY_DEVELOPMENT in data:
            result[STORY_DEVELOPMENT] = data[STORY_DEVELOPMENT]
        if mechanism_first(data):
            result['mechanical_object'] = data['mechanical_object']
        if flexible_story(data):
            # Chapters are authored navigation or editorial notes. The joint
            # picture track remains the executable clock.
            result.pop('chapters', None)
            if 'chapters' in data:
                result['chapters'] = copy.deepcopy(data['chapters'])
        if producer_directed(data):
            result['subject_kind'] = data.get('subject_kind', 'mechanical_implementation')
            result['production_method'] = data['production_method']
            if directed:
                result[PRODUCER_DIRECTION] = data[PRODUCER_DIRECTION]
                result['reference_principles'] = copy.deepcopy(data.get('reference_principles', []))
                result['render']['preview_native'] = False
    if data.get('content_policy_version') == 1:
        from .growth import shot_requirements
        result.update(content_policy_version=1, growth_goals=copy.deepcopy(data['growth_goals']))
        if data.get('growth_policy_version') == 2:
            result['growth_policy_version'] = 2
        else:
            result.pop('growth_policy_version', None)
        if 'duration_policy_override' in data:
            result['duration_policy_override'] = copy.deepcopy(data['duration_policy_override'])
        else:
            result.pop('duration_policy_override', None)
        for row, shot in zip(storyboard, data['shots']):
            row.update(shot_requirements(shot, data))
        for row, shot in zip(mappings, data['shots']):
            row.update(shot_requirements(shot, data))
    if data.get('reference_policy_version') == 1:
        for key in ('reference_policy_version', 'evidence_map', 'content_timing'):
            result[key] = copy.deepcopy(data[key])
        for row, shot in zip(result['storyboard'], data['shots']):
            row['knowledge_ids'] = copy.deepcopy(shot['knowledge_ids'])
    from .comprehension import enabled
    if enabled(data):
        from .production_contract import nonmechanical_subject
        identity_fields = (('subject_kind', 'subject_identity', 'subject_references', 'subject_opening')
                           if nonmechanical_subject(data)
                           else ('product_identity', 'product_references', 'product_opening'))
        for key in identity_fields:
            result[key] = copy.deepcopy(data[key])
        result['product_policy_version'] = 1
        for collection in (storyboard, mappings):
            for row, shot in zip(collection, data['shots']):
                row['comprehension'] = copy.deepcopy(shot['comprehension'])
    if visual:
        result[FIELD] = VERSION
        from .media_policy import FIELD as MEDIA_FIELD, enabled as asset_first
        if asset_first(data):
            result[MEDIA_FIELD] = data[MEDIA_FIELD]
        result['visual_findings'] = validate_plan(data)
        from .knowledge_progression import FIELD as PROGRESSION_FIELD, enabled
        if enabled(data):
            result[PROGRESSION_FIELD] = data[PROGRESSION_FIELD]
            result['render'].setdefault('encode_profile', 'progression-witness-v1')
        else:
            result['render'].setdefault('encode_profile', 'witness-v1')
        validate_config(result)
    elif locked:
        validate_config(result)
    writejson(output, result)
    binding = dict(schema_version=1, status=result['production_status'], blueprint_path=str(blueprint.resolve()),
                   blueprint_program_sha256=result['blueprint_program_sha256'],
                   blueprint_sha256=filehash(blueprint), base_config_sha256=filehash(base),
                   config_sha256=filehash(output), shot_requirements=mappings,
                   scientific_acceptance='UNKNOWN', visual_acceptance='UNKNOWN', listening='UNKNOWN')
    writejson(output.with_suffix('.binding.json'), binding)
    return binding


def image_source(s, directory):
    spec = s.get('animatic', {})
    if not isinstance(spec, dict):
        raise ValueError('animatic must be an object')
    if not spec.get('image'):
        return None
    image = (directory / spec['image']).resolve()
    if image.suffix.lower() not in {'.png', '.jpg', '.jpeg'} or not image.is_file():
        raise ValueError('Existing static PNG/JPEG screenshot required')
    if filehash(image) != spec.get('sha256'):
        raise ValueError('Animatic image hash mismatch: ' + str(image))
    return image


def sampled_run(args, log, metrics):
    """Stop the subprocess on a 0.5-second budget sample failure; retain its log."""
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open('w') as handle:
        with subprocess.Popen([str(a) for a in args], stdout=handle, stderr=subprocess.STDOUT) as process:
            try:
                while True:
                    try:
                        code = process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        code = None
                    used = budget()
                    metrics.peak = max(metrics.peak, used)
                    metrics.temp_samples.append(dict(epoch=time.time(), bytes=used))
                    if code is not None:
                        if code:
                            raise subprocess.CalledProcessError(code, args)
                        break
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
                raise


def animatic(blueprint, output):
    blueprint, output = Path(blueprint).resolve(), Path(output).resolve()
    data = json.loads(blueprint.read_text()); duration = validate(data)
    sources = [image_source(s, blueprint.parent) for s in data['shots']]
    if any(abs(t*15-round(t*15)) > 1e-6 for s in data['shots'] for t in s['time_range']):
        raise ValueError('Animatic boundaries must fall on 15fps frames')
    font = next((p for p in (Path('/System/Library/Fonts/PingFang.ttc'),
                            Path('/System/Library/Fonts/STHeiti Medium.ttc'),
                            Path('/System/Library/Fonts/Supplemental/Songti.ttc'),
                            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')) if p.is_file()), None)
    if font is None:
        raise ValueError('No supported drawtext font available')
    # Prefer PingFang; macOS also ships Chinese glyphs in Heiti and Songti.
    if font.name == 'DejaVuSans.ttf' and any(ord(c) > 127 for c in json.dumps(data, ensure_ascii=False)):
        raise ValueError('Chinese animatic requires an installed Chinese font')
    output.mkdir(parents=True, exist_ok=True)
    manifest_path, media = output/'animatic-manifest.json', output/'animatic.mp4'
    if media.exists() or manifest_path.exists() or (output/'animatic.failed.json').exists():
        raise ValueError('Use a new output directory; existing animatic is immutable')
    with lock(ROOT/'work/production.lock'):
        metrics = Metrics('blueprint-animatic-' + str(time.time_ns()))
        metrics.temp_samples = []
        try:
            with tempfile.TemporaryDirectory(prefix='animatic-', dir=ROOT/'work') as tmp:
                work, pieces, coverage = Path(tmp), [], []
                for i, (s, source) in enumerate(zip(data['shots'], sources)):
                    started = time.time(); seconds = s['time_range'][1]-s['time_range'][0]
                    # Keep diagnostic metadata above the model and speech below
                    # it. Text must not conceal the very mechanism QA inspects.
                    caption = '\n'.join([*s['subtitles'], *s['overlays']])
                    text = work/f'caption-{i}.txt'
                    wrapped = '\n'.join(textwrap.fill(line, 36) for line in caption.splitlines())
                    if len(wrapped.splitlines()) > 4:
                        raise ValueError('Animatic caption exceeds reserved four-line band; split the utterance or shot')
                    text.write_text(wrapped)
                    title = work/f'title-{i}.txt'
                    title.write_text(s['shot_id'] + ' | ' + s['knowledge_goal'])
                    watermark = work/'watermark.txt'
                    watermark.write_text('PROVISIONAL / STATIC PLACEHOLDER')
                    # All filter paths are generated safe filenames, never user text or image paths.
                    vf = ('scale=960:310:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:100:color=0x555555,'
                          f"drawtext=fontfile='{font}':textfile={watermark}:fontcolor=yellow:fontsize=24:x=20:y=20,"
                          f"drawtext=fontfile='{font}':textfile={title}:expansion=none:fontcolor=white:fontsize=20:x=20:y=65,"
                          f"drawtext=fontfile='{font}':textfile={text}:expansion=none:fontcolor=white:fontsize=24:"
                          'x=20:y=430:box=1:boxcolor=black@0.7:boxborderw=8')
                    args = ['ffmpeg', '-v', 'error', '-nostdin', '-n']
                    args += ['-loop', '1', '-i', str(source)] if source else ['-f', 'lavfi', '-i', 'color=c=0x555555:s=960x540:r=15']
                    piece = work/f'shot-{i}.mp4'
                    sampled_run(args + ['-vf', vf, '-r', '15', '-frames:v', str(round(seconds*15)),
                                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an', str(piece)], output/'logs'/f'shot-{i}.log', metrics)
                    pieces.append(piece); metrics.record('static-shot', started, shot_id=s['shot_id'])
                    coverage.append(dict(shot_id=s['shot_id'], time_range=s['time_range'],
                                         kind='STATIC_SCREENSHOT' if source else 'GRAY_SLATE',
                                         image=str(source) if source else None,
                                         sha256=filehash(source) if source else None, mechanical_motion='NOT_SHOWN'))
                listing = work/'concat.txt'
                listing.write_text(''.join("file '" + str(p) + "'\n" for p in pieces))
                started = time.time()
                sampled_run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'concat', '-safe', '0', '-i', listing,
                     '-c', 'copy', '-movflags', '+faststart', media], output/'logs'/'concat.log', metrics)
                sampled_run(['ffmpeg', '-v', 'error', '-xerror', '-i', media, '-f', 'null', '-'], output/'logs'/'decode.log', metrics)
                info = probe(media)
                video = next(s for s in info['streams'] if s['codec_type'] == 'video')
                if abs(float(info['format']['duration'])-duration) > 1/15+.001 or (video['width'], video['height']) != (960, 540):
                    raise ValueError('Encoded animatic timeline/dimensions mismatch')
                metrics.record('concat-and-decode', started)
                manifest = dict(status='DRAFT_UNAPPROVED', blueprint_sha256=filehash(blueprint),
                                media_sha256=filehash(media), media=str(media), duration_seconds=duration,
                                coverage=coverage, full_decode='PASS', listening='UNKNOWN', continuous_viewing='UNKNOWN',
                                core_mechanics='UNKNOWN', production_approved=False, probe=info)
                manifest['layout'] = {'model_band_y': [100, 410], 'caption_band_y': [422, 534],
                                      'title_band_y': [65, 85], 'text_model_band_overlap_pixels': 0}
                writejson(manifest_path, manifest)
                return manifest
        except BaseException as error:
            writejson(output/'animatic.failed.json', dict(status='FAILED', error=str(error),
                      blueprint_sha256=filehash(blueprint), production_approved=False,
                      logs=[str(p) for p in sorted((output/'logs').glob('*.log'))],
                      temp_peak_sampled_bytes=metrics.peak, temp_samples=metrics.temp_samples))
            raise
        finally:
            metrics.finish(tokens=None, cost=None, human_interventions=None, temp_sample_interval_seconds=.5,
                           temp_samples=metrics.temp_samples)


def match_assets(blueprint, output, library=Path('references')):
    """Match the visual plan using the existing library; never freeze decisions or grant QA."""
    from .media_policy import binding, enabled as asset_first
    from .reference_library import match_media
    blueprint, output = Path(blueprint), Path(output)
    if blueprint.resolve() == output.resolve():
        raise ValueError('Asset matching must not overwrite the visual Blueprint')
    data = json.loads(blueprint.read_text())
    if not asset_first(data) or not isinstance(data.get('shots'), list) or not data['shots']:
        raise ValueError('Match the new asset-first visual Blueprint before compilation')
    results, used = [], []
    for shot in data['shots']:
        query = copy.deepcopy(shot.get('media_query', {}))
        query.setdefault('tags', [shot['visual_type']])
        query.setdefault('mechanism_knowledge', shot['knowledge_ids'])
        query.setdefault('required_visual_capabilities', shot.get('required_visual_capabilities', []))
        query.setdefault('required_model_capabilities', shot.get('required_model_capabilities', []))
        if 'graphic' in shot:
            query.setdefault('graphic_type', shot['graphic']['type'])
        query.setdefault('usage_scope', 'commercial-video')
        query.setdefault('duration_sec', shot['duration'])
        query.setdefault('project_id', data.get('task_id'))
        implementation = data.get('product_identity', {}).get('mechanism_id')
        if shot.get('mechanical_role') == 'core' and implementation:
            if query.get('mechanism_id', implementation) != implementation:
                raise ValueError('Core media query differs from Blueprint mechanism identity')
            query['mechanism_id'] = implementation
        query.update(shot_id=shot['shot_id'], used_intervals=copy.deepcopy(used))
        # Selecting a model still requires the existing Asset/CAD inspection.
        query.setdefault('accepted_types', {'blender':['video','model'], 'remotion':['video','graphic','template'],
                                            'footage':['video']}[shot['render_engine']])
        result = match_media(query, library)
        if result['selected_asset'] is not None and result['reuse_decision'] not in {'REUSE_MODEL','REUSE_TEMPLATE'}:
            used.append({'sha256':result['selected_asset']['sha256'], 'time_range':result['source_time_range']})
        results.append({'shot_id': shot['shot_id'], 'knowledge_goal': shot['knowledge_goal'],
                        'query': query, 'match': result})
    report = {'schema_version':1, 'media_policy_version':1, 'visual_policy_version':2,
              'status':'MATCHED_REQUIRES_PRODUCER_REVIEW', 'blueprint':binding(blueprint),
              'library':str(Path(library).resolve()), 'shots':results,
              'network_accessed':False, 'formal_acceptance':False}
    writejson(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('compile', 'animatic'):
        p = sub.add_parser(command)
        p.add_argument('--blueprint', required=True, type=Path); p.add_argument('--output', required=True, type=Path)
        if command == 'compile':
            p.add_argument('--base', required=True, type=Path); p.add_argument('--draft', action='store_true')
    p = sub.add_parser('match-media')
    p.add_argument('--blueprint', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--library', type=Path, default=Path('references'))
    a = parser.parse_args(argv)
    if a.command == 'match-media':
        result = match_assets(a.blueprint, a.output, a.library)
    else:
        result = compile_config(a.blueprint, a.base, a.output, a.draft) if a.command == 'compile' else animatic(a.blueprint, a.output)
    print(json.dumps({'status': result['status'], 'output': str(a.output)}))


if __name__ == '__main__':
    main()
