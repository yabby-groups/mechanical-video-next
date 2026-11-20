"""Visual decisions carried by the existing Blueprint and production config."""
import math
from pathlib import Path
from urllib.parse import urlparse

from scripts.common import ROOT, filehash, probe


VERSION = 2
FIELD = 'visual_policy_version'
ENGINES = {
    'real_use': {'footage'}, 'product_exterior': {'blender', 'footage'},
    'exploded_view': {'blender'}, 'mechanical_cutaway': {'blender'},
    'micro_principle': {'blender', 'remotion'}, 'abstract_phenomenon': {'blender', 'remotion'},
    'parameter_chart': {'remotion'}, 'design_comparison': {'blender', 'remotion', 'footage'},
    'state_change': {'blender', 'remotion', 'footage'},
    'technical_history': {'remotion', 'footage'}, 'annotated_detail': {'blender'},
    'everyday_return': {'blender', 'remotion', 'footage'},
}
CAMERAS = {'establish', 'closeup', 'macro', 'follow', 'reveal', 'cutaway', 'isolate', 'match_cut'}
OBSERVATION_CAMERAS = {
    'establish_structure': 'establish',
    'contact': 'reveal',
    'linkage': 'reveal',
    'compare_states': 'reveal',
    'track_part': 'follow',
    'expose_interior': 'cutaway',
}
FIXED_OBSERVATIONS = {'contact', 'linkage', 'compare_states'}
SCALES = {'wide', 'medium', 'close', 'macro', 'diagram'}
RESEARCH = {'use_context', 'common_misconception', 'science_question', 'causal_relationship',
            'comparison', 'technical_background', 'structure_to_phenomenon', 'everyday_conclusion'}
QA_CHECKS = {'shot_scale', 'camera_angle', 'shot_value', 'knowledge_progression',
             'narration_alignment', 'mechanism_size', 'motion_visibility', 'whole_detail_link',
             'cause_comparison_change', 'material_relevance'}
SHOT_FIELDS = {'knowledge_goal', 'visual_type', 'visual_focus', 'visual_action',
               'render_engine', 'camera', 'transition', 'assets', 'evidence', 'duration',
               'mechanical_role', 'knowledge_ids', 'progression'}


def version(document):
    value = document.get(FIELD, 1)
    if type(value) is not int or value not in {1, VERSION}:
        raise ValueError('Unsupported visual production policy')
    return value


def match_policy(task, document):
    from .joint_timeline import enabled as joint
    if joint(task) != joint(document):
        raise ValueError('Joint timeline policy differs from task creation policy')
    from .production_contract import enabled as science_contract
    if science_contract(task) != science_contract(document):
        raise ValueError('Production contract differs from task creation policy')
    if science_contract(task) and task.get('subject_kind') is not None and task['subject_kind'] != document.get('subject_kind','mechanical_implementation'):
        raise ValueError('Scientific subject kind differs from task creation policy')
    if version(task) != version(document):
        raise ValueError('Visual production policy differs from task creation policy')
    from .knowledge_progression import enabled
    if enabled(task) != enabled(document):
        raise ValueError('Knowledge progression differs from task creation policy')
    from .media_policy import enabled as asset_first
    if asset_first(task) != asset_first(document):
        raise ValueError('Asset-first media differs from task creation policy')


def design_fields(shot):
    from .media_policy import SHOT_FIELDS as MEDIA_FIELDS
    return {key: shot[key] for key in SHOT_FIELDS | MEDIA_FIELDS |
            {'material_limit', 'direction', 'expression_class', 'required_visual_capabilities', 'required_model_capabilities'} if key in shot}


def match_blueprint(blueprint, config):
    """Check the executable timeline against the frozen visual decisions."""
    if len(config['storyboard']) != len(blueprint['shots']):
        raise ValueError('Visual config differs from the frozen shot list')
    from . import joint_timeline as joint
    shared = joint.enabled(blueprint)
    if shared and any(config.get(k) != blueprint.get(k) for k in ('timeline', 'measured_timeline')):
        raise ValueError('Executable timing differs from the frozen joint timeline')
    for row, planned in zip(config['storyboard'], blueprint['shots'], strict=True):
        spec = config['shots'][row['shot']]
        if (row['id'] != planned['shot_id'] or row['seconds'] != planned['duration']
                or row['narration'] != joint.shot_narration(blueprint, planned)
                or row['subtitles'] != (row['narration'] if shared else planned['subtitles'])
                or spec['visual'] != design_fields(planned)
                or any(spec.get(k) != planned.get(k) for k in ('graphic', 'footage', 'split_screen'))):
            raise ValueError(f'Executable visual shot differs from Blueprint: {planned["shot_id"]}')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    return type(value) in {int, float} and math.isfinite(value)


