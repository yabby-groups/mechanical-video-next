"""Versioned science/director requirements inside existing records and gates."""
import hashlib
import math
from pathlib import Path
import re
import subprocess

from .visual_narrative import located, nonempty

FIELD = 'production_contract_version'
NAME = 'mixed-original-v1'
PRESENTATION_STYLE = 'presentation_style'
NATURAL_SCIENCE = 'natural_science'
PRODUCTION_LABELS = frozenset({
    '原理示意', '教学动画', '教学模型', '概念模型', '仅供演示',
    '动画演示', '示意画面', '以下为演示', '3D 模型展示',
    '教学演示', '教学级运动学', '模型示意', '数学模型',
    '数据驱动动画', '物理仿真', '物理仿真回放', '教学装配',
})
CLASSROOM_OPENINGS = (
    '下面我们来学习', '接下来进行原理演示', '这里使用一个教学模型',
    '如动画所示', '这个示意图告诉我们', '现在我们介绍它的工作原理',
)


def audience_caption(text):
    """Remove standalone production tags while retaining concrete conditions."""
    return ' · '.join(part for part in map(str.strip, re.split(r'[·｜|]', text))
                      if part and part.strip(' ／/。') not in PRODUCTION_LABELS)


def validate_audience_copy(row):
    for line in row.get('narration', []):
        if line.lstrip().startswith(CLASSROOM_OPENINGS):
            raise ValueError(f'Rewrite classroom narration as a concrete scientific observation: {line}')
    graphic = row.get('graphic', {})
    science = row.get('science', {})
    visible = [row.get(key) for key in ('title', 'subtitle', 'chapter', 'label', 'note', 'formula')]
    visible += [graphic.get(key) for key in ('title', 'formula')]
    visible += [value for item in graphic.get('items', []) for value in (item.get('label'), item.get('detail'))]
    visible += list(row.get('subtitles', [])) + list(row.get('overlays', []))
    visible += [item.get('text') for item in row.get('information', []) + row.get('annotations', [])]
    visible += [mark.get('text') for mark in science.get('print_marks', [])]
    for line in visible:
        if isinstance(line, str) and any(part.strip(' ／/。') in PRODUCTION_LABELS
                                        for part in re.split(r'[·｜|]', line)):
            raise ValueError(f'Remove the standalone production label or explain the concrete limitation: {line}')


DIMENSIONS = {'scientific_accuracy', 'mechanical_motion', 'visual_expression',
              'narrative_comprehension', 'originality_copyright', 'av_delivery'}
DIRECTION = {'why_visual', 'composition', 'lighting', 'continuity', 'sound_intent'}
REVIEW_METHODS = {
    'continuous_video': {'video'}, 'continuous_audio': {'audio'},
    'continuous_audiovisual': {'video', 'audio'},
    'sampled_frames': set(), 'technical_decode': set(), 'document_review': set(),
}


def enabled(document):
    version = document.get(FIELD, 0)
    if type(version) is not int or version not in {0, 1}:
        raise ValueError('Unsupported production contract version')
    if version == 1 and (document.get('production_contract') != NAME
            or document.get('media_policy_version') != 1
            or document.get('visual_policy_version') != 2):
        raise ValueError('mixed-original-v1 needs matching explicit policy versions')
    return version == 1


def validate_research(research):
    science = research.get('science', {})
    if science.get('subject_kind') not in {'mechanical_implementation', 'physical_phenomenon'}:
        raise ValueError('Identify the mechanical implementation or bounded physical phenomenon')
    if not all(nonempty(science.get(k)) for k in ('question', 'answer', 'scope')):
        raise ValueError('Scientific question, supported answer and scope required')
    if science['subject_kind']=='physical_phenomenon':
        subject=science.get('subject',{})
        if (not all(nonempty(subject.get(k)) for k in ('id','name','scope'))
                or subject.get('model_kind') not in {'conceptual','mathematical'}):
            raise ValueError('Physical phenomena need a named bounded conceptual/mathematical subject, not a fabricated retail product')
    facts = science.get('facts')
    if not isinstance(facts, list) or not facts:
        raise ValueError('Concise science.facts ledger required')
    seen = set()
    for fact in facts:
        identity = fact.get('id')
        if not nonempty(identity) or identity in seen or not nonempty(fact.get('claim')):
            raise ValueError('Unique fact IDs and concrete claims required')
        seen.add(identity)
        if fact.get('status') not in {'VERIFIED', 'UNKNOWN'}:
            raise ValueError('Fact status must disclose VERIFIED or UNKNOWN')
        if fact.get('kind') not in {'observed', 'derived', 'teaching_approximation', 'hypothesis'}:
            raise ValueError('Disclose the scientific evidence kind')
        if not nonempty(fact.get('scope')) or not isinstance(fact.get('assumptions'), list):
            raise ValueError('Facts require scope and explicit assumptions')
        if fact['status'] == 'VERIFIED':
            if fact['kind'] == 'hypothesis':
                raise ValueError('An unverified hypothesis cannot support a narrated fact')
            located(fact.get('sources'))
        elif not nonempty(fact.get('limitation')):
            raise ValueError('Unknown facts need a specific limitation')
    return {fact['id']: fact for fact in facts}


