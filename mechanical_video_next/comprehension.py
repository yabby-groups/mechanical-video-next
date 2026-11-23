"""Product and comprehension gates. Recorded observations are not audience predictions.

Planning validates traceability; media acceptance additionally requires an independent
reviewer's observations of the exact encoded video and narration. Neither generates PASS.
"""
import math
from pathlib import Path
import json
import subprocess
from scripts.common import filehash, read_input_json

PRODUCT_FIELDS = ('product_id', 'name', 'type', 'model_scope', 'appearance', 'purpose',
                  'operation', 'observable_action', 'mechanism_id')
RELATIONS = {'whole_product', 'operation', 'internal_parts', 'mechanism', 'return_to_function'}
PHENOMENON_RELATIONS = {'phenomenon','conditions','model','causal_test','return_to_question'}
QUESTIONS = ('product', 'operation', 'core_parts', 'power_source', 'transmission',
             'output', 'new_knowledge', 'narration_match')


def enabled(data):
    return data.get('product_policy_version') == 1


def phenomenon(data, research=None):
    """Only explicit new-contract science subjects replace retail identity gates."""
    from .production_contract import enabled as science_contract
    return science_contract(data) and (data.get('subject_kind') or data.get('science',{}).get('subject_kind')
                                      or (research or {}).get('science',{}).get('subject_kind'))=='physical_phenomenon'


def subject_story(data):
    from .production_contract import discovery, nonmechanical_subject
    return discovery(data) and nonmechanical_subject(data)


def _required(row, fields, label):
    if not isinstance(row, dict) or any(not row.get(k) for k in fields):
        raise ValueError(label + ': missing evidence ' + ', '.join(fields))


def _interval(value, outer=None):
    valid = (isinstance(value, list) and len(value) == 2
             and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in value)
             and 0 <= value[0] < value[1])
    return valid and (outer is None or outer[0] <= value[0] < value[1] <= outer[1])


def _binding(row, label):
    path = Path(row.get('path', ''))
    if not path.is_file() or filehash(path) != row.get('sha256'):
        raise ValueError(label + ': missing or stale file binding')
    return path