def local_binding(ref):
    path = ROOT / ref.get('path', '')
    if not path.is_file() or filehash(path) != ref.get('sha256'):
        raise ValueError(f'Missing or changed visual source: {path}')
    return path


def located(refs):
    if not isinstance(refs, list) or not refs:
        raise ValueError('Located visual evidence required')
    for ref in refs:
        if not isinstance(ref, dict) or not nonempty(ref.get('position')):
            raise ValueError('A visual evidence locator is required')
        local_binding(ref)


def validate_research(research):
    topics = research.get('visual_research', {})
    if set(topics) != RESEARCH:
        raise ValueError('Visual research must address all eight research angles')
    for key, row in topics.items():
        if row.get('status') == 'SUPPORTED' and nonempty(row.get('finding')):
            located(row.get('evidence'))
        elif row.get('status') in {'UNKNOWN', 'NOT_APPLICABLE'} and nonempty(row.get('reason')):
            continue
        else:
            raise ValueError(f'Visual research needs a supported finding or a recorded limitation: {key}')


def validate_design(plan, *, hybrid=False):
    if not isinstance(plan, dict) or not SHOT_FIELDS <= plan.keys():
        raise ValueError('Incomplete visual narrative shot')
    if any(not nonempty(plan[k]) for k in ('knowledge_goal', 'visual_focus', 'visual_action')):
        raise ValueError('Visual goal, focus and observable action are required')
    kind, engine, role = (plan[k] for k in ('visual_type', 'render_engine', 'mechanical_role'))
    allowed = ENGINES.get(kind, set()) | ({'footage'} if hybrid and kind in {'mechanical_cutaway', 'annotated_detail'} else set())
    if engine not in allowed or role not in {'core', 'support'}:
        raise ValueError('Unsupported visual type, renderer or mechanical role')
    if role == 'core' and engine != 'blender' and not (hybrid and engine == 'footage'):
        raise ValueError('Core mechanical action requires real Blender 3D')
    if kind in {'exploded_view', 'mechanical_cutaway', 'annotated_detail'} and engine != 'blender' and not (hybrid and engine == 'footage'):
        raise ValueError('Mechanical structure needs its verified 3D assembly')
    for field in ('assets', 'knowledge_ids'):
        values = plan[field]
        if not isinstance(values, list) or any(not nonempty(x) for x in values):
            raise ValueError(f'Visual {field} must list named bindings')
    if not plan['knowledge_ids'] or (engine != 'remotion' and not plan['assets']):
        raise ValueError('Knowledge and referenced production assets are required')
    located(plan['evidence'])
    if not number(plan['duration']) or round(plan['duration'] * 30) < 3 or abs(plan['duration'] * 30 - round(plan['duration'] * 30)) > 1e-6:
        raise ValueError('Visual durations need at least three frames on the 30 fps grid')
    camera = plan['camera']
    if not isinstance(camera, dict) or camera.get('scale') not in SCALES or not nonempty(camera.get('angle')):
        raise ValueError('Visual camera needs scale and angle')
    if engine == 'blender':
        planned_camera(plan)
    if engine != 'blender' and 'preset' in camera:
        raise ValueError('Blender presets apply only to Blender shots')
    transition = plan['transition']
    if (not isinstance(transition, dict) or transition.get('kind') not in {'cut', 'match_cut', 'chapter'}
            or not nonempty(transition.get('link'))):
        raise ValueError('Visual transition needs an explanation of the editorial link')
    if transition['kind'] == 'chapter' and not nonempty(transition.get('text')):
        raise ValueError('Chapter transition needs a visible section title')
    progression = plan['progression']
    if not isinstance(progression, dict) or progression.get('kind') not in {'new', 'develop', 'recap'} or not nonempty(progression.get('reason')):
        raise ValueError('Explain how the shot advances or recalls the knowledge')
    if 'material_limit' in plan and not nonempty(plan['material_limit']):
        raise ValueError('Record the unavailable asset and the chosen substitution')


