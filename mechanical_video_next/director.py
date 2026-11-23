"""Producer decisions that compile into the existing picture, sound and render tracks."""
from copy import deepcopy
from math import isfinite

from scripts.common import digest
from . import joint_timeline as joint

FIELD = 'creative_direction_version'
VERSION = 1
APPROACHES = {'mystery', 'failure_inference', 'direct_experiment'}
TREATMENT = ('question', 'watch_reason', 'hook', 'tension', 'reveal', 'explanation',
             'payoff', 'dropoff_risk', 'rhythm', 'evaluation')
SHOT = ('narrative_purpose', 'audience_question', 'subject', 'visual_focus',
        'shot_type', 'framing', 'camera_position', 'camera_movement', 'object_movement',
        'reveal_strategy', 'lighting_style', 'visual_effects', 'transition',
        'audio_cues', 'scientific_evidence', 'asset_requirements', 'new_information')
ROUTES = {
    'native_3d': 'blender', 'cad_blender': 'blender', 'owned_native_animation': 'blender',
    'remotion': 'remotion', 'layered_animation': 'footage', 'scientific_visualization': 'remotion',
    'licensed_footage': 'footage', 'mixed_composite': 'footage',
}
METRICS = ('accuracy', 'expression', 'intent', 'availability', 'style')
EDIT_KINDS = {'cut', 'match_cut', 'action_match', 'j_cut', 'l_cut', 'contrast',
              'sound_lead', 'pause', 'time_compression', 'reveal'}
CAMERA = {'camera_path', 'camera_framing', 'camera_clip', 'camera_path_follow',
          'camera_rig', 'observation_window', 'anchors'}
# Each entry specifies an adapter, its executable input and the evidence it needs.
STRATEGIES = {
    'macro_reveal': ('blender', ('camera_path',), 'A named physical detail in its assembly'),
    'transparent_cutaway': ('blender', ('opacity_tracks', 'section_plane'), 'Verified hidden geometry'),
    'exploded_view': ('blender', ('exploded_view',), 'Part assembly and a conceptual explosion program'),
    'motion_tracking': ('blender', ('camera_path_follow', 'follow', 'camera_rig'), 'A named moving datum'),
    'force_visualization': ('remotion', ('graphic',), 'Sourced force or labeled qualitative representation'),
    'energy_flow': ('remotion', ('graphic',), 'Verified energy path with a declared representation'),
    'motion_comparison': ('remotion', ('graphic',), 'Comparable states with an explicit interpretation'),
    'mechanism_isolation': ('blender', ('visible_parts', 'opacity_tracks'), 'Known parts and context'),
    'failure_vs_success': ('remotion', ('graphic',), 'Observed failure or explicitly idealized comparison'),
    'hidden_mechanism_reveal': ('blender', ('opacity_tracks', 'section_plane', 'camera_path'), 'Verified obscured component'),
    'slow_motion_detail': ('blender', ('time_map',), 'Source action with synchronized time mapping'),
    'scale_transition': ('blender', ('camera_path', 'camera_framing'), 'A common spatial anchor'),
}
SCHEMATIC = {'transparent_cutaway', 'exploded_view', 'force_visualization', 'energy_flow',
             'failure_vs_success', 'mechanism_isolation', 'slow_motion_detail'}


def enabled(document):
    version = document.get(FIELD, 0)
    if type(version) is not int or version not in (0, VERSION):
        raise ValueError('Unsupported creative direction version')
    return version == VERSION


def text_fields(row, fields):
    return isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key].strip() for key in fields)