def validate_direction(blueprint, research=None):
    if not enabled(blueprint):
        return
    narrative = blueprint.get('narrative', {})
    if not all(nonempty(narrative.get(k)) for k in ('question', 'tension', 'answer', 'arc_reason')):
        raise ValueError('Original question, tension, answer and chosen narrative arc required')
    if 'audience_decision' in narrative:
        decision = narrative['audience_decision']
        if (not isinstance(decision, dict) or not all(nonempty(decision.get(key)) for key in
                ('daily_context', 'opening_visual', 'viewer_takeaway', 'selection_rationale'))):
            raise ValueError('Audience decision needs a daily context, opening visual, takeaway and selection rationale')
        shots = blueprint['shots']
        if (not shots or decision.get('opening_shot_id') != shots[0]['shot_id']
                or decision.get('payoff_shot_id') not in {shot['shot_id'] for shot in shots}):
            raise ValueError('Audience decision must bind the first shot and a payoff shot')
    facts = validate_research(research) if research is not None else None
    for shot in blueprint['shots']:
        direction = shot.get('direction', {})
        if not DIRECTION <= direction.keys() or not all(nonempty(direction[k]) for k in DIRECTION):
            raise ValueError('Each shot requires visual rationale, composition, light, continuity and sound intent')
        if facts is not None:
            for identity in shot['knowledge_ids']:
                if identity not in facts or facts[identity]['status'] != 'VERIFIED':
                    raise ValueError('Unsupported fact restricts its dependent shot: ' + identity)


def validate_qa(report, media, *, acceptance, blueprint=None):
    """Six conclusions are independent; deterministic success cannot fill senses."""
    review = report.get('quality_dimensions', {})
    if set(review) != DIMENSIONS:
        raise ValueError('Six independent quality dimensions required')
    hashes = {item['sha256'] for item in media}
    for name, row in review.items():
        if (row.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}
                or row.get('media_sha256') not in hashes or not nonempty(row.get('observation'))):
            raise ValueError('Quality dimensions require exact-media observations: ' + name)
        if row['status'] == 'FAIL' or (acceptance and row['status'] != 'PASS'):
            raise ValueError('Quality dimension prevents acceptance: ' + name)
    if acceptance and (report.get('full_video_reviewed') is not True
            or report.get('full_audio_listened') is not True):
        raise ValueError('Complete actual viewing and listening required for acceptance')
    if acceptance:
        validate_review_observations(report, media, blueprint)


