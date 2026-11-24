"""Technical checks for a measured voice timeline and optional ASR observations."""
from difflib import SequenceMatcher
import re
import unicodedata

from scripts import narration
from scripts.common import ROOT
from . import audio_acceptance, joint_timeline as joint
from .voice_direction import review_cues


def normalized(text):
    return ''.join(char for char in unicodedata.normalize('NFKC', text).casefold()
                   if char.isalnum())


def transcript_cues(expected, actual):
    left, right = normalized(expected), normalized(actual)
    return [
        {'operation': tag, 'expected': left[i:j], 'observed': right[a:b]}
        for tag, i, j, a, b in SequenceMatcher(None, left, right, autojunk=False).get_opcodes()
        if tag != 'equal'
    ]


def level_report(path, profile, label):
    levels = narration.measure_loudness(path, profile)
    cues = []
    try:
        audio_acceptance.check_levels(levels, profile, label)
    except ValueError as error:
        cues.append(str(error))
    return dict(technical_levels='NEEDS_REVIEW' if cues else 'PASS',
                integrated_lufs=float(levels['input_i']), true_peak_dbtp=float(levels['input_tp']),
                level_cues=cues)


def measure_quality(timeline, direction, observations=None, *, media=None):
    master = joint.bound(timeline['narration_audio'])
    profile = narration.load_profile(ROOT / 'config/narration-neil.json')
    observed = observations or {}
    rows = []
    previous_end = 0
    for speech, request in zip(timeline['speech'], direction['segments'], strict=True):
        start, end = speech['start_sample'], speech['end_sample']
        duration_ms = (end - start) / 48
        cues = []
        try:
            audio_acceptance.verify_speech_silence(master, [
                {'id': speech['id'], 'samples': (start, end)}
            ])
        except ValueError:
            cues.append('句内至少 500 ms 低于 −48 dBFS，复核停顿。')
        asr = observed.get(speech['id'])
        if asr is not None and asr['audio_sha256'] != speech['audio']['sha256']:
            raise ValueError('ASR observation refers to different audio: ' + speech['id'])
        differences = transcript_cues(request['text'], asr['text']) if asr else []
        if differences:
            cues.append('ASR 文本有差异，需定位核听。')
        if duration_ms > request['target_duration_ms'] + 1:
            cues.append('语音超过导演目标时长，仍在镜头硬边界内。')
        anchors = []
        for anchor in request.get('action_anchors', []):
            action_sample = anchor['frame'] * joint.SAMPLES_PER_FRAME
            # A timestamped reviewer/aligner must attest to the exact bound clip.
            tokens = [] if asr is None else [
                token for token in asr.get('phrases', []) if token['phrase'] == anchor['phrase']
            ]
            occurrence = anchor.get('occurrence', 1)
            phrase_sample = None
            if len(tokens) >= occurrence:
                offset = tokens[occurrence - 1]['offset_ms']
                if type(offset) not in (int, float) or not 0 <= offset < duration_ms:
                    raise ValueError('ASR anchor is outside the audio: ' + speech['id'])
                phrase_sample = start + round(offset * 48)
            delta_ms = None if phrase_sample is None else (phrase_sample - action_sample) / 48
            status = 'UNKNOWN' if delta_ms is None else 'WITHIN_TOLERANCE'
            if delta_ms is not None and abs(delta_ms) > anchor.get('tolerance_ms', 300):
                status = 'NEEDS_REVIEW'
            if not start <= action_sample < end:
                status = 'NEEDS_REVIEW'
            anchors.append(dict(anchor, action_sample=action_sample, phrase_sample=phrase_sample,
                                delta_ms=delta_ms, status=status,
                                timing_basis='recognizer estimate' if delta_ms is not None else None))
        gap_ms = (start - previous_end) / 48
        if rows and gap_ms >= 1000:
            cues.append('与上一句相隔至少 1 秒，结合镜头复核是否为有意留白。')
        rows.append(dict(segment_id=speech['id'], duration_ms=duration_ms, gap_before_ms=gap_ms, cues=cues,
                         transcript_differences=differences, asr_status='UNKNOWN' if asr is None else
                         'NEEDS_REVIEW' if differences else 'TEXT_MATCH',
                         observed_text=asr['text'] if asr is not None else None,
                         action_anchors=anchors, speaker_reference_cosine=
                         speech['cache'].get('inference', {}).get('speaker_reference_cosine')))
        previous_end = end
    scores = [row['speaker_reference_cosine'] for row in rows if row['speaker_reference_cosine'] is not None]
    return dict(
        **level_report(master, profile, 'Audition master'),
        encoded_levels=level_report(media, profile, 'Audition AAC') if media else None,
        direction_cues=review_cues(direction), rows=rows, listening='UNKNOWN', continuity='UNKNOWN',
        pronunciation='UNKNOWN', emotion_fit='UNKNOWN', native_naturalness='UNKNOWN',
        speaker_consistency='UNKNOWN',
        speaker_reference_cosine_range=[min(scores), max(scores)] if scores else None,
        acoustic_action_sync='UNKNOWN',
    )


def phrase_observations(result, anchors):
    characters, offsets = [], []
    for token, seconds in zip(result['tokens'], result['seconds'], strict=True):
        if token.startswith('<') and token.endswith('>'):
            continue
        letters = normalized(token)
        characters.extend(letters)
        offsets.extend([seconds * 1000] * len(letters))
    decoded = ''.join(characters)
    return [
        {'phrase': phrase, 'offset_ms': offsets[match.start()]}
        for phrase in dict.fromkeys(anchor['phrase'] for anchor in anchors)
        if normalized(phrase)
        for match in re.finditer(re.escape(normalized(phrase)), decoded)
    ]


def sensevoice(timeline, config):
    """Use a preinstalled, offline SenseVoiceSmall runtime."""
    from pathlib import Path
    import json
    import os
    import subprocess
    from tempfile import TemporaryDirectory

    model = Path(config['model_dir']).expanduser().resolve()
    backend = config.get('backend', 'sherpa-onnx')
    if backend == 'sherpa-onnx':
        files = ('model.int8.onnx', 'tokens.txt')
        worker = [str(Path(__file__).with_name('voice_asr.py'))]
    elif backend == 'funasr':
        files = ('configuration.json',)
        worker = [str(Path(__file__).with_name('voice_worker.py')), 'sensevoice']
    else:
        raise ValueError('Unknown SenseVoice backend: ' + backend)
    if not all((model / filename).is_file() for filename in files):
        raise ValueError('Provision the local SenseVoiceSmall model first')
    runtime = Path(config['runtime_python']).expanduser().absolute()
    with TemporaryDirectory(prefix='mechanical-voice-asr-') as directory:
        payload = Path(directory) / 'observations.json'
        subprocess.run([
            str(runtime), *worker,
            str(model), str(payload), *[str(joint.bound(row['audio'])) for row in timeline['speech']],
        ], check=True, timeout=config.get('timeout_seconds', 300),
            env=dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1'))
        raw = json.loads(payload.read_text())
    direction = timeline['voice_direction']['segments']
    observations = {}
    for row, request, result in zip(timeline['speech'], direction, raw, strict=True):
        if backend == 'sherpa-onnx':
            text = result['text']
            phrases = phrase_observations(result, request.get('action_anchors', []))
        else:
            text = re.sub(r'<\|[^|]+\|>', '', result)
            phrases = []
        observations[row['id']] = dict(audio_sha256=row['audio']['sha256'], text=text, phrases=phrases)
    return observations
