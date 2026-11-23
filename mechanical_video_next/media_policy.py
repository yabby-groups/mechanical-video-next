"""Asset-first policy inside the existing Blueprint and production pipeline.

Missing version means historical behavior. A cached file never grants rights.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess

from scripts.common import ROOT, filehash, probe, read_input_json, writejson

FIELD = 'media_policy_version'
VERSION = 1
SOURCE_TYPES = {'REFERENCE_ONLY', 'LICENSED_REUSE', 'OWNED', 'GENERATED'}
SHOT_FIELDS = {'source_type', 'source_url', 'source_time_range', 'license_status',
               'usage_restrictions', 'selected_asset', 'reuse_decision', 'generation_required',
               'license', 'credit', 'content_verified', 'matching', 'mechanism_verification'}
REQUIRED = SHOT_FIELDS - {'mechanism_verification'}
QA_CHECKS = {'license_compliance', 'source_correspondence', 'knowledge_service',
             'mechanical_evidence', 'continuity', 'visual_quality', 'narration_alignment'}
COPYRIGHT_CHECKS = {'rights_chain', 'current_use_scope', 'attribution', 'reference_only_exclusion'}
ORIGINALITY_CHECKS = {'independent_research', 'original_narration', 'knowledge_structure',
    'storyboard_design', 'visual_arrangement', 'reference_expression_distance',
    'transformations_not_originality', 'science_explanation'}


def enabled(document):
    value = document.get(FIELD, 0)
    if type(value) is not int or value not in {0, VERSION}:
        raise ValueError('Unsupported asset-first media policy')
    if value and document.get('visual_policy_version') != 2:
        raise ValueError('Asset-first media requires explicit visual policy 2')
    return value == VERSION


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': filehash(path)}


def bound(ref):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError('A local media/source binding is required')
    path = (ROOT / ref['path']).resolve()
    if not path.is_file() or filehash(path) != ref.get('sha256'):
        raise ValueError('Missing or changed asset-first media/source binding')
    return path


def interval(value):
    return (isinstance(value, list) and len(value) == 2
            and all(type(x) in {int, float} and math.isfinite(x) for x in value)
            and 0 <= value[0] < value[1])


def validate_rights(row):
    rights = row.get('license', {})
    if (row.get('source_type') not in SOURCE_TYPES - {'REFERENCE_ONLY'}
            or row.get('license_status') != 'VERIFIED' or rights.get('status') != 'VERIFIED'
            or rights.get('editing_and_distribution') is not True
            or rights.get('commercial_use') is not True
            or not all(isinstance(rights.get(k), str) and rights[k].strip() for k in ('name', 'holder'))
            or not isinstance(row.get('credit'), str) or not row['credit'].strip()):
        raise ValueError('Formal media requires verified commercial editing/distribution rights and credit')
    restrictions = row.get('usage_restrictions')
    if not isinstance(restrictions, list) or any(not isinstance(x, str) or not x.strip() for x in restrictions):
        raise ValueError('Media usage restrictions must be explicit')
    license_name = rights['name'].upper()
    if any(token in license_name for token in ('-NC', '-ND', 'NONCOMMERCIAL', 'NO DERIVATIVES')):
        raise ValueError('Noncommercial/no-derivatives assets cannot enter commercial edited media')
    proof = rights.get('proof')
    bound(proof)
    if not isinstance(proof.get('position'), str) or not proof['position'].strip():
        raise ValueError('License evidence needs an inspected location')


def validate_shot(row, seconds, *, footage=None, graphic=None, flexible=False):
    if not REQUIRED <= row.keys():
        raise ValueError('Incomplete asset-first shot decision: ' + ', '.join(sorted(REQUIRED - row.keys())))
    if not row.get('knowledge_goal') or not row.get('visual_type') or row['content_verified'] is not True:
        raise ValueError('Selected media must serve a verified knowledge goal')
    validate_rights(row)
    match = row['matching']
    if not isinstance(match, dict):
        raise ValueError('Record the asset decision')
    ranks = []
    if not flexible:
        if not isinstance(match.get('attempts'), list) or not match['attempts']:
            raise ValueError('Record ordered local-first asset matching before generation')
        ranks = [a.get('priority') for a in match['attempts']]
        if any(type(x) is not int or not 1 <= x <= 5 for x in ranks) or ranks != sorted(ranks):
            raise ValueError('Asset matching must follow the five local-first source tiers')
    generate = row['generation_required']
    reuse_model = row['reuse_decision'] == 'REUSE_MODEL'
    reuse_template = row['reuse_decision'] == 'REUSE_TEMPLATE'
    if type(generate) is not bool or row['reuse_decision'] not in ({'GENERATE','REUSE_MODEL','REUSE_TEMPLATE'} if generate else {'REUSE'}):
        raise ValueError('Reuse decision and generation_required disagree')
    if reuse_model or reuse_template:
        model = bound(row['selected_asset'])
        suffixes = {'.blend','.glb','.step','.stp','.stl','.obj'} if reuse_model else {'.tsx','.ts'}
        if (row.get('render_engine') != ('blender' if reuse_model else 'remotion') or row['source_time_range'] is not None
                or model.suffix.lower() not in suffixes):
            raise ValueError('Reusable input must match its native animation renderer')
        if 'receipt' not in match:
            raise ValueError('Model reuse requires the actual asset matching receipt')
        receipt = read_input_json(bound(match['receipt']))
        entries = receipt.get('shots', {})
        sid = match.get('receipt_shot', row.get('shot_id'))
        entry = entries.get(sid,{}) if isinstance(entries,dict) else next((e for e in entries if e.get('shot_id') == sid),{})
        result = entry.get('result',entry.get('match',{}))
        if (result.get('reuse_decision') != row['reuse_decision']
                or result.get('selected_asset',{}).get('sha256') != row['selected_asset']['sha256']
                or result.get('license') != row['license']):
            raise ValueError('Model input differs from the actual matched source')
        return row
    if generate:
        if row['source_type'] != 'GENERATED' or row['selected_asset'] is not None or row['source_time_range'] is not None:
            raise ValueError('Generated shots cannot pretend to reuse an existing video')
        reason = match.get('generation_reason')
        if flexible and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError('Explain why this shot calls for original production')
        if not flexible and (set(ranks) != {1, 2, 3, 4, 5} or not reason):
            raise ValueError('Generation requires recorded gaps in all existing material tiers')
        if not flexible and any(a.get('status') == 'NOT_SEARCHED' or 'not searched' in str(a.get('result', '')).lower()
               for a in match['attempts']):
            raise ValueError('Unsearched source tiers cannot automatically authorize generation')
    else:
        src = bound(row['selected_asset'])
        if 'receipt' in match:
            receipt = read_input_json(bound(match['receipt']))
            entries = receipt.get('shots', {})
            sid = match.get('receipt_shot', row.get('shot_id'))
            entry = (entries.get(sid, {}) if isinstance(entries, dict)
                     else next((e for e in entries if e.get('shot_id') == sid), {}))
            result = entry.get('result', entry.get('match', {}))
            if (result.get('reuse_decision') != 'REUSE'
                    or result.get('selected_asset', {}).get('sha256') != row['selected_asset']['sha256']
                    or result.get('license') != row['license']):
                raise ValueError('Selected source differs from the bound library matching receipt')
        if row.get('render_engine') == 'remotion':
            if (row.get('mechanical_role') == 'core' or row['source_time_range'] is not None or not row['source_url']
                    or src.suffix != '.json' or graphic is None or read_input_json(src) != graphic):
                raise ValueError('Reused native information animation must bind its exact graphic definition')
            return row
        if not row['source_url'] or not interval(row['source_time_range']):
            raise ValueError('Reused media requires source URL and exact source interval')
        start, end = row['source_time_range']
        if abs(end - start - seconds) > 1 / 30000:
            raise ValueError('Reuse interval must match the shot; no looping or slow padding')
        info = probe(src)
        video = next((s for s in info['streams'] if s['codec_type'] == 'video'), {})
        if (video.get('width', 0) < 1920 or video.get('height', 0) < 1080
                or end > float(info['format']['duration']) + 1e-5):
            raise ValueError('Reused video must meet native HD quality and source duration')
        if footage is not None and (bound(footage) != src or abs(footage.get('start_frame', -1)/30 - start) > 1e-7
                                    or footage.get('license') != row['license'] or footage.get('credit') != row['credit']):
            raise ValueError('Executable footage differs from the selected licensed interval')
    if row.get('mechanical_role') == 'core' and row.get('render_engine') == 'footage':
        verification = row.get('mechanism_verification', {})
        if (verification.get('status') != 'PASS' or verification.get('independent') is not True
                or verification.get('continuous_video') is not True
                or not verification.get('reviewer_thread_id') or not verification.get('observation')
                or verification.get('source_sha256') != row['selected_asset']['sha256']
                or verification.get('time_range') != row['source_time_range']
                or not set(row.get('knowledge_ids', [])) <= set(verification.get('confirmed_knowledge_ids', []))
                or verification.get('real_mechanism') is not True):
            raise ValueError('Core footage needs independent observed real-mechanism evidence for this exact source interval')
        bound(verification.get('report'))
    return row


def validate_document(document):
    if not enabled(document):
        return
    from .production_contract import flexible_story
    flexible = flexible_story(document)
    shots = document.get('shots', {})
    if isinstance(shots, dict):
        rows = [(dict(shots[r['shot']]['visual'], shot_id=r['id']), shots[r['shot']])
                for r in document.get('storyboard', [])]
    else:
        rows = [(s, s) for s in shots]
    used = set()
    for row, execution in rows:
        validate_shot(row, row['duration'], footage=execution.get('footage'),
                      graphic=execution.get('graphic'), flexible=flexible)
        supplemental_sources(execution, row['duration'])
        if not row['generation_required']:
            key = (row['selected_asset']['sha256'], tuple(row['source_time_range'] or []))
            if key in used and not flexible:
                raise ValueError('Repeated source interval cannot fill the timeline')
            used.add(key)


def supplemental_sources(shot, seconds):
    """Every visible split source has its own rights and exact muted interval."""
    if 'split_screen' not in shot:
        return []
    from .visual_narrative import validate_footage
    sources = shot['split_screen'].get('sources')
    if not isinstance(sources, list) or len(sources) != 2 or sources[0] != shot.get('footage'):
        raise ValueError('Split-screen sources must include the exact primary footage')
    result=[]
    for source in sources:
        validate_footage(source, seconds=seconds)
        rights=dict(source, source_type=source.get('source_type','LICENSED_REUSE'),
                    license_status=source.get('license_status', source.get('license',{}).get('status')),
                    usage_restrictions=source.get('usage_restrictions',[]))
        validate_rights(rights)
        result.append({**rights, 'source_time_range':[source['start_frame']/30,source['start_frame']/30+seconds],
                       'source_audio':'muted'})
    return result


def write_manifest(path, final, config, build_proof):
    """Bind the complete hybrid timeline to its actual existing Remotion build."""
    validate_document(config)
    proof = json.loads(Path(build_proof).read_text())
    from . import joint_timeline as joint
    shared = joint.enabled(config)
    rows, cursor = [], 0
    for chapter, segment in zip(config['storyboard'], proof['build']['segments'], strict=True):
        spec = config['shots'][chapter['shot']]
        visual = spec['visual']
        frames = round(chapter['seconds'] * 30)
        row = {k: visual[k] for k in SHOT_FIELDS | {'knowledge_goal', 'visual_type', 'mechanical_role', 'knowledge_ids'} if k in visual}
        row.update(shot_id=chapter['id'], render_engine=visual['render_engine'],
                   output_time_range=[cursor / 30, (cursor + frames) / 30],
                   frame_range=[cursor, cursor + frames],
                   source_audio='muted',
                   production_method=visual['render_engine'])
        if shared:
            row['source_start_frame'] = segment['source_start_frame']
        else:
            row['audio'] = segment['audio']
        if 'render_output' in segment:
            row['render_output'] = segment['render_output']
        if 'split_screen' in spec:
            row['supplemental_sources'] = supplemental_sources(spec, chapter['seconds'])
        rows.append(row)
        cursor += frames
    manifest = {FIELD: VERSION, 'visual_policy_version': 2, 'schema_version': 1,
                'media_contract': 'asset-first-hybrid-v1', 'media': binding(final),
                'build_proof': binding(build_proof), 'shots': rows, 'frame_count': cursor,
                'source_audio_policy': 'muted', 'formal_acceptance': False,
                'original_3d_only_acceptance': False}
    if shared:
        manifest.update({joint.FIELD: joint.VERSION, 'narration': proof['build']['narration']})
    for key in ('production_contract_version','production_contract','knowledge_progression_version','subject_kind'):
        if key in config:
            manifest[key]=config[key]
    writejson(path, manifest)
    validate_manifest(path)
    record_uses(config, binding(final))
    return manifest


def record_uses(config, media):
    """Append source usage to the same local index after a real composition exists."""
    from .reference_library import record_media_use
    uses = []
    for chapter in config['storyboard']:
        visual = config['shots'][chapter['shot']]['visual']
        matching = visual['matching']
        if visual['reuse_decision'] == 'GENERATE' or 'receipt' not in matching:
            continue
        receipt = json.loads(bound(matching['receipt']).read_text())
        entries = receipt.get('shots', {})
        sid = matching.get('receipt_shot', chapter['id'])
        entry = (entries.get(sid, {}) if isinstance(entries, dict)
                 else next((r for r in entries if r['shot_id'] == sid), {}))
        result = entry.get('result', entry.get('match', {}))
        selected = result.get('selected', {})
        if not selected:
            continue
        blob = Path(result['selected_asset']['path']).resolve()
        if (blob.parent.name != visual['selected_asset']['sha256']
                or blob.parent.parent.name != 'blobs' or blob.parent.parent.parent.name != 'media'):
            raise ValueError('Matching receipt does not point to the existing content library')
        uses.append(record_media_use(selected['record'], config['id'], chapter['id'],
                    visual['source_time_range'], media, visual['knowledge_ids'], blob.parents[3]))
    return uses


def validate_manifest(path, media=None):
    doc = json.loads(Path(path).read_text())
    if (not enabled(doc) or doc.get('media_contract') != 'asset-first-hybrid-v1'
            or doc.get('original_3d_only_acceptance') is not False):
        raise ValueError('A hybrid manifest cannot claim original 3D-only acceptance')
    final = bound(doc['media'])
    if media is not None and binding(final) != media:
        raise ValueError('Hybrid manifest belongs to another final media')
    proof = json.loads(bound(doc['build_proof']).read_text())
    if proof['media'] != doc['media'] or proof.get('media_contract') != 'asset-first-hybrid-v1':
        raise ValueError('Hybrid manifest needs the exact bound hybrid build')
    from .provenance import verify_remotion_inputs
    verify_remotion_inputs(proof['build'])
    config = proof['build']['visual_config']
    from . import joint_timeline as joint
    shared = joint.enabled(config)
    if shared and doc.get('narration') != proof['build']['narration']:
        raise ValueError('Hybrid manifest narration differs from the joint master')
    from .visual_narrative import match_policy
    match_policy(config, doc)
    validate_document(config)
    if len(doc['shots']) != len(config['storyboard']):
        raise ValueError('Hybrid sources must cover every output shot')
    cursor = 0
    for row, chapter, segment in zip(doc['shots'], config['storyboard'], proof['build']['segments'], strict=True):
        supplement = supplemental_sources(config['shots'][chapter['shot']], chapter['seconds'])
        if row.get('supplemental_sources',[]) != supplement:
            raise ValueError('Complete media manifest must bind every split-screen source and rights interval')
        expected = config['shots'][chapter['shot']]['visual']
        if expected['reuse_decision'] == 'REUSE_MODEL':
            native = next((s for s in proof['shots'] if s['shot_id'] == chapter['shot']), {})
            if not any(a.get('sha256') == expected['selected_asset']['sha256'] for a in native.get('model_assets', [])):
                raise ValueError('Native render does not bind the matched reusable model input')
        if expected['reuse_decision'] == 'REUSE_TEMPLATE' and not any(
                r['sha256'] == expected['selected_asset']['sha256'] for r in proof['build']['render_sources']):
            raise ValueError('Rendered visualization does not bind the matched native template source')
        if any(row.get(k) != expected.get(k) for k in SHOT_FIELDS | {'knowledge_goal', 'visual_type', 'mechanical_role', 'knowledge_ids', 'render_engine'}):
            raise ValueError('Hybrid source decisions differ from the bound executable build')
        count = round(chapter['seconds'] * 30)
        if (row['shot_id'] != chapter['id'] or row['frame_range'] != [cursor, cursor+count]
                or row['output_time_range'] != [cursor/30, (cursor+count)/30]
                or row.get('source_audio') != 'muted'
                or row.get('render_output') != segment.get('render_output')):
            raise ValueError('Hybrid timeline has changed sources, gaps or overlaps')
        if shared:
            if row.get('source_start_frame') != segment['source_start_frame'] or 'audio' in row:
                raise ValueError('Hybrid shot must bind its exact source offset and use the joint master')
        else:
            if row['audio'] != segment['audio']:
                raise ValueError('Hybrid shot audio differs from the build')
            bound(row['audio'])
        cursor += count
    if cursor != doc['frame_count'] or cursor != proof['build']['frame_count']:
        raise ValueError('Hybrid timeline frame count mismatch')
    stream = next(s for s in probe(final)['streams'] if s['codec_type'] == 'video')
    num, den = map(int, stream['avg_frame_rate'].split('/'))
    if [stream['width'], stream['height'], num/den, int(stream['nb_frames'])] != [1920,1080,30,cursor]:
        raise ValueError('Hybrid final must be 1920x1080/30 with exact continuous timeline')
    return doc


def validate_qa(qa, manifest, *, acceptance, original_inputs=None, technical_audio=False):
    doc = validate_manifest(manifest)
    review = qa.get('hybrid_media_review', {})
    if review.get('manifest') != binding(manifest) or review.get('media') != doc['media']:
        raise ValueError('Hybrid QA must bind exact media and complete source manifest')
    if set(review.get('shots', {})) != {r['shot_id'] for r in doc['shots']}:
        raise ValueError('Hybrid QA must cover every shot')
    for sid, checks in review['shots'].items():
        if set(checks) != QA_CHECKS:
            raise ValueError('Incomplete hybrid material QA: ' + sid)
        for check in checks.values():
            if (not check.get('observation') or check.get('status') not in {'PASS','FAIL','UNKNOWN'}
                    or check['status'] == 'FAIL' or (acceptance and check['status'] != 'PASS')):
                raise ValueError('Hybrid QA FAIL/UNKNOWN prevents acceptance')
    if acceptance and (review.get('continuous_video') is not True
                       or (not technical_audio and review.get('listening') is not True)):
        raise ValueError('Hybrid acceptance requires actual continuous viewing and listening')
    # Lawful reuse and original expression are independent findings. No asset ratio grants either.
    for name, required in (('copyright_review', COPYRIGHT_CHECKS),
                           ('original_expression_review', ORIGINALITY_CHECKS)):
        section = qa.get(name, {})
        if section.get('media') != doc['media'] or section.get('manifest') != binding(manifest):
            raise ValueError(f'{name} must bind the exact media and source manifest')
        if section.get('independent') is not True or not section.get('reviewer_thread_id'):
            raise ValueError(f'{name} requires an independent reviewer')
        checks = section.get('checks', {})
        if set(checks) != required:
            raise ValueError(f'Incomplete {name}')
        for check in checks.values():
            if (not check.get('observation') or check.get('status') not in {'PASS','FAIL','UNKNOWN'}
                    or check['status'] == 'FAIL' or (acceptance and check['status'] != 'PASS')):
                raise ValueError(f'{name} FAIL/UNKNOWN prevents acceptance')
        if name == 'original_expression_review':
            inputs = section.get('input_bindings', {})
            for ref in inputs.values():
                bound(ref)
            if acceptance and (not {'research','script','blueprint'} <= inputs.keys()
                    or original_inputs is None or any(inputs.get(k) != v for k,v in original_inputs.items())):
                raise ValueError('Original expression review must bind this task research, script and knowledge/storyboard design')
            if acceptance and section.get('ratio_used_as_originality_verdict') is not False:
                raise ValueError('Originality cannot be established by a material percentage')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--decode', action='store_true')
    args = parser.parse_args()
    doc = validate_manifest(args.manifest)
    if args.decode:
        subprocess.run(['ffmpeg','-v','error','-i',str(bound(doc['media'])),'-f','null','-'],check=True)
    print(json.dumps({'status':'TECHNICAL_PASS_UNACCEPTED', 'media':doc['media']},ensure_ascii=False))


if __name__ == '__main__':
    main()