def review_media_identity(binding):
    """Identify the encoded film and decoded audio, without claiming perception."""
    from scripts.common import filehash, probe
    path = Path(binding['path'])
    if not path.is_file() or filehash(path) != binding.get('sha256'):
        raise ValueError('Review media is missing or changed')
    streams = probe(path)['streams']
    video = next((s for s in streams if s['codec_type'] == 'video'), None)
    audio = next((s for s in streams if s['codec_type'] == 'audio'), None)
    if video is None or audio is None:
        raise ValueError('Full review requires actual video and narration audio')
    durations = {kind: float(stream['duration']) for kind, stream in (('video', video), ('audio', audio))}
    if any(not math.isfinite(value) or value <= 0 for value in durations.values()):
        raise ValueError('Review requires finite actual stream durations')
    digest = hashlib.sha256()
    process = subprocess.Popen(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:a:0',
                                '-f', 's16le', '-acodec', 'pcm_s16le', '-'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    count = 0
    try:
        while chunk := process.stdout.read(65536):
            digest.update(chunk)
            count += len(chunk)
        if process.wait() or not count:
            raise ValueError('Complete review audio decoding failed')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
    if filehash(path) != binding['sha256']:
        raise ValueError('Review media changed during audio identity verification')
    return {'media_sha256': binding['sha256'], 'durations': durations,
            'audio_pcm_sha256': digest.hexdigest(),
            'audio_pcm_format': {'format': 's16le', 'sample_rate': int(audio['sample_rate']),
                                 'channels': int(audio['channels'])}}


def validate_review_observations(report, media, blueprint):
    """Validate traceable attestations in the existing QA handoff, not senses.

    These records are hash-bound by the same immutable QA envelope as the six
    conclusions. No second report store or automatically generated PASS exists.
    A truthful independent reviewer remains responsible for actual perception.
    """
    rows = report.get('review_observations')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Full acceptance requires time-covered review observations')
    if not isinstance(blueprint, dict) or not isinstance(blueprint.get('shots'), list) or not blueprint['shots']:
        raise ValueError('Review observations require the current bound Blueprint shots')
    shots = {shot['shot_id']: shot for shot in blueprint['shots']}
    if len(shots) != len(blueprint['shots']):
        raise ValueError('Review Blueprint shot identities must be unique')
    last_shot = blueprint['shots'][-1]['shot_id']
    reviewer = report.get('reviewer_thread_id')
    if report.get('independent_reviewer') is not True or not nonempty(reviewer):
        raise ValueError('Review observations require an independent reviewer identity')
    if reviewer in report.get('production_thread_ids', []):
        raise ValueError('Production agents cannot supply independent review observations')
    identities = {m['sha256']: review_media_identity(m) for m in media}
    coverage = {sha: {'video': [], 'audio': []} for sha in identities}
    observations = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Review observations must be structured records')
        identity, sha = row.get('id'), row.get('media_sha256')
        method, window = row.get('method'), row.get('time_range')
        sid, dimension = row.get('shot_id'), row.get('dimension')
        if (not nonempty(identity) or identity in observations or not nonempty(sha) or sha not in identities
                or not nonempty(method) or method not in REVIEW_METHODS or row.get('reviewer_thread_id') != reviewer
                or not nonempty(sid) or sid not in shots or not nonempty(dimension) or dimension not in DIMENSIONS
                or row.get('knowledge_ids') != shots[sid].get('knowledge_ids', [])
                or row.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}
                or not nonempty(row.get('observation')) or not nonempty(row.get('capability_boundary'))):
            raise ValueError('Review observations require unique IDs, exact media, method, result and capability boundary')
        start, stop = shots[sid]['time_range']
        if sid == last_shot:
            stop = max(stop, *identities[sha]['durations'].values())
        if (not isinstance(window, list) or len(window) != 2
                or any(type(v) not in {int, float} or not math.isfinite(v) for v in window)
                or not max(0, start-.001) <= window[0] < window[1] <= min(stop, max(identities[sha]['durations'].values()))+.001):
            raise ValueError('Review observation interval lies outside its actual media shot')
        modalities = REVIEW_METHODS[method]
        if 'audio' in modalities and any(row.get(key) != identities[sha][key]
                                        for key in ('audio_pcm_sha256', 'audio_pcm_format')):
            raise ValueError('Listening observations must bind the actual decoded audio and format')
        if row['status'] != 'PASS':
            raise ValueError('Applicable review observation FAIL/UNKNOWN prevents final acceptance')
        if row['status'] == 'PASS':
            for modality in modalities:
                coverage[sha][modality].append(window)
        observations[identity] = row
    def require_coverage(intervals, duration, label, start=0.):
        end = start
        for start, stop in sorted(intervals):
            if start > end+.001:
                raise ValueError('Continuous review has an unobserved interval: ' + label)
            end = max(end, stop)
        if end < duration-.001:
            raise ValueError('Continuous review does not cover the complete actual ' + label)

    for sha, modalities in coverage.items():
        for modality, intervals in modalities.items():
            require_coverage(intervals, identities[sha]['durations'][modality], modality)
    for name, conclusion in report['quality_dimensions'].items():
        refs = conclusion.get('observation_ids')
        if (not isinstance(refs, list) or not refs or any(not nonempty(ref) for ref in refs)
                or len(refs) != len(set(refs))
                or any(ref not in observations or observations[ref]['status'] != 'PASS'
                       or observations[ref]['media_sha256'] != conclusion['media_sha256']
                       or observations[ref]['dimension'] != name for ref in refs)):
            raise ValueError('Quality dimension requires matching independent observation records: ' + name)
        # A full-film conclusion cannot cite only a conveniently selected scene.
        # Rights/original-expression conclusions may instead cite document review;
        # the separate existing copyright and originality checks remain mandatory.
        modalities = ({'video'} if name in {'mechanical_motion', 'visual_expression'} else
                      set() if name == 'originality_copyright' else {'video', 'audio'})
        for sid, shot in shots.items():
            start, stop = shot['time_range']
            for modality in modalities or {None}:
                intervals = [observations[ref]['time_range'] for ref in refs
                             if observations[ref]['shot_id'] == sid and (modality is None or
                             modality in REVIEW_METHODS[observations[ref]['method']])]
                duration = (identities[conclusion['media_sha256']]['durations'][modality]
                            if modality is not None else stop)
                end = duration if sid == last_shot else min(stop, duration)
                require_coverage(intervals, end, name + '/' + sid + '/' + str(modality), start=start)
