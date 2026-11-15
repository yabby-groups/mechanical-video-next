"""Reference-first contracts for new tasks only; no rendering or CAD generation.

These gates validate recorded evidence and bindings. They do not claim to have
watched a source, reviewed geometry, or acquired rights on an agent's behalf.
"""
import hashlib
import json
from pathlib import Path
from .growth import finite

STRATEGIES = ('existing-media', 'verified-existing', 'autonomous-cad')
CONTENT_CHECKS = ('reliable_sources', 'specific_mechanism', 'no_model_mixing',
                  'supported_knowledge', 'demonstrable_motion', 'model_matches',
                  'content_duration', 'no_invented_parts', 'executable_shots')


def _required(row, fields, label):
    if not isinstance(row, dict) or any(not row.get(k) for k in fields):
        raise ValueError(label + ' missing required evidence fields')


def validate_research(research):
    _required(research, ('mechanism_id', 'references'), 'Research')
    refs = {}
    for ref in research['references']:
        _required(ref, ('id', 'location', 'source_name', 'author', 'type', 'acquired_at',
                        'viewed_scope', 'structure_evidence', 'motion_evidence',
                        'license', 'usable_content', 'mechanism_id'), 'Reference')
        if ref['id'] in refs or ref['mechanism_id'] != research['mechanism_id']:
            raise ValueError('Duplicate reference or mixed mechanism/model')
        if 'unknowns' not in ref or 'conflicts' not in ref:
            raise ValueError('Reference must disclose unknowns and conflicts')
        scope = ref['viewed_scope']
        _required(scope, ('status', 'evidence'), 'Actual viewing scope')
        expected = {'video': 'VIDEO_INSPECTED', 'drawing': 'DRAWING_INSPECTED',
                    'patent': 'DOCUMENT_READ', 'manual': 'DOCUMENT_READ',
                    'document': 'DOCUMENT_READ', 'cad': 'MODEL_INSPECTED'}
        if ref['type'] not in expected:
            raise ValueError('Appearance-only or unknown reference cannot prove internal mechanics')
        if scope['status'] not in {'VIDEO_INSPECTED', 'DRAWING_INSPECTED', 'DOCUMENT_READ', 'MODEL_INSPECTED'}:
            raise ValueError('Title, cover or metadata cannot prove mechanics')
        if scope['status'] != expected[ref['type']]:
            raise ValueError('Actual viewing status must match reference type')
        if ref['type'] == 'video':
            ranges = scope.get('time_ranges', [])
            if not ranges or any(len(t) != 2 or not all(finite(v) for v in t) or not 0 <= t[0] < t[1] for t in ranges):
                raise ValueError('Video requires actual viewed time ranges')
            _required(scope, ('confirmed_actions',), 'Video')
        if ref['type'] == 'drawing':
            _required(scope, ('drawing_numbers', 'parts', 'connections', 'dimensions'), 'Drawing')
        if ref['type'] == 'patent':
            _required(scope, ('embodiment', 'figure_numbers'), 'Patent implementation')
        if ref.get('unresolved_core_conflict') is not False:
            raise ValueError('Resolve core structural conflicts before modeling')
        refs[ref['id']] = ref
    return refs


def select_asset_strategy(research, candidates):
    """Select the highest qualified and legally usable available candidate.

    An investigated but unavailable category is retained with a reason. A title
    alone, an unknown license, or an appearance-only source never qualifies.
    """
    refs = validate_research(research)
    if not isinstance(candidates, list):
        raise ValueError('Asset search candidates required')
    for strategy in STRATEGIES:
        rows = [c for c in candidates if c.get('strategy') == strategy]
        if not rows:
            raise ValueError('Record search result for asset category: ' + strategy)
        for row in rows:
            _required(row, ('reason',), 'Asset candidate')
            if row.get('qualified') is not True:
                continue
            _required(row, ('id', 'source_ids', 'mechanism_id', 'validation_evidence'), 'Qualified candidate')
            if (row['mechanism_id'] != research['mechanism_id'] or not set(row['source_ids']) <= refs.keys()
                    or row.get('legal_use') is not True or row.get('content_match') is not True):
                raise ValueError('Qualified asset must match mechanism, evidence and permitted use')
            if strategy != 'autonomous-cad' and not row.get('source_files'):
                raise ValueError('Existing asset requires actual source files')
            return strategy, row['id']
    raise ValueError('Insufficient evidence: retain research, narrow scope; never invent internal structure')