def planned_camera(plan):
    preset = plan['camera'].get('preset')
    observation = plan.get('direction', {}).get('observation')
    if observation is not None:
        from .science_shots import validate_observation_window
        validate_observation_window(observation)
        if observation.get('kind') not in OBSERVATION_CAMERAS:
            raise ValueError('Unknown director observation goal')
    if preset == 'auto':
        if not observation:
            raise ValueError('Automatic camera requires an observation goal with named geometry')
        return OBSERVATION_CAMERAS[observation['kind']]
    if preset not in CAMERAS:
        raise ValueError('Blender camera needs an executable preset')
    return preset


def validate_plan(document):
    """Check the plan before committing to CAD or native rendering."""
    from .media_policy import enabled as asset_first, validate_document
    from . import joint_timeline as joint
    hybrid = asset_first(document)
    shots = document['shots']
    if not isinstance(shots, list) or not shots:
        raise ValueError('Visual Blueprint needs ordered shots')
    shared = joint.enabled(document)
    seen, shot_ids, findings, previous = set(), set(), [], None
    for shot in shots:
        validate_design(shot, hybrid=hybrid)
        ids = set(shot['knowledge_ids'])
        sid = shot.get('shot_id')
        narration = shot.get('narration')
        if (not nonempty(sid) or sid in shot_ids or (not shared and
                (not isinstance(narration, list) or not narration or not all(nonempty(x) for x in narration)))):
            raise ValueError('Visual plan requires shot ID and narration')
        shot_ids.add(sid)
        if not ids - seen and shot['progression']['kind'] == 'new':
            raise ValueError(f'{sid} repeats known facts declared as new')
        if ids - seen and shot['progression']['kind'] == 'recap':
            raise ValueError(f'{sid} introduces new facts during a recap')
        if previous is not None:
            if all(shot[k] == previous[k] for k in ('visual_type', 'visual_focus', 'visual_action', 'camera')):
                findings.append({'shot_id': sid, 'issue': 'repeated_visual', 'review': shot['progression']['reason']})
            elif shot['camera']['scale'] == previous['camera']['scale'] and shot['camera']['angle'] == previous['camera']['angle']:
                findings.append({'shot_id': sid, 'issue': 'repeated_scale_and_angle', 'review': shot['progression']['reason']})
        if not ids - seen:
            findings.append({'shot_id': sid, 'issue': 'reused_knowledge', 'review': shot['progression']['reason']})
        seen |= ids
        previous = shot
    if not any(s['mechanical_role'] == 'core' for s in shots):
        raise ValueError('Mechanical production requires at least one core Blender shot')
    from .knowledge_progression import enabled, validate_timeline
    if enabled(document):
        findings.extend(validate_timeline(shots))
    validate_document(document)
    return findings


def validate_footage(source, *, seconds=None):
    path = local_binding(source)
    license = source.get('license', {})
    url = urlparse(source.get('source_url', ''))
    if (path.suffix.lower() not in {'.mp4', '.mov', '.webm'} or url.scheme not in {'https', 'http', 'file'}
            or (url.scheme != 'file' and not url.netloc) or not nonempty(source.get('credit'))
            or license.get('status') != 'VERIFIED'
            or license.get('editing_and_distribution') is not True
            or not nonempty(license.get('name')) or not nonempty(license.get('holder'))):
        raise ValueError('Footage requires a verified editing/distribution license and attribution')
    located([license.get('proof')])
    start = source.get('start_frame')
    if type(start) is not int or start < 0:
        raise ValueError('Footage start_frame must be a nonnegative 30 fps timeline offset')
    if seconds is not None:
        result = probe(path)
        stream = next((s for s in result['streams'] if s['codec_type'] == 'video'), {})
        duration = stream.get('duration', result['format'].get('duration'))
        if not stream or duration in {None, 'N/A'} or start / 30 + seconds > float(duration) + 1e-6:
            raise ValueError('Licensed source has no video or is shorter than the authored footage interval')
    return path