def validate_product_sources(data, research=None):
    """Validate the observed product or an explicit bounded scientific subject."""
    if subject_story(data) or phenomenon(data,research):
        subject=data.get('subject_identity') or data.get('science',{}).get('subject',{})
        _required(subject,('id','name','scope','model_kind'),'Bounded science subject')
        from .production_contract import subject_kind
        models = {'documented'} if subject_kind(data) == 'documented_technology' else {'conceptual', 'mathematical'}
        if subject['model_kind'] not in models:
            raise ValueError('Unverified simulation cannot identify a scientific subject')
        refs=data.get('subject_references',[])
        if not refs:
            raise ValueError('Located inspected scientific subject sources required')
        sources={}
        from .visual_narrative import located
        for ref in refs:
            _required(ref,('reference_id','supported_claims','evidence'),'Scientific subject reference')
            if ref['reference_id'] in sources:
                raise ValueError('Duplicate subject source')
            located(ref['evidence'])
            sources[ref['reference_id']]=ref
        if research is not None and research.get('science',{}).get('subject') != subject:
            raise ValueError('Scientific model scope differs from verified research')
        return sources
    product = data.get('product_identity', {})
    _required(product, PRODUCT_FIELDS, 'Real product identity')
    if research is not None and product['mechanism_id'] != research.get('mechanism_id'):
        raise ValueError('Product mechanism does not match researched implementation')
    refs = data.get('product_references', (research or {}).get('product_references', []))
    if not isinstance(refs, list) or not refs:
        raise ValueError('Real product reference required; CAD or patent alone is insufficient')
    sources = {}
    real_product = False
    for ref in refs:
        _required(ref, ('reference_id', 'product_id', 'mechanism_id', 'type', 'location', 'observations', 'supported_claims',
                        'evidence_files'), 'Product reference')
        for binding in ref['evidence_files']:
            _binding(binding, 'Observed product source')
        if ref['reference_id'] in sources or ref['product_id'] != product['product_id']:
            raise ValueError('Product reference duplicate or model mixing')
        if ref['mechanism_id'] != product['mechanism_id']:
            raise ValueError('Product source mechanism differs from selected implementation')
        if ref.get('relationship_status') != 'CONFIRMED' or not ref.get('relationship_evidence'):
            raise ValueError('Product reference relationship to actual product unconfirmed')
        observation = ref['observations']
        if ref['type'] == 'video' and observation.get('status') == 'UNKNOWN':
            # Unwatched sources stay disclosed research leads, never evidence
            # for the identity or mechanism being depicted.
            continue
        _required(observation, ('observed_product', 'identified_parts', 'assembly_positions'), 'Actual source observation')
        if not isinstance(observation.get('unknowns'), list):
            raise ValueError('Source unknowns must be explicitly recorded')
        if ref['type'] == 'video':
            if not observation.get('viewed_ranges') or any(not _interval(t) for t in observation['viewed_ranges']):
                raise ValueError('Video reference requires actual viewed ranges')
            _required(observation, ('key_timecodes', 'confirmed_actions', 'viewing_method'), 'Video observation')
            if observation.get('viewing_method') != 'continuous_video' and observation.get('continuous_motion_verified') is True:
                raise ValueError('Screenshots cannot establish continuous source motion')
            for point in observation['key_timecodes']:
                if (not isinstance(point, (int, float)) or isinstance(point, bool)
                        or not math.isfinite(point)
                        or not any(t[0] <= point <= t[1] for t in observation['viewed_ranges'])):
                    raise ValueError('Key source timecodes must fall inside actually observed intervals')
            real_product = real_product or ref.get('depicts_real_product') is True
        elif ref['type'] in {'photo', 'drawing', 'manual', 'patent', 'document', 'cad'}:
            _required(observation, ('figure_or_region',), 'Located source observation')
            if ref['type'] == 'patent':
                _required(observation, ('embodiment',), 'Specific patent implementation')
            real_product = real_product or (ref['type'] in {'photo', 'manual', 'document'}
                and ref.get('depicts_real_product') is True)
            # A documented implementation is a legitimate teaching subject.
            # This identifies that embodiment, never a claimed retail product.
            if product.get('identity_basis') == 'documented_mechanism' and ref['type'] in {'drawing', 'manual', 'patent', 'document'}:
                _required(product, ('teaching_scope',), 'Documented mechanism scope')
                _required(observation, ('embodiment', 'confirmed_actions'), 'Documented mechanism implementation')
                real_product = True
        else:
            raise ValueError('Unknown product source type')
        sources[ref['reference_id']] = ref
    if not real_product:
        raise ValueError('CAD/patent-only evidence cannot identify an actual product')
    return sources


def validate_product_research(research):
    """A research handoff needs a real product, not only a patent embodiment."""
    _required(research, ('mechanism_id',), 'Selected product implementation')
    return validate_product_sources(research, research)