def validate_asset(research, asset):
    selected = select_asset_strategy(research, asset.get('candidates'))
    if (asset.get('strategy'), asset.get('selected_candidate_id')) != selected:
        raise ValueError('Asset must prefer qualified legal reuse before new CAD')
    candidate = next(c for c in asset['candidates'] if c.get('id') == selected[1])
    if selected[0] != 'autonomous-cad':
        for source in candidate['source_files']:
            path = Path(source.get('path', ''))
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source.get('sha256'):
                raise ValueError('Existing asset source missing or changed')
        if selected[0] == 'verified-existing' and asset.get('model') not in candidate['source_files']:
            raise ValueError('Selected assembly must bind the actual asset model')
    if asset.get('mechanism_id') != research['mechanism_id']:
        raise ValueError('Asset mechanism differs from verified research')
    if 'model_source' not in asset or 'substantive_repairs' not in asset:
        raise ValueError('Record model source and substantive repair history')
    for repair in asset['substantive_repairs']:
        _required(repair, ('cause', 'evidence', 'changed_assumption', 'result'), 'Repair')
        if repair['cause'] not in {'reference', 'model', 'assembly', 'animation'}:
            raise ValueError('Classify repair cause before rebuilding')
    return selected


def validate_plan(blueprint, research, asset):
    refs = validate_research(research)
    validate_asset(research, asset)
    _required(blueprint, ('core_question', 'evidence_map', 'shots', 'content_timing'), 'Blueprint')
    shots = {s['shot_id']: s for s in blueprint['shots']}
    claims = {}
    for row in blueprint['evidence_map']:
        _required(row, ('knowledge_id', 'conclusion', 'source_ids', 'reference_locations',
                        'parts', 'actions', 'usable_material', 'shot_ids', 'verification_method'), 'Evidence map')
        if (row['knowledge_id'] in claims or not set(row['source_ids']) <= refs.keys()
                or not set(row['shot_ids']) <= shots.keys() or row.get('verified') is not True):
            raise ValueError('Unsupported, duplicate or unbound mechanical conclusion')
        for location in row['reference_locations']:
            _required(location, ('source_id', 'position'), 'Claim source position')
            if location['source_id'] not in row['source_ids']:
                raise ValueError('Claim location must bind its source')
        if set(row['source_ids']) != {p['source_id'] for p in row['reference_locations']}:
            raise ValueError('Every source requires a specific claim location')
        for sid in row['shot_ids']:
            if row['knowledge_id'] not in shots[sid].get('knowledge_ids', []):
                raise ValueError('Evidence map must bind verified knowledge in both directions')
        claims[row['knowledge_id']] = row
    for shot in shots.values():
        ids = shot.get('knowledge_ids', [])
        if not ids or not set(ids) <= claims.keys() or any(shot['shot_id'] not in claims[k]['shot_ids'] for k in ids):
            raise ValueError('Every narrated shot must bind verified knowledge')
    end = 0
    for shot in blueprint['shots']:
        interval = shot.get('time_range', [])
        if (len(interval) != 2 or not all(finite(t) for t in interval)
                or interval[0] != end or interval[1] <= interval[0]):
            raise ValueError('Evidence shots require contiguous executable time_range')
        end = interval[1]
    if end != blueprint.get('duration_seconds') or len(shots) != len(blueprint['shots']):
        raise ValueError('Evidence timeline must match duration and unique shot IDs')
    timing = blueprint['content_timing']
    _required(timing, ('basis', 'chapters'), 'Content timing')
    if timing.get('status') != 'PASS' or timing.get('measured_narration_seconds') is None:
        raise ValueError('Content insufficient or narration not measured; do not lock duration')
    duration = blueprint.get('duration_seconds')
    if (not finite(duration) or not 120 <= duration <= 300
            or not finite(timing['measured_narration_seconds'])
            or not 0 < timing['measured_narration_seconds'] <= duration):
        raise ValueError('Knowledge-supported duration must be 120–300 seconds')
    covered = set()
    for chapter in timing['chapters']:
        _required(chapter, ('id', 'knowledge_ids', 'new_information', 'duration_reason'), 'Chapter')
        if not set(chapter['knowledge_ids']) <= claims.keys() or covered.intersection(chapter['knowledge_ids']):
            raise ValueError('Repeated or unsupported chapter knowledge cannot fill duration')
        covered.update(chapter['knowledge_ids'])
    if covered != claims.keys():
        raise ValueError('Content timing must cover verified knowledge')
    return {'knowledge_points': len(claims), 'duration_seconds': duration,
            'asset_strategy': asset['strategy']}