def validate_graphic(graphic, *, progression=False):
    kind = graphic.get('type')
    if kind == 'angular_comparison' and progression:
        from .knowledge_progression import validate_angular_graphic
        validate_angular_graphic(graphic)
        return
    if kind == 'dual_reel_speed' and progression:
        from .knowledge_progression import validate_dual_reel_graphic
        validate_dual_reel_graphic(graphic)
        return
    if kind not in {'diagram', 'comparison', 'chart', 'timeline', 'data_animation'} or not nonempty(graphic.get('title')):
        raise ValueError('Unknown information graphic or missing title')
    items = graphic.get('items')
    minimum, maximum = (2, 2) if kind == 'comparison' else (2, 4)
    if not isinstance(items, list) or not minimum <= len(items) <= maximum:
        raise ValueError('Information graphic has unsupported item count')
    for item in items:
        if not isinstance(item, dict) or not nonempty(item.get('label')) or not nonempty(item.get('detail')):
            raise ValueError('Information graphic items need labels and details')
        if kind == 'chart' and (not number(item.get('value')) or item['value'] < 0):
            raise ValueError('Bar chart expects finite nonnegative values')
        if kind == 'data_animation':
            keys = item.get('keyframes')
            if (not isinstance(keys, list) or len(keys) < 2
                    or any(not isinstance(k, list) or len(k) != 2 or not all(number(v) for v in k)
                           or min(k) < 0 for k in keys)
                    or keys[0][0] != 0 or any(a[0] >= b[0] for a,b in zip(keys,keys[1:]))):
                raise ValueError('Animated data needs ordered finite nonnegative [seconds,value] keys from zero')
    if kind == 'data_animation':
        presentation = graphic.get('presentation', 'bars')
        if presentation not in {'bars', 'trace'}:
            raise ValueError('Unknown data animation presentation')
        if presentation == 'trace':
            from .science_shots import source_binding
            source_binding(graphic.get('basis'))
            if len(items) != 2 or not nonempty(graphic.get('formula')):
                raise ValueError('Trace compares two series and requires a visible model or measurement boundary')
        peak = max(k[1] for item in items for k in item['keyframes'])
        domain = graphic.get('domainMax', peak)
        if not nonempty(graphic.get('unit')) or not number(domain) or domain <= 0 or domain < peak:
            raise ValueError('Animated data requires units and a positive domain covering all values')
        from .remotion_build import validate_phone_text
        validate_phone_text(graphic['title'],1664)
        for item in items:
            validate_phone_text(item['label'],410)
            for _,value in item['keyframes']:
                if presentation == 'bars':
                    validate_phone_text(f'{value:.2f} {graphic["unit"]}',400)
        if 'formula' in graphic:
            validate_phone_text(graphic['formula'],1664)
    if kind == 'chart' and (not nonempty(graphic.get('unit')) or not any(s['value'] for s in items)):
        raise ValueError('Bar chart requires units and a positive scale')
    if 'formula' in graphic and not nonempty(graphic['formula']):
        raise ValueError('Graphic formula must be a visible string')
    if progression:
        from .knowledge_progression import validate_graphic_text
        validate_graphic_text(graphic)


def validate_execution(shot, *, progression=False, hybrid=False):
    visual = shot['visual']
    validate_design(visual, hybrid=hybrid)
    engine = visual['render_engine']
    if shot.get('seconds') != visual['duration']:
        raise ValueError('Executable and planned visual durations differ')
    if engine == 'blender':
        if shot.get('template') == 'editorial' or 'graphic' in shot or 'footage' in shot:
            raise ValueError('Blender shot cannot be replaced with editorial media')
        camera = visual['camera']
        science = shot.get('science', {})
        required = {
            'closeup': (shot, 'camera_focus_region'), 'macro': (shot, 'camera_focus_region'),
            'follow': (science, 'follow'), 'reveal': (science, 'camera_path'),
            'cutaway': (shot, 'section_plane'), 'isolate': (shot, 'visible_parts'),
            'match_cut': (science, 'camera_path'),
        }
        preset = planned_camera(visual)
        rig_follow = science.get('camera_rig', {}).get('follow')
        if preset in required and not (preset == 'follow' and rig_follow) and not required[preset][0].get(required[preset][1]):
            raise ValueError(f'Camera preset {preset} requires {required[preset][1]}')
        if preset == 'follow' and not rig_follow and shot.get('template') != 'camera_follow':
            raise ValueError('Use the camera_follow template to track the named object')
        if not science.get('basis'):
            raise ValueError('Visual Blender clips require located science and render provenance')
        located(science['basis'])
        planned = {(local_binding(ref).resolve(), ref['position']) for ref in visual['evidence']}
        if any((local_binding(ref).resolve(), ref['position']) not in planned for ref in science['basis']):
            raise ValueError('Blender execution evidence must be included in the planned visual shot')
        if visual['mechanical_role'] == 'core' and science.get('role') == 'structural_detail':
            raise ValueError('Core visual shot cannot use the static detail provenance exemption')
    elif shot.get('template') != 'editorial' or any(k in shot for k in ('science', 'layers', 'tracks', 'mesh_tracks')):
        raise ValueError('Editorial shot cannot masquerade as an executable mechanical scene')
    elif engine == 'footage':
        if 'graphic' in shot:
            raise ValueError('Choose one editorial background per shot')
        validate_footage(shot.get('footage', {}), seconds=shot['seconds'])
        if 'split_screen' in shot:
            sources = shot['split_screen'].get('sources')
            if (not isinstance(sources, list) or len(sources) != 2
                    or sources[0] != shot['footage'] or visual['mechanical_role'] != 'support'):
                raise ValueError('Split screen needs two licensed sources, matching primary footage and supporting role')
            for source in sources:
                validate_footage(source, seconds=shot['seconds'])
    else:
        if 'footage' in shot:
            raise ValueError('Information graphics cannot load arbitrary footage')
        graphic = shot.get('graphic', {})
        validate_graphic(graphic, progression=progression)
        if graphic.get('type') == 'data_animation' and any(item['keyframes'][-1][0] > shot['seconds'] for item in graphic['items']):
            raise ValueError('Data keyframes extend beyond the shot')
        if progression:
            from .knowledge_progression import DYNAMIC
            if any(b['kind'] in DYNAMIC for b in visual['progression'].get('observable', [])) and graphic['type'] not in {'chart', 'angular_comparison', 'dual_reel_speed', 'data_animation'}:
                raise ValueError('Dynamic knowledge requires animated data or geometry, not label reveals')