def validate_product_plan(data, research=None):
    """Check specific product evidence and executable cause/effect, never perception."""
    sources = validate_product_sources(data, research)
    if subject_story(data):
        return validate_subject_story(data, sources)
    from .joint_timeline import enabled as joint, shot_narration
    physical=phenomenon(data,research)
    product = data['subject_identity'] if physical else data['product_identity']
    required_relations=PHENOMENON_RELATIONS if physical else RELATIONS
    shots = data.get('shots', [])
    if not shots:
        raise ValueError('Product plan requires shots')
    seen_information, relations = set(), set()
    for shot in shots:
        row = shot.get('comprehension', {})
        _required(row, ('reference_ids', 'product_parts', 'input_action', 'transmission', 'output_action',
                        'visual_evidence', 'new_knowledge', 'necessity', 'causal_link',
                        'recognition_relations', 'verification_method'), 'Shot comprehension ' + str(shot.get('shot_id')))
        if not set(row['reference_ids']) <= sources.keys():
            raise ValueError('Shot comprehension has unbound product reference')
        proof = row.get('causal_evidence', {})
        for stage in ('input_action', 'transmission', 'output_action'):
            location = proof.get(stage, {})
            _required(location, ('reference_id', 'claim', 'position'), 'Located causal evidence ' + stage)
            source = sources.get(location['reference_id'], {})
            if (location['reference_id'] not in row['reference_ids']
                    or location['claim'] != row[stage]
                    or location['claim'] not in source.get('supported_claims', [])):
                raise ValueError('Input/transmission/output must bind actual supported source claims')
            if stage == 'transmission' and source.get('type') == 'photo' and source['observations'].get('internal_structure_visible') is not True:
                raise ValueError('Exterior photo cannot establish internal transmission')
        if row.get('narration') not in (shot_narration(data, shot) or ([None] if joint(data) else [])):
            raise ValueError('Comprehension narration does not match executable shot')
        if row['new_knowledge'] in seen_information:
            raise ValueError('Repeated shot knowledge cannot fill duration')
        seen_information.add(row['new_knowledge'])
        if not set(row['recognition_relations']) <= required_relations:
            raise ValueError('Unknown product recognition relation')
        relations.update(row['recognition_relations'])
        for rid in row['reference_ids']:
            if row.get('requires_continuous_source_motion') and sources[rid]['observations'].get('continuous_motion_verified') is not True:
                raise ValueError('Claim needs actually observed continuous source motion')
    if relations != required_relations:
        raise ValueError('Missing whole product / operation / internal / mechanism / functional return relationship')
    opening = data.get('subject_opening' if physical else 'product_opening', {})
    _required(opening, ('shot_id', 'time_range', 'subject_reveal' if physical else 'product_reveal', 'real_action', 'why_question', 'answer_promise'), 'Subject opening')
    first = shots[0]
    if opening['shot_id'] != first['shot_id'] or not _interval(opening['time_range'], first['time_range']) or opening['time_range'][1] > 5:
        raise ValueError('Product identity, real action and why must appear within first five seconds')
    if not ({'phenomenon','conditions'} if physical else {'whole_product', 'operation'}) <= set(first['comprehension']['recognition_relations']):
        raise ValueError('Opening cannot consist only of abstract moving parts')
    from .production_contract import creative_first
    if creative_first(data):
        decision = data.get('narrative', {}).get('audience_decision', {})
        if opening['why_question'] != decision.get('question'):
            raise ValueError('Comprehension opening must answer the planned everyday question')
        ending_relation = 'return_to_question' if physical else 'return_to_function'
        if ending_relation not in shots[-1]['comprehension']['recognition_relations']:
            raise ValueError('The ending must return to the phenomenon or product in the opening')
    return {'product_id': product['id'] if physical else product['product_id'], 'shots': len(shots), 'status': 'PLAN_VALIDATED_NOT_MEDIA_ACCEPTED'}


def validate_subject_story(data, sources):
    shots = data.get('shots', [])
    opening = data.get('subject_opening', {})
    _required(opening, ('shot_id', 'time_range', 'subject_reveal', 'why_question'), 'Subject opening')
    decision = data.get('narrative', {}).get('audience_decision', {})
    if (not shots or opening['shot_id'] != shots[0]['shot_id']
            or not _interval(opening['time_range'], shots[0]['time_range'])
            or opening['why_question'] != decision.get('question')):
        raise ValueError('Opening must establish the researched subject and audience question')
    for shot in shots:
        row = shot.get('comprehension', {})
        _required(row, ('reference_ids', 'new_knowledge', 'visual_evidence'), 'Subject comprehension')
        if not set(row['reference_ids']) <= sources.keys():
            raise ValueError('Subject comprehension needs a located source')
    return {'subject_id': data['subject_identity']['id'], 'shots': len(shots),
            'status': 'PLAN_VALIDATED_NOT_MEDIA_ACCEPTED'}