def plan_digest(blueprint, research, asset):
    return hashlib.sha256(json.dumps([blueprint, research, asset], sort_keys=True,
                                    separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def validate_route_plan(path, binding):
    path = Path(path)
    if (Path(binding.get('path', '')).resolve() != path.resolve()
            or binding.get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
        raise ValueError('Route plan must bind exact independently reviewed commands and inputs')
    plan = json.loads(path.read_text())
    produced = set()
    external = {str(Path(p).resolve()) for p in plan.get('prerequisite_inputs', [])}
    for step in plan['steps']:
        external.update(str(Path(p).resolve()) for p in step.get('inputs', [])
                        if str(Path(p).resolve()) not in produced)
        produced.update(str(Path(p).resolve()) for p in step['outputs'])
    actual = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in external}
    if binding.get('input_hashes') != actual:
        raise ValueError('Route plan external inputs differ from independent review')


def validate_preproduction(blueprint, research, asset, qa):
    result = validate_plan(blueprint, research, asset)
    if (qa.get('reviewer_role') != 'QA' or qa.get('independent') is not True
            or qa.get('plan_sha256') != plan_digest(blueprint, research, asset)):
        raise ValueError('Independent QA must bind exact reference, asset and blueprint versions')
    checks = qa.get('content_checks', {})
    if any(i.get('severity') in {'blocking', 'critical', 'major', 'error'} for i in qa.get('issues', [])):
        raise ValueError('Unresolved blocking content QA defects')
    for key in CONTENT_CHECKS:
        row = checks.get(key, {})
        if row.get('status') != 'PASS' or not row.get('evidence'):
            raise ValueError('Preproduction authenticity FAIL/UNKNOWN: ' + key)
    return result


def validate_final_report(report, media):
    _required(report, ('media', 'primary_references', 'model_material_sources'), 'Reference report')
    for key in ('teaching_approximations', 'duration_added_knowledge', 'removed_repetition'):
        if not isinstance(report.get(key), list):
            raise ValueError('Reference report requires list: ' + key)
    if report['media'] != media:
        raise ValueError('Reference report must bind actual delivered media versions')
    for key in ('actual_reuse_ratio', 'supported_knowledge_count', 'unverified_conclusions',
                'wrong_structure_rebuilds', 'human_interventions'):
        if key not in report:
            raise ValueError('Reference report missing: ' + key)
    ratio = report['actual_reuse_ratio']
    if ratio is not None and (not finite(ratio) or not 0 <= ratio <= 1 or not report.get('reuse_measurement_basis')):
        raise ValueError('Reuse ratio requires measured basis or null')
    if report['unverified_conclusions'] != []:
        raise ValueError('Unverified mechanical conclusions block acceptance')
    for key in ('supported_knowledge_count', 'wrong_structure_rebuilds', 'human_interventions'):
        value = report[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError('Counts must be observed nonnegative integers or null')
    return report