def validate_storyboard(scenes, facts, *, mechanics=False):
    """Validate the Director's story decisions before choosing rendering inputs."""
    fields = ('id', 'visual_form', 'visible_change', 'story_purpose', 'causal_link')
    if not isinstance(scenes, list) or not scenes:
        raise ValueError('Direct the complete story as an ordered sequence of scenes')
    seen = set()
    for scene in scenes:
        if not text_fields(scene, fields) or scene['id'] in seen:
            raise ValueError('Each scene needs a distinct ID, visible change and causal role')
        ids = scene.get('fact_ids')
        if not isinstance(ids, list) or any(
                not isinstance(key, str) or facts.get(key, {}).get('status') != 'VERIFIED'
                for key in ids):
            raise ValueError('Storyboard claims must link to verified research')
        seen.add(scene['id'])
    if mechanics:
        if any(scene.get('mechanical_role') not in {'support', 'core'} for scene in scenes):
            raise ValueError('Identify which scenes explain the core mechanism')
        core = [scene for scene in scenes if scene['mechanical_role'] == 'core']
        if not core or any(scene.get('render_engine') != 'blender' or not scene['fact_ids'] for scene in core):
            raise ValueError('The storyboard needs source-supported Blender scenes for the core mechanism')


def select_route(candidates, core):
    """Use scientific eligibility first, then compare presentation and production cost."""
    if not isinstance(candidates, list) or not candidates:
        raise ValueError('Visual Planner needs assessed candidate routes')
    seen, eligible = set(), []
    for row in candidates:
        if not text_fields(row, ('route', 'basis')) or row['route'] not in ROUTES or row['route'] in seen:
            raise ValueError('Each visual candidate needs one supported route and a concrete basis')
        route = row['route']
        seen.add(route)
        if not all(type(row.get(key)) is int and 0 <= row[key] <= 4 for key in METRICS):
            raise ValueError('Visual candidate assessments must be integers from 0 to 4')
        if not all(type(row.get(key)) in (int, float) and isfinite(row[key]) and row[key] >= 0
                   for key in ('estimated_seconds', 'estimated_cost')):
            raise ValueError('Visual candidates need finite nonnegative time and cost estimates')
        if row['availability'] and row['accuracy'] >= (4 if core else 2) and (
                not core or (route != 'layered_animation' and ROUTES[route] in {'blender', 'footage'})):
            eligible.append(row)
    if not eligible:
        raise ValueError('No available visual route supplies the required scientific evidence')
    return max(eligible, key=lambda row: (
        row['accuracy'], row['intent'] + row['expression'] + row['style'],
        row['availability'], -row['estimated_cost'], -row['estimated_seconds']))['route']


def validate(document):
    if not enabled(document):
        return
    selected = validate_treatments(document.get('director'))
    if selected['question'] != document.get('core_question'):
        raise ValueError('Selected treatment and Blueprint must share the core question')
    plan = joint.validate(document['timeline'], document['shots'])
    from .director_audio import sound_stems
    stems = sound_stems(plan, document.get('sound_events', []))
    cuts = {row['id']: row for row in plan['shots']}
    for shot in document['shots']:
        direction = shot.get('director')
        if not text_fields(direction, SHOT):
            raise ValueError('Incomplete director storyboard for ' + shot['shot_id'])
        if direction['visual_focus'] != shot['visual_focus']:
            raise ValueError('Director focus differs from the executable shot focus')
        route = select_route(direction.get('candidates'), shot['mechanical_role'] == 'core')
        if ROUTES[route] != shot['render_engine']:
            raise ValueError('Blueprint renderer differs from the selected visual route')
        if route == 'mixed_composite' and not shot.get('split_screen'):
            raise ValueError('Mixed composition needs bound split-screen inputs')
        if route == 'layered_animation':
            if not text_fields(direction, ('schematic_scope',)) or shot.get('mechanical_role') != 'support':
                raise ValueError('Layered visual needs an explicit illustrative scope and a supporting role')
            validate_layered_source(direction.get('layered_receipt'), shot.get('footage', {}))
        if (direction.get('strategy') not in STRATEGIES
                and direction.get('strategy') != 'source_observation'):
            raise ValueError('Unknown visual strategy')
        if direction.get('strategy') in SCHEMATIC and not text_fields(direction, ('schematic_scope',)):
            raise ValueError('Describe which visual behavior is schematic or retimed')
        if direction.get('strategy') == 'source_observation' and direction.get('presentation'):
            raise ValueError('Source observation uses the verified native media as authored')
        presentation = direction.get('presentation', {})
        if not isinstance(presentation, dict) or ('graphic' in presentation
                and presentation['graphic'] != shot.get('graphic')):
            raise ValueError('Visual presentation must agree with the Blueprint graphic')
        validate_edits(direction.get('edits'), cuts[shot['shot_id']], plan, stems=stems)


