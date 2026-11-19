"""Local, dated reference observations. Never fetches or confirms freshness.

Candidate input is an array, a candidates/analysis object, or that object with
optional ``creative_blueprint`` and ``blueprint_qa``. A verified blueprint QA
must bind ``blueprint_sha256`` to digest(blueprint), pass ANIMATIC_CHECKS, and
reference actual unchanged MP4 media. Draft blueprints are not cached as verified.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
from fractions import Fraction
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from .viral import date, validate_creative_blueprint
from .workflow import ANIMATIC_CHECKS, check_media, digest

ALIASES = (('拉链', 'zipper'), ('齿轮', 'gear', 'gears'),
           ('棘轮', 'ratchet'), ('弹簧', 'spring'), ('轴承', 'bearing'),
           ('卷尺', 'tape measure'), ('曲柄', 'crank'), ('连杆', 'linkage'))
FRESHNESS = 'UNVERIFIED_CACHED_OBSERVATIONS'


def canonical_video_id(url):
    """Identify actual works; strip tracking, never resolve short links online."""
    if not isinstance(url, str):
        raise ValueError('Original public video URL required')
    p = urlsplit(url)
    host = (p.hostname or '').lower().removeprefix('www.')
    if p.scheme not in {'http', 'https'} or not host or p.username or p.password:
        raise ValueError('Original public video URL required')
    segments = [s for s in p.path.split('/') if s]
    if any(s.lower() in {'search', 'search_result', 'results'} for s in segments):
        raise ValueError('Search URL cannot identify a reference video')
    query = parse_qs(p.query)
    if host in {'youtube.com', 'm.youtube.com', 'youtu.be'}:
        key = (segments[0] if host == 'youtu.be' and segments else None)
        key = key or (query.get('v') or [None])[0]
        if not key and len(segments) == 2 and segments[0] in {'shorts', 'embed'}:
            key = segments[1]
        if not key or not re.fullmatch(r'[A-Za-z0-9_-]+', key):
            raise ValueError('YouTube video ID required')
        return 'youtube:' + key
    if host in {'douyin.com', 'm.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com'}:
        key = (query.get('modal_id') or query.get('vid') or [None])[0]
        if not key:
            found = re.search(r'/(?:video|share/video)/(\d+)', p.path)
            key = found.group(1) if found else None
        if not key or not key.isdigit():
            raise ValueError('Douyin work ID required; unresolved short links are not IDs')
        return 'douyin:' + key
    if host in {'xiaohongshu.com', 'm.xiaohongshu.com'}:
        found = re.search(r'/(?:explore|discovery/item)/([A-Za-z0-9]+)', p.path)
        if not found:
            raise ValueError('Xiaohongshu work ID required')
        return 'xiaohongshu:' + found.group(1)
    if host in {'v.douyin.com', 'xhslink.com', 'b23.tv'}:
        raise ValueError('Resolve short links to original work URLs before ingest')
    if host in {'bilibili.com', 'm.bilibili.com'}:
        found = re.search(r'/video/(BV[A-Za-z0-9]+|av\d+)', p.path)
        if not found:
            raise ValueError('Bilibili video ID required')
        return 'bilibili:' + found.group(1)
    if not segments:
        raise ValueError('A site homepage cannot identify a reference video')
    tracking = {'fbclid', 'gclid', 'spm', 'share_token', 'share_source', 'source'}
    stable = sorted((k, v) for k, values in query.items()
                    if not k.lower().startswith('utm_') and k.lower() not in tracking
                    for v in values)
    return urlunsplit(('https', host, p.path.rstrip('/'), urlencode(stable), ''))


def _key(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _path(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError('Reference path escapes library root')
    return path


def _read(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def _write(root, relative, data, immutable=False):
    path = _path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if immutable and path.exists():
        if path.read_text() != encoded:
            raise ValueError('Immutable reference observation changed')
        return False
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.reference-',
                                     encoding='utf-8', delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return True


@contextmanager
def _lock(root):
    Path(root).mkdir(parents=True, exist_ok=True)
    with _path(root, '.library.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _labels(values):
    if isinstance(values, str) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError('Labels must be a list of nonempty text values')
    return sorted(set(unicodedata.normalize('NFKC', v).strip() for v in values))


def _index(root, category, label, observations, provenance):
    relative = f'{category}/{_key(label)}.json'
    entry = _read(_path(root, relative), {'schema_version': 1, 'label': label,
                                        'observations': [], 'provenance': []})
    entry['observations'] = sorted(set(entry['observations']) | set(observations))
    if provenance not in entry['provenance']:
        entry['provenance'].append(provenance)
    _write(root, relative, entry)


def _verified_blueprint(blueprint, qa):
    validate_creative_blueprint(blueprint)
    if not isinstance(qa, dict) or qa.get('blueprint_sha256') != digest(blueprint):
        raise ValueError('Verified blueprint requires QA bound to exact blueprint SHA256')
    checks = qa.get('checks', {})
    if not ANIMATIC_CHECKS <= set(checks) or any(value != 'PASS' for value in checks.values()):
        raise ValueError('Verified blueprint requires every actual QA check PASS')
    reviewer = qa.get('reviewer_thread_id')
    if (qa.get('independent_reviewer') is not True or not isinstance(reviewer, str)
            or not reviewer.strip() or reviewer in qa.get('producer_thread_ids', [])
            or any(i.get('severity') in {'critical', 'major', 'error'} for i in qa.get('issues', []))):
        raise ValueError('Verified blueprint requires independent QA without blocking issues')
    check_media(qa.get('media'))
    if not any(Path(item['path']).suffix.lower() == '.mp4' for item in qa['media']):
        raise ValueError('Actual blueprint QA requires MP4 evidence')


def ingest(data, topic, mechanisms=(), root=Path('references'), source_path=None):
    """Cache reported evidence, including partial/unviewed candidates unchanged."""
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError('Nonempty topic required')
    mechanisms = _labels(mechanisms)
    source = {'path': str(Path(source_path).resolve()) if source_path else None,
              'sha256': (hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
                         if source_path else digest(data)), 'payload_sha256': digest(data)}
    document = {'candidates': data} if isinstance(data, list) else data
    if not isinstance(document, dict) or not isinstance(document.get('candidates'), list):
        raise ValueError('Input must contain a candidates array')
    json.dumps(document, allow_nan=False)
    # Validate everything before mutating the library.
    prepared = []
    for candidate in document['candidates']:
        if not isinstance(candidate, dict):
            raise ValueError('Candidate must be an object')
        identity = canonical_video_id(candidate.get('url'))
        capture = candidate.get('observed_at') or document.get('observed_at')
        date(capture)
        _labels(candidate.get('patterns', []))
        observation = {'schema_version': 1, 'canonical_id': identity,
                       'captured_at': capture, 'candidate': candidate,
                       'freshness': FRESHNESS}
        sha = digest(observation)
        relative = f'patterns/observations/{_key(identity)}/{sha}.json'
        prepared.append((relative, observation))
    blueprint = document.get('creative_blueprint', document.get('blueprint'))
    qa = document.get('blueprint_qa', document.get('qa'))
    blueprint_rejection = None
    if blueprint is not None:
        try:
            _verified_blueprint(blueprint, qa)
        except (ValueError, OSError) as error:
            blueprint_rejection = str(error)
            blueprint = None
    created = 0
    with _lock(root):
        for category in ('themes', 'mechanisms', 'patterns', 'blueprints'):
            _path(root, category).mkdir(parents=True, exist_ok=True)
        for relative, observation in prepared:
            created += _write(root, relative, observation, immutable=True)
        paths = [p for p, _ in prepared]
        _index(root, 'themes', topic.strip(), paths, source)
        for label in mechanisms:
            _index(root, 'mechanisms', label, paths, source)
        for relative, observation in prepared:
            for label in _labels(observation['candidate'].get('patterns', [])):
                _index(root, 'patterns', label, [relative], source)
        blueprint_path = None
        if blueprint is not None:
            entry = {'schema_version': 1, 'status': 'VERIFIED_AT_CAPTURE',
                     'topic': topic.strip(), 'mechanisms': mechanisms,
                     'blueprint': blueprint, 'blueprint_sha256': digest(blueprint),
                     'qa': qa, 'source': source, 'freshness': FRESHNESS}
            blueprint_path = f'blueprints/{digest(entry)}.json'
            _write(root, blueprint_path, entry, immutable=True)
    return {'observations': len(prepared), 'new_observations': created,
            'canonical_references': len({v['canonical_id'] for _, v in prepared}),
            'blueprint': blueprint_path, 'blueprint_rejection': blueprint_rejection,
            'root': str(Path(root).resolve()),
            'network_accessed': False, 'freshness': FRESHNESS}


def _terms(value):
    text = unicodedata.normalize('NFKC', value).casefold()
    terms = set(re.findall(r'[^\W_]+', text, flags=re.UNICODE))
    for aliases in ALIASES:
        if any(alias in text for alias in aliases):
            terms.update(aliases)
    return terms


def search(query, root=Path('references'), limit=20):
    """Search local observations first; returned metrics are always historical."""
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or limit < 1:
        raise ValueError('Nonempty query and positive integer limit required')
    root = Path(root).resolve()
    labels = {}
    for category in ('themes', 'mechanisms', 'patterns'):
        for path in sorted(_path(root, category).glob('*.json')):
            entry = _read(_path(root, str(path.relative_to(root))), {})
            for observation in entry.get('observations', []):
                labels.setdefault(observation, set()).add(entry['label'])
    terms = _terms(query)
    found = {}
    for path in sorted(_path(root, 'patterns/observations').glob('*/*.json')):
        relative = str(path.relative_to(root))
        observation = _read(_path(root, relative))
        if path.stem != digest(observation):
            raise ValueError('Cached observation hash mismatch: ' + relative)
        candidate = observation['candidate']
        searchable = ' '.join([*labels.get(relative, set()),
                               str(candidate.get('title', '')), str(candidate.get('observations', '')),
                               str(candidate.get('mechanism', '')), str(candidate.get('patterns', ''))])
        haystack = ' '.join(_terms(searchable))
        score = sum(term in haystack for term in terms)
        if not score:
            continue
        identity = observation['canonical_id']
        record = found.setdefault(identity, {'canonical_id': identity, 'score': 0, 'observations': []})
        record['score'] = max(record['score'], score)
        record['observations'].append({'path': relative, 'sha256': path.stem,
                                       'captured_at': observation['captured_at'],
                                       'candidate': candidate, 'labels': sorted(labels.get(relative, set()))})
    results = sorted(found.values(), key=lambda r: (-r['score'], r['canonical_id']))[:limit]
    blueprints = []
    for path in sorted(_path(root, 'blueprints').glob('*.json')):
        entry = _read(_path(root, str(path.relative_to(root))))
        if path.stem != digest(entry):
            raise ValueError('Cached blueprint hash mismatch')
        text = ' '.join([entry['topic'], *entry['mechanisms'], entry['blueprint']['core_question']])
        if any(term in ' '.join(_terms(text)) for term in terms):
            # Evidence may disappear after capture; do not renew historical PASS.
            try:
                _verified_blueprint(entry['blueprint'], entry['qa'])
                evidence_current = True
            except (ValueError, OSError):
                evidence_current = False
            blueprints.append({'path': str(path.relative_to(root)), 'sha256': path.stem,
                               'evidence_current': evidence_current, **entry})
    return {'query': query, 'root': str(root.resolve()), 'results': results,
            'blueprints': blueprints[:limit], 'network_accessed': False,
            'freshness': FRESHNESS, 'freshness_confirmed': False}


MEDIA_TYPES = {'REFERENCE_ONLY', 'LICENSED_REUSE', 'OWNED', 'GENERATED'}
MEDIA_ORIGINS = {'project', 'local', 'third_party', 'stock', '3d'}
VIDEO_SUFFIXES = {'.mp4', '.mov', '.webm'}
MODEL_SUFFIXES = {'.glb', '.gltf', '.blend', '.step', '.stp', '.stl', '.obj'}


def _file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _restricted_license(license_info):
    restrictions = license_info.get('usage_restrictions', [])
    if not isinstance(restrictions, list):
        return True
    text = ' '.join([str(license_info.get('name', '')), *(str(x) for x in restrictions)]).upper()
    return bool(re.search(r'(?<![A-Z])(?:NC|ND)(?![A-Z])|NON[ -]?COMMERCIAL|NO[ -]?DERIVATIVES', text))


def ingest_media(metadata, path, root=Path('references')):
    """Store a content-addressed blob and an independent immutable rights record."""
    if not isinstance(metadata, dict):
        raise ValueError('Media metadata must be an object')
    data = dict(metadata)
    data.setdefault('source_type', 'REFERENCE_ONLY')
    data.setdefault('origin', 'third_party')
    if data['source_type'] not in MEDIA_TYPES or data['origin'] not in MEDIA_ORIGINS:
        raise ValueError('Invalid media source_type or origin')
    for name in ('tags', 'mechanism_knowledge', 'used_shots', 'sources', 'visual_capabilities', 'model_capabilities'):
        data[name] = _labels(data.get(name, []))
    if 'mechanism_id' in data and (not isinstance(data['mechanism_id'], str) or not data['mechanism_id'].strip()):
        raise ValueError('Media mechanism_id must identify a specific implementation')
    segment = data.get('segment')
    if segment is not None:
        if not isinstance(segment, dict):
            raise ValueError('Segment must be an object')
        start, end = segment.get('start_sec'), segment.get('end_sec')
        if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end))
                or start < 0 or end <= start):
            raise ValueError('Invalid segment bounds')
    quality = data.get('quality', {})
    if not isinstance(quality, dict):
        raise ValueError('Quality must be an object')
    license_info = data.get('license', {})
    if not isinstance(license_info, dict):
        raise ValueError('License must be an object')
    license_info = dict(license_info)
    license_info['usage_scopes'] = _labels(license_info.get('usage_scopes', []))
    data['license'] = license_info
    path = Path(path).resolve(strict=True)
    suffix = path.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        from scripts.common import probe
        info = probe(path)
        stream = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
        if not stream:
            raise ValueError('Media has no video stream')
        try:
            fps = float(Fraction(stream['avg_frame_rate']))
            duration = float(stream.get('duration') or info['format']['duration'])
            width, height = int(stream['width']), int(stream['height'])
        except (KeyError, ValueError, ZeroDivisionError, TypeError) as error:
            raise ValueError('Video measurements unavailable') from error
        if not all(math.isfinite(x) and x > 0 for x in (fps, duration, width, height)):
            raise ValueError('Invalid video measurements')
        if segment and segment['end_sec'] > duration + 1e-6:
            raise ValueError('Segment exceeds video duration')
        for key, measured in (('width', width), ('height', height), ('fps', fps)):
            if key in quality and (type(quality[key]) not in (int, float) or abs(quality[key] - measured) > .01):
                raise ValueError('Declared quality differs from measured ' + key)
        data['quality'] = {**quality, 'width': width, 'height': height, 'fps': fps, 'duration_sec': duration}
        data['media_kind'] = 'video'
    elif suffix in {'.tsx','.ts'} and data.get('template_kind') == 'remotion':
        if not data.get('supported_graphics'):
            raise ValueError('Remotion template needs its supported graphic interface')
        data['supported_graphics'] = _labels(data['supported_graphics'])
        data['media_kind'] = 'template'
        data['segment'] = None
    elif suffix == '.json':
        from .visual_narrative import validate_graphic
        validate_graphic(json.loads(path.read_text()))
        data['media_kind'] = 'graphic'
        data['segment'] = None  # Native animation definitions have no source-video time interval.
    elif suffix in MODEL_SUFFIXES:
        inventory = data.get('inventory', {})
        if (not isinstance(inventory, dict) or inventory.get('inspected') is not True
                or not isinstance(inventory.get('proof'), dict)):
            raise ValueError('3D model requires inspected inventory and proof')
        data['media_kind'] = 'model'
    else:
        raise ValueError('Unsupported media extension')
    data['extension'] = suffix
    json.dumps(data, allow_nan=False)
    sha = _file_sha(path)
    record = {'schema_version': 1, 'sha256': sha, 'metadata': data}
    record_sha = digest(record)
    with _lock(root):
        blob = _path(root, f'media/blobs/{sha}/source{suffix}')
        blob.parent.mkdir(parents=True, exist_ok=True)
        existing = list(blob.parent.glob('source.*'))
        if existing:
            blob = existing[0]
        if blob.exists():
            if _file_sha(blob) != sha:
                raise ValueError('Cached media hash mismatch')
        else:
            from scripts.common import budget
            budget()
            if shutil.disk_usage(blob.parent).free < path.stat().st_size + 3*1024**3:
                raise ValueError('Insufficient space for content cache and 3 GiB reserve')
            with tempfile.NamedTemporaryFile(dir=blob.parent, prefix='.media-', delete=False) as f:
                temporary = Path(f.name)
                try:
                    with path.open('rb') as source:
                        shutil.copyfileobj(source, f)
                    f.flush()
                    os.fsync(f.fileno())
                    if _file_sha(temporary) != sha:
                        raise ValueError('Media changed during ingest')
                    os.replace(temporary, blob)
                finally:
                    temporary.unlink(missing_ok=True)
        relative = f'media/records/{record_sha}.json'
        _write(root, relative, record, immutable=True)
    return {'sha256': sha, 'blob': str(blob), 'record': relative, 'record_sha256': record_sha}


def _media_records(root):
    root = Path(root).resolve()
    for path in sorted(_path(root, 'media/records').glob('*.json')):
        record = _read(path)
        if path.stem != digest(record):
            raise ValueError('Media record hash mismatch: ' + str(path))
        yield path, record


def search_media(query, root=Path('references')):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Nonempty query required')
    terms = _terms(query)
    return [{'record': str(p.relative_to(Path(root).resolve())), **r, 'uses': media_uses(r['sha256'], root)}
            for p, r in _media_records(root)
            if terms & _terms(' '.join(r['metadata']['tags'] + r['metadata']['mechanism_knowledge']))]


def media_uses(sha256, root=Path('references')):
    if not re.fullmatch(r'[a-f0-9]{64}', sha256):
        raise ValueError('A content SHA256 is required')
    rows = []
    for path in sorted(_path(root, f'media/uses/{sha256}').glob('*.json')):
        row = _read(path)
        if digest(row) != path.stem:
            raise ValueError('Media usage record changed')
        rows.append(row)
    return rows


def record_media_use(record, task_id, shot_id, time_range, media, knowledge_ids, root=Path('references')):
    """Record actual composed use, without asserting final perceptual acceptance."""
    entry = _read(_path(root, record))
    if not entry or Path(record).stem != digest(entry):
        raise ValueError('Media record hash mismatch')
    if not task_id or not shot_id or not isinstance(media, dict):
        raise ValueError('Usage needs task, shot and actual final media')
    path = Path(media.get('path', ''))
    if not path.is_file() or _file_sha(path) != media.get('sha256'):
        raise ValueError('Actual media missing or changed')
    if entry['metadata']['media_kind'] == 'video':
        segment = entry['metadata'].get('segment') or {'start_sec':0,'end_sec':entry['metadata']['quality']['duration_sec']}
        if (not isinstance(time_range,list) or len(time_range) != 2
                or not all(type(x) in (int,float) and math.isfinite(x) for x in time_range)
                or not segment['start_sec'] <= time_range[0] < time_range[1] <= segment['end_sec']):
            raise ValueError('Usage outside recorded source interval')
    elif time_range is not None:
        raise ValueError('Native assets have no source-video interval')
    row = {'schema_version':1, 'asset_sha256':entry['sha256'], 'record':record,
           'task_id':task_id,'shot_id':shot_id,'source_time_range':time_range,
           'knowledge_ids':_labels(knowledge_ids),'media':dict(media, path=str(path.resolve())),
           'acceptance':'NOT_GRANTED_BY_USAGE_RECORD'}
    with _lock(root):
        relative = f'media/uses/{entry["sha256"]}/{digest(row)}.json'
        _write(root, relative, row, immutable=True)
    return {'path':str(_path(root,relative).resolve()), 'sha256':_file_sha(_path(root,relative))}


def match_media(shot, root=Path('references')):
    """Return ordered decisions; metadata assertions still require production QA."""
    if not isinstance(shot, dict):
        raise ValueError('Shot must be an object')
    tags = set(_labels(shot.get('tags', [])))
    knowledge = set(_labels(shot.get('mechanism_knowledge', [])))
    scope = shot.get('usage_scope')
    if not tags or not knowledge or not isinstance(scope, str) or not scope.strip():
        raise ValueError('Shot requires tags, mechanism_knowledge and usage_scope')
    implementation = shot.get('mechanism_id')
    if implementation is not None and (not isinstance(implementation, str) or not implementation.strip()):
        raise ValueError('Shot mechanism_id must identify a specific implementation')
    duration = shot.get('duration_sec')
    if duration is not None and (type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0):
        raise ValueError('Shot duration must be a positive finite number')
    attempts = []
    for path, record in _media_records(root):
        m, sha = record['metadata'], record['sha256']
        origin = m['origin']
        owned = m['source_type'] in {'OWNED','GENERATED'}
        priority = (1 if owned and origin == 'project' and m.get('project_id') == shot.get('project_id')
                    and shot.get('project_id') else 2 if owned else
                    {'project':3,'local':3,'third_party':3,'stock':4,'3d':5}[origin])
        reasons = []
        candidates = list(_path(root, f'media/blobs/{sha}').glob('source.*'))
        blob = candidates[0] if candidates else _path(root, f'media/blobs/{sha}/source{m.get("extension", "")}')
        if not blob.is_file() or _file_sha(blob) != sha:
            reasons.append('media_hash_invalid')
        lic = m['license']
        if m['source_type'] == 'REFERENCE_ONLY':
            reasons.append('reference_only')
        proof_binding = lic.get('proof') or {}
        if not isinstance(proof_binding, dict):
            proof_binding = {}
        proof = proof_binding.get('path')
        expected = proof_binding.get('sha256')
        if (not isinstance(proof, str) or not proof or not isinstance(expected, str)
                or not proof_binding.get('position') or not Path(proof).is_file()
                or _file_sha(proof) != expected):
            reasons.append('license_proof_invalid')
        if (lic.get('status') != 'VERIFIED' or not lic.get('name') or not lic.get('holder')
                or lic.get('editing_and_distribution') is not True or lic.get('commercial_use') is not True):
            reasons.append('license_not_verified_for_use')
        if _restricted_license(lic):
            reasons.append('license_restriction')
        if m.get('content_verified') is not True or not m.get('source_url') or not m.get('credit') or not m['sources']:
            reasons.append('content_or_attribution_unverified')
        if m.get('media_kind') == 'model':
            proof = m.get('inventory', {}).get('proof', {})
            proof_path = proof.get('path')
            if (not isinstance(proof_path, str) or not Path(proof_path).is_file()
                    or not proof.get('position') or _file_sha(proof_path) != proof.get('sha256')):
                reasons.append('inventory_proof_invalid')
        if scope not in lic['usage_scopes']:
            reasons.append('usage_scope_not_authorized')
        q = m.get('quality', {})
        if q.get('approved') is not True:
            reasons.append('quality_not_approved')
        for key, default in (() if m.get('media_kind') in {'model','graphic','template'} else (('width', 1920), ('height', 1080), ('fps', 24))):
            value, minimum = q.get(key), shot.get('min_' + key, default)
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or type(minimum) not in (int, float) or not math.isfinite(minimum)
                    or minimum <= 0 or value < minimum):
                reasons.append('insufficient_' + key)
        if not tags.intersection(m['tags']) or not knowledge.issubset(m['mechanism_knowledge']):
            reasons.append('content_mismatch')
        if implementation is not None and m.get('mechanism_id') != implementation:
            reasons.append('mechanism_id_mismatch')
        capability_field = 'model_capabilities' if m.get('media_kind') == 'model' else 'visual_capabilities'
        needed = _labels(shot.get('required_' + capability_field, []))
        if not set(needed) <= set(m.get(capability_field, [])):
            reasons.append('missing_required_' + capability_field)
        if m.get('media_kind') == 'template' and shot.get('graphic_type') not in m.get('supported_graphics', []):
            reasons.append('unsupported_graphic_interface')
        accepted = shot.get('accepted_types')
        if accepted is not None and (not isinstance(accepted, list) or m.get('media_kind') not in accepted):
            reasons.append('media_type_mismatch')
        if duration is not None and m.get('media_kind') == 'video':
            segment = m.get('segment') or {'start_sec': 0, 'end_sec': q.get('duration_sec', 0)}
            if segment['end_sec'] - segment['start_sec'] + 1e-6 < duration:
                reasons.append('segment_too_short')
        if sha in shot.get('used_hashes', []) or (shot.get('shot_id') and shot['shot_id'] in m['used_shots']):
            reasons.append('already_used')
        available = m.get('segment') or {'start_sec':0,'end_sec':q.get('duration_sec',0)}
        chosen_range = ([available['start_sec'], available['start_sec'] + shot.get('duration_sec', available['end_sec']-available['start_sec'])]
                        if m.get('media_kind') == 'video' else None)
        if m.get('media_kind') not in {'model','template'} and any(u.get('sha256') == sha and u.get('time_range') == chosen_range for u in shot.get('used_intervals', [])):
            reasons.append('already_used_interval')
        attempts.append({'record': str(path.relative_to(Path(root).resolve())), 'sha256': sha,
                         'blob': str(blob), 'priority': priority, 'eligible': not reasons,
                         'reasons': reasons, 'metadata': m})
    attempts.sort(key=lambda a: (a['priority'], a['sha256'], a['record']))
    selected = next((a for a in attempts if a['eligible']), None)
    decision = 'REUSE' if selected else 'GENERATE'
    chosen = selected['metadata'] if selected else {}
    segment = chosen.get('segment')
    if selected and chosen.get('media_kind') == 'video' and segment is None:
        segment = {'start_sec':0,'end_sec':chosen['quality']['duration_sec']}
    source_range = ([segment['start_sec'], segment['start_sec'] + shot.get('duration_sec',segment['end_sec']-segment['start_sec'])]
                    if segment else None)
    restrictions = chosen.get('license', {}).get('usage_restrictions', [])
    model_reuse = selected is not None and chosen.get('media_kind') == 'model'
    template_reuse = selected is not None and chosen.get('media_kind') == 'template'
    return {'decision': decision, 'reuse_decision': 'REUSE_MODEL' if model_reuse else 'REUSE_TEMPLATE' if template_reuse else 'REUSE' if selected else 'RESEARCH_REQUIRED',
            'generation_required': model_reuse or template_reuse,
            'selected': selected,
            'selected_asset': {'path': selected['blob'], 'sha256': selected['sha256']} if selected else None,
            'source_type': chosen.get('source_type'), 'source_url': chosen.get('source_url'),
            'time_range': segment, 'source_time_range': source_range,
            'license': chosen.get('license'), 'license_status': chosen.get('license', {}).get('status'),
            'usage_restrictions': restrictions if isinstance(restrictions, list) else [],
            'content_verified': chosen.get('content_verified', False), 'credit': chosen.get('credit'),
            'attempts': attempts, 'fallback': 'GENERATE_AFTER_SEARCH', 'network_accessed': False,
            'external_search_gaps': [] if selected else [
                {'priority': 3, 'provider': 'authorized third-party sources', 'status': 'NOT_SEARCHED'},
                {'priority': 4, 'provider': 'Pexels', 'status': 'NOT_SEARCHED'},
                {'priority': 4, 'provider': 'Pixabay', 'status': 'NOT_SEARCHED'},
                {'priority': 4, 'provider': 'Wikimedia Commons', 'status': 'NOT_SEARCHED'},
                {'priority': 5, 'provider': 'licensed 3D models and animation', 'status': 'NOT_SEARCHED'}]}


def prepare_media_clip(record, root=Path('references'), start_sec=None, end_sec=None):
    """Normalize an eligible video segment; reuse only a hash-verified cached result."""
    from scripts.common import budget, probe
    relative = record.get('record') if isinstance(record, dict) else record
    if not isinstance(relative, str):
        raise ValueError('Media record path required')
    record_path = _path(root, relative)
    entry = _read(record_path)
    if not entry or record_path.stem != digest(entry):
        raise ValueError('Media record hash mismatch')
    m, sha = entry['metadata'], entry['sha256']
    if m.get('media_kind') != 'video':
        raise ValueError('Clip preparation requires video')
    lic = m.get('license', {})
    proof = lic.get('proof', {})
    proof_path = proof.get('path') if isinstance(proof, dict) else None
    restrictions = lic.get('usage_restrictions', [])
    if (m.get('source_type') == 'REFERENCE_ONLY' or m.get('content_verified') is not True
            or lic.get('status') != 'VERIFIED' or lic.get('editing_and_distribution') is not True
            or lic.get('commercial_use') is not True or not lic.get('usage_scopes')
            or not lic.get('name') or not lic.get('holder') or not m.get('credit') or not m.get('source_url')
            or _restricted_license(lic)
            or not isinstance(proof_path, str) or not Path(proof_path).is_file()
            or not proof.get('position') or _file_sha(proof_path) != proof.get('sha256')):
        raise ValueError('Current license or content evidence does not permit clip preparation')
    blobs = list(_path(root, f'media/blobs/{sha}').glob('source.*'))
    if len(blobs) != 1 or _file_sha(blobs[0]) != sha:
        raise ValueError('Media hash mismatch')
    segment = m.get('segment') or {'start_sec': 0, 'end_sec': m['quality']['duration_sec']}
    start = segment['start_sec'] if start_sec is None else start_sec
    end = segment['end_sec'] if end_sec is None else end_sec
    if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end))
            or start < segment['start_sec'] or end > segment['end_sec'] or start >= end):
        raise ValueError('Clip range exceeds authorized segment')
    version = subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]
    config = {'source_sha256': sha, 'start_sec': start, 'end_sec': end,
              'transform': 'scale-pad-1920x1080-fps30-bt709-yuv420p-noaudio-v1', 'ffmpeg': version}
    key = digest(config)
    folder = _path(root, f'media/clips/{key}')
    output, receipt = folder / 'clip.mp4', folder / 'receipt.json'
    with _lock(root):
        saved = _read(receipt)
        if saved and saved.get('config') == config and output.is_file() and saved.get('sha256') == _file_sha(output):
            return {'path': str(output), 'sha256': saved['sha256'], 'cache_hit': True, 'config': config}
        budget()
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, suffix='.mp4', delete=False) as handle:
            temporary = Path(handle.name)
        try:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-i', str(blobs[0]),
                            '-t', str(end-start), '-vf',
                            'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p',
                            '-an', '-c:v', 'libx264', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                            '-colorspace', 'bt709', str(temporary)], check=True)
            info = probe(temporary)
            stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
            if (stream['width'], stream['height'], stream['pix_fmt'], stream['avg_frame_rate']) != (1920, 1080, 'yuv420p', '30/1'):
                raise ValueError('Encoded clip failed format validation')
            budget()
            result_sha = _file_sha(temporary)
            os.replace(temporary, output)
            _write(root, f'media/clips/{key}/receipt.json', {'config': config, 'sha256': result_sha})
        finally:
            temporary.unlink(missing_ok=True)
    return {'path': str(output), 'sha256': result_sha, 'cache_hit': False, 'config': config}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('search')
    command.add_argument('--query', required=True)
    command.add_argument('--limit', type=int, default=20)
    command.add_argument('--root', type=Path, default=Path('references'))
    command = sub.add_parser('ingest')
    command.add_argument('--input', required=True, type=Path)
    command.add_argument('--topic', required=True)
    command.add_argument('--mechanisms', nargs='*', default=[])
    command.add_argument('--root', type=Path, default=Path('references'))
    command = sub.add_parser('media-ingest')
    command.add_argument('--input', required=True, type=Path)
    command.add_argument('--path', required=True, type=Path)
    command.add_argument('--root', type=Path, default=Path('references'))
    command = sub.add_parser('media-search')
    command.add_argument('--query', required=True)
    command.add_argument('--root', type=Path, default=Path('references'))
    command = sub.add_parser('media-match')
    command.add_argument('--input', required=True, type=Path)
    command.add_argument('--root', type=Path, default=Path('references'))
    args = parser.parse_args()
    if args.command == 'search':
        result = search(args.query, args.root, args.limit)
    elif args.command == 'ingest':
        result = ingest(json.loads(args.input.read_text()), args.topic, args.mechanisms,
                        args.root, args.input)
    elif args.command == 'media-ingest':
        result = ingest_media(json.loads(args.input.read_text()), args.path, args.root)
    elif args.command == 'media-search':
        result = search_media(args.query, args.root)
    else:
        result = match_media(json.loads(args.input.read_text()), args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