def validate_media_qa(blueprint, report, media=None):
    """Fail closed on absent/stale media, unreviewed motion/audio, or self acceptance.

    Blind observations are an independent reviewer proxy, not proof that all real
    viewers understand. File and time coverage are mechanically checked here;
    semantic correctness still requires the recorded independent inspection.
    """
    from .joint_timeline import enabled as joint, shot_narration
    validate_product_plan(blueprint)
    if report.get('independent') is not True or report.get('reviewer_role') != 'QA':
        raise ValueError('Comprehension requires independent QA')
    reviewer = report.get('reviewer_thread_id')
    producers = set(report.get('production_thread_ids', [])) | set(blueprint.get('production_thread_ids', []))
    if not reviewer or not producers or reviewer in producers:
        raise ValueError('Independent reviewer must differ from actual production agents')
    bound = report.get('media', [])
    if not bound or (media is not None and bound != media):
        raise ValueError('Comprehension QA must bind exact delivered media')
    durations = {}
    for item in bound:
        path = _binding(item, 'Actual comprehension media')
        if path.suffix.lower() != '.mp4':
            raise ValueError('Comprehension requires actual MP4, not a CAD or still image')
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        if not {'audio', 'video'} <= {s['codec_type'] for s in info['streams']}:
            raise ValueError('Comprehension media requires video and actual narration audio')
        durations[item['sha256']] = float(info['format']['duration'])
        if abs(durations[item['sha256']] - blueprint['shots'][-1]['time_range'][1]) > .15:
            raise ValueError('Incomplete MP4 cannot establish full comprehension')
    shots = {s['shot_id']: s for s in blueprint['shots']}
    subject = subject_story(blueprint)
    categories = (('subject_recognition', 'story_comprehension', 'viewer_comprehension') if subject else
                  ('product_recognition', 'mechanism_comprehension', 'viewer_comprehension'))
    questions = ('subject', 'question', 'turning_point', 'takeaway', 'narration_match') if subject else QUESTIONS
    recognition = 'subject_identified' if subject else 'product_identified'
    for category in categories:
        rows = report.get(category, [])
        expected = {(sha, sid) for sha in durations for sid in shots}
        if len(rows) != len(expected) or {(r.get('media_sha256'), r.get('shot_id')) for r in rows} != expected:
            raise ValueError('Comprehension QA must cover every actual route and shot: ' + category)
        for row in rows:
            shot = shots[row['shot_id']]
            _required(row, ('observed_object', 'observed_action', 'observed_causal_chain', 'heard_narration', 'evidence', 'answers'), category)
            receipts = row.get('actual_media_evidence')
            if not isinstance(receipts, list) or not receipts:
                raise ValueError('Actual comprehension observations require a bound review receipt')
            # A generic text file, unrelated screenshot or a stale review cannot
            # serve as evidence for arbitrary PASS rows. This is provenance
            # validation; it cannot establish that a reviewer told the truth.
            for binding in receipts:
                receipt_path = _binding(binding, 'Actual comprehension review receipt')
                try:
                    receipt = read_input_json(receipt_path)
                except (ValueError, UnicodeError) as exc:
                    raise ValueError('Comprehension review receipt must be structured observation JSON') from exc
                expected_receipt = dict(reviewer_thread_id=reviewer, category=category)
                for key in ('media_sha256', 'shot_id', 'time_range', 'observed_object', 'observed_action',
                            'observed_causal_chain', 'heard_narration', 'answers', 'continuous_viewing',
                            'listening', 'viewing_method', recognition, 'narration_matches_action'):
                    expected_receipt[key] = row.get(key)
                if category == 'viewer_comprehension':
                    for key in ('blind_observation', 'script_review_order'):
                        expected_receipt[key] = row.get(key)
                if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected_receipt.items()):
                    raise ValueError('Actual comprehension review receipt does not match media, reviewer or observations')
            if (row.get('status') != 'PASS' or row.get('continuous_viewing') is not True or row.get('listening') is not True
                    or row.get('viewing_method') != 'continuous_video'
                    or row.get('time_range') != shot['time_range']):
                raise ValueError('Comprehension FAIL/UNKNOWN or incomplete continuous audiovisual evidence')
            if row.get('narration_matches_action') is not True or row.get(recognition) is not True:
                raise ValueError('Unrecognizable subject or narration/action mismatch')
            if row['heard_narration'] not in (shot_narration(blueprint, shot) or ([None] if joint(blueprint) else [])):
                raise ValueError('Observed narration does not match planned mechanical explanation')
            if row.get('reference_ids') != shot['comprehension']['reference_ids']:
                raise ValueError('Actual media observation must bind planned source evidence')
            if set(row['answers']) != set(questions) or any(not v for v in row['answers'].values()):
                raise ValueError('Complete viewer comprehension answers required')
            if category == 'viewer_comprehension':
                blind = row.get('blind_observation', {})
                if blind.get('script_withheld') is not True or not blind.get('object') or not blind.get('action'):
                    raise ValueError('Blind object/action observation must precede script review')
                if not isinstance(blind.get('observation_order'), int) or not isinstance(row.get('script_review_order'), int) or blind['observation_order'] >= row['script_review_order']:
                    raise ValueError('Blind observation must precede narration/script review')
    return {'status': 'PASS', 'scope': 'independent-reviewer-proxy-only', 'media': bound}