def validate_layered_source(receipt, footage):
    """Use a previously rendered 2.5D clip through the existing licensed-video adapter."""
    import json

    if (not text_fields(receipt, ('path', 'sha256')) or not text_fields(footage, ('path', 'sha256'))):
        raise ValueError('Layered visual needs bound media and a native layer-render receipt')
    data = json.loads(joint.bound(receipt).read_text())
    program = data.get('program')
    media = data.get('media')
    checks = data.get('checks')
    if (data.get('render_route') != '2.5d' or not text_fields(program, ('path', 'sha256'))
            or not text_fields(media, ('path', 'sha256')) or media['sha256'] != footage['sha256']
            or not text_fields(checks, ('path', 'sha256'))):
        raise ValueError('Layered visual needs the rendered media, layer program and checks')
    if joint.bound(media).resolve() != joint.bound(footage).resolve():
        raise ValueError('Layered render receipt points to a different video')
    execution = json.loads(joint.bound(checks).read_text())
    source = json.loads(joint.bound(program).read_text())
    if (source.get('render_route') != '2.5d' or source.get('mechanical_role') != 'support'
            or not isinstance(source.get('layers'), list) or not source['layers']):
        raise ValueError('Layered render must use a 2.5D layer program')
    if execution.get('source_hashes') != {str(joint.bound(layer)): layer['sha256'] for layer in source['layers']}:
        raise ValueError('Layer checks differ from the current rendered program sources')


def validate_treatments(direction):
    if not text_fields(direction, ('selection_reason',)):
        raise ValueError('Director needs a reason for selecting the treatment')
    treatments = direction.get('treatments')
    if (not isinstance(treatments, dict) or set(treatments) != APPROACHES
            or not all(text_fields(row, TREATMENT) for row in treatments.values())
            or len({row['hook'].strip() for row in treatments.values()}) != 3
            or len({row['explanation'].strip() for row in treatments.values()}) != 3
            or not isinstance(direction.get('selected'), str)
            or direction['selected'] not in APPROACHES):
        raise ValueError('Director needs three distinct treatments and a reason for selecting one')
    return treatments[direction['selected']]


def validate_edits(edits, picture, plan, *, stems=()):
    if not isinstance(edits, list) or not edits:
        raise ValueError('Each shot needs an editing decision')
    start, stop = picture['start_frame'], picture['end_frame']
    for edit in edits:
        if (not text_fields(edit, ('kind', 'purpose')) or edit['kind'] not in EDIT_KINDS
                or type(edit.get('frame')) is not int or not start <= edit['frame'] < stop):
            raise ValueError('Editing decisions need a purpose and a frame inside the shot')
        kind = edit['kind']
        frame = edit['frame']
        if kind in {'cut', 'match_cut', 'action_match', 'contrast', 'j_cut', 'l_cut'} and frame != start:
            raise ValueError('A picture cut must bind its actual timeline boundary')
        if kind in {'match_cut', 'action_match'} and (not start or not text_fields(edit, ('anchor',))):
            raise ValueError('Match cut needs a preceding picture and an explicit common anchor')
        if kind in {'j_cut', 'l_cut'}:
            segment = next((row for row in plan['narration'] if row['id'] == edit.get('speech_id')), {})
            if not segment or not segment['start_frame'] < frame < segment['deadline_frame']:
                raise ValueError('J/L cut requires a speech slot crossing the picture cut')
        if kind == 'action_match':
            previous = next((row for row in plan['shots'] if row['end_frame'] == frame), {})
            if not set(previous.get('action_views', {})) & set(picture.get('action_views', {})):
                raise ValueError('Action match needs the same mechanical clock on both sides')
        if kind == 'pause' and any(row['start_frame'] <= frame < row['deadline_frame']
                                   for row in plan['narration']):
            raise ValueError('Pause must fall in a visual observation window without speech')
        if kind == 'sound_lead':
            sample = frame * joint.SAMPLES_PER_FRAME
            if not any(row['lead_frames'] > 0 and row['start_sample'] < sample < row['end_sample']
                       for row in stems if row.get('lead_frames')):
                raise ValueError('Sound lead requires an effect that crosses the reveal point')