def configure_blender(shot):
    """Translate named camera choices into the existing Blender renderer inputs."""
    camera = shot['visual']['camera']
    visual = shot['visual']
    preset = planned_camera(visual)
    observation = visual.get('direction', {}).get('observation')
    if observation is not None:
        science = shot.get('science')
        if science is None:
            raise ValueError('Observation goals require a native science shot')
        science['observation_window'] = {key: observation[key] for key in ('anchors', 'progress')}
        if camera['preset'] == 'auto' and observation['kind'] in FIXED_OBSERVATIONS:
            path = science.get('camera_path')
            if not path:
                raise ValueError('Fixed observation requires an authored camera path with a useful first pose')
            pose = {k: v for k, v in path[0].items() if k != 'follow_weight'}
            science['camera_path'] = [dict(pose, progress=t) for t in (0, 1)]
            science.pop('camera_path_follow', None)
            science.pop('camera_framing', None)
            science.get('camera_rig', {}).pop('follow', None)
    if preset in {'closeup', 'macro'} and 'focus_region' in camera:
        shot['camera_focus_region'] = camera['focus_region']
    lighting = shot.get('studio_lighting', {}).copy()
    if preset in {'establish', 'macro', 'follow', 'reveal', 'match_cut'}:
        lighting['camera_push'] = False
    if preset == 'isolate':
        for key, value in {'key_strength': 1.1, 'fill_strength': .78}.items():
            lighting.setdefault(key, value)
    if lighting:
        shot['studio_lighting'] = lighting


def editorial_props(shot):
    result = {}
    if 'graphic' in shot:
        result['graphic'] = shot['graphic']
    if 'footage' in shot:
        result['footage'] = {'credit': shot['footage']['credit'], 'startFrame': shot['footage']['start_frame']}
    transition = shot['visual']['transition']
    if transition['kind'] == 'chapter':
        result['chapter'] = transition['text']
    return result


def validate_review(review, shot_ids, *, acceptance):
    rows = review if isinstance(review, dict) else {}
    if set(rows) != set(shot_ids):
        raise ValueError('Visual QA must cover the exact Blueprint timeline')
    for sid, row in rows.items():
        if set(row) != QA_CHECKS:
            raise ValueError(f'{sid}: incomplete visual QA')
        for key, check in row.items():
            status = check.get('status')
            if status not in {'PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE'} or not nonempty(check.get('observation')):
                raise ValueError(f'{sid}: missing visual observation for {key}')
            if key in {'shot_value', 'knowledge_progression', 'narration_alignment', 'material_relevance'} and status == 'NOT_APPLICABLE':
                raise ValueError(f'{sid}: {key} applies to every shot')
            if status == 'FAIL' or (acceptance and status == 'UNKNOWN'):
                raise ValueError(f'{sid}: visual QA {status} for {key}')
