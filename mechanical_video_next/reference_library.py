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
import os
from pathlib import Path
import re
import tempfile
import unicodedata
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
    args = parser.parse_args()
    if args.command == 'search':
        result = search(args.query, args.root, args.limit)
    else:
        result = ingest(json.loads(args.input.read_text()), args.topic, args.mechanisms,
                        args.root, args.input)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