def validate_measured_edit(document, measured):
    """A speech slot can cross a cut while its actual Neil audio ends early."""
    if not enabled(document):
        return
    speech = {row['id']: row for row in measured['speech']}
    for shot in document['shots']:
        for edit in shot['director']['edits']:
            if edit['kind'] in {'j_cut', 'l_cut'}:
                row = speech[edit['speech_id']]
                sample = edit['frame'] * joint.SAMPLES_PER_FRAME
                if not row['start_sample'] < sample < row['end_sample']:
                    raise ValueError('The measured Neil utterance does not cross the selected cut')


def validate_pacing(document, research=None):
    from . import pacing
    if not pacing.enabled(document):
        return
    facts = None
    if research is not None:
        facts = {row['id'] for row in research['science']['facts'] if row['status'] == 'VERIFIED'}
    pacing.validate(document['timeline'], document.get('pacing'), facts=facts)


def mechanical_digest(shot):
    """Fingerprint the verified driver, contact constraints and immutable source tracks."""
    science = shot.get('science', {})
    return digest({
        'template': shot.get('template'), 'tracks': shot.get('tracks'),
        'mesh_tracks': shot.get('mesh_tracks'), 'rotation_interpolation': shot.get('rotation_interpolation'),
        'distance': shot.get('distance'),
        'science': {
            key: science.get(key) for key in ('driver', 'basis', 'constraints', 'motion_bodies', 'motion_source', 'mode', 'control')
        },
    })


def validate_action_programs(config):
    """Keep verified action frames on their source clock through compilation."""
    from .science_shots import source_progress

    plan = config['timeline']
    actions = {row['id']: row for row in plan['actions']}
    native_clocks = {}
    for cut, row in zip(plan['shots'], config['storyboard'], strict=True):
        shot = config['shots'][row['shot']]
        for event_id in cut.get('action_views', {}):
            action = actions[event_id]
            if shot['template'] == 'editorial':
                if (not shot.get('footage') or shot.get('graphic') or shot.get('split_screen')
                        or shot['footage'] != action.get('footage')):
                    raise ValueError('Mechanical event requires the verified source footage: ' + event_id)
                if any(shot['footage'].get(key) != action['source'].get(key) for key in ('path', 'sha256')):
                    raise ValueError('Mechanical event footage differs from the bound source: ' + event_id)
                continue
            program = action_program_digest(shot)
            if program != action.get('shot_programs', {}).get(row['id']):
                raise ValueError('Mechanical program changed for ' + event_id + '/' + row['id'])
            clock = (program, cut.get('source_clock_origin', 0))
            if native_clocks.setdefault(event_id, clock) != clock:
                raise ValueError('Mechanical event must retain its native program and clock across cuts: ' + event_id)
            count = joint.frame_number(shot['seconds'])
            source_start = cut.get('source_start_frame', 0)
            first = source_start + max(0, action['start_frame'] - cut['start_frame'])
            last = source_start + min(action['end_frame'], cut['end_frame']) - cut['start_frame'] - 1
            if last >= count:
                raise ValueError('Mechanical event exceeds the native render: ' + event_id)
            mapping = shot.get('science', {}).get('time_map')
            if mapping and count > 1:
                left, right = first / (count - 1), last / (count - 1)
                points = [left, right, *(key[0] for key in mapping if left < key[0] < right)]
                if any(abs(source_progress(mapping, point) - point) > 1e-9 for point in points):
                    raise ValueError('Time map changes the verified mechanical event: ' + event_id)


def action_program_digest(shot):
    return digest({'mechanical': mechanical_digest(shot), 'source_frames': joint.frame_number(shot['seconds'])})


def apply_strategy(shot, direction, engine, *, source=None):
    """Resolve strategy into the existing Blender/Remotion inputs, preserving motion."""
    result = deepcopy(shot)
    strategy = direction['strategy']
    fields = direction.get('presentation', {})
    if not isinstance(fields, dict):
        raise ValueError('Visual presentation must be a mapping of renderer fields')
    if strategy == 'source_observation':
        if fields:
            raise ValueError('Source observation cannot change the media')
        if engine == 'blender' and mechanical_digest(result) != mechanical_digest(source or shot):
            raise ValueError('Presentation changed the native mechanical program')
        if any(row['kind'] == 'time_compression' for row in direction.get('edits', [])):
            raise ValueError('Time compression must use an authored source time map')
        return result
    renderer, required, _ = STRATEGIES[strategy]
    if renderer != engine or fields.keys() - (CAMERA | set(required)):
        raise ValueError('Strategy can only write its own presentation fields')
    if strategy in SCHEMATIC and not text_fields(direction, ('schematic_scope',)):
        raise ValueError('Schematic presentation must declare its scope')
    science = result.get('science', {})
    for key, value in fields.items():
        if key in {'visible_parts', 'section_plane', 'graphic'}:
            result[key] = deepcopy(value)
        elif key in CAMERA or key in {'time_map', 'opacity_tracks'}:
            science[key] = deepcopy(value)
            if key == 'camera_rig':
                science.pop('camera_clip', None)
        else:
            raise ValueError('Use the existing shot template to implement ' + key)
    if not any(result.get(key) or science.get(key) or key == result.get('template') for key in required):
        raise ValueError('Strategy has no corresponding renderer input: ' + strategy)
    if renderer == 'blender':
        from .science_shots import validate as validate_shot
        if not science or mechanical_digest(result) != mechanical_digest(source or shot):
            raise ValueError('Presentation changed the native mechanical program')
        validate_shot(result)
    if any(row['kind'] == 'time_compression' for row in direction.get('edits', [])) and not science.get('time_map'):
        raise ValueError('Time compression must use an authored source time map')
    return result


def preview_evidence(path, plan, core_ids):
    """Decode the complete workprint and measure picture changes within each shot."""
    import subprocess
    from scripts.common import probe

    validate_plan = joint.validate(plan)
    streams = probe(path)['streams']
    video = next((row for row in streams if row['codec_type'] == 'video'), {})
    audio = next((row for row in streams if row['codec_type'] == 'audio'), {})
    if (video.get('avg_frame_rate') != '30/1' or video.get('width', 1921) > 960
            or video.get('height', 1081) > 540 or not audio
            or abs(float(audio.get('duration', 0)) - plan['frame_count'] / 30) > .05):
        raise ValueError('Dynamic workprint requires low-resolution 30 fps picture and complete audio')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], check=True)
    decoded = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0',
        '-vf', 'scale=160:-2,format=gray', '-f', 'framemd5', '-'], text=True)
    hashes = [row.rsplit(',', 1)[-1].strip() for row in decoded.splitlines() if not row.startswith('#')]
    if len(hashes) != plan['frame_count']:
        raise ValueError('Workprint decode differs from the joint picture duration')
    changes = {row['id']: len(set(hashes[row['start_frame']:row['end_frame']]))
               for row in validate_plan['shots']}
    if not set(core_ids) <= changes.keys() or any(changes[sid] < 3 for sid in core_ids):
        raise ValueError('Static workprint cannot confirm moving core shots')
    return dict(media=joint.binding(path), plan_sha256=digest(plan), frame_count=len(hashes),
                distinct_decoded_images=changes, continuous_viewing='UNKNOWN',
                continuous_listening='UNKNOWN')


def require_preview(workprint, receipt, plan, core_ids):
    if receipt != preview_evidence(workprint, plan, core_ids):
        raise ValueError('Dynamic workprint receipt is stale or incomplete')
