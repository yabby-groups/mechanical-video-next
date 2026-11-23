"""Verify the rendered AAC against the approved, sample-aligned Neil timeline."""
from array import array
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import wave

from scripts.common import ROOT, check_output, codehash, digest, filehash, probe
from . import joint_timeline as joint
from .media_policy import binding, bound, validate_rights


MODE = 'verified_neil_technical'
AAC_FRAME = 1024
# Audiogen's streaming RIFF header uses a sentinel data size before EOF is known.
STREAMING_WAV_FRAMES = 0x7fffff9b // 2
SILENCE_LEVEL = 10 ** (-48 / 20)
SILENCE_LIMIT = joint.SAMPLE_RATE // 2
WINDOW = joint.SAMPLE_RATE // 10
MIN_MIX_MARGIN_DB = 10
MUSIC_LISTENING = {'story_fit', 'neil_clarity', 'mechanical_sync', 'opening',
                   'reveal', 'transitions', 'ending'}


def music_review(report, media):
    """A listening conclusion needs observations against the complete exact MP4."""
    review = report.get('music_listening_review')
    if review is None:
        return 'UNKNOWN'
    films = [row for row in media if Path(row['path']).suffix.lower() == '.mp4']
    if len(films) != 1 or review.get('media_sha256') != films[0]['sha256']:
        raise ValueError('Music listening review must bind the exact production MP4')
    checks = review.get('checks', {})
    if set(checks) != MUSIC_LISTENING or any(
            row.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}
            or not isinstance(row.get('observation'), str) or not row['observation'].strip()
            for row in checks.values()):
        raise ValueError('Music listening review needs observed story fit, clarity, sync, entry, reveal, transitions and ending')
    statuses = {row['status'] for row in checks.values()}
    if statuses != {'UNKNOWN'}:
        span = review.get('time_range')
        if (review.get('method') not in {'continuous_audio', 'continuous_audiovisual'}
                or not isinstance(span, list) or len(span) != 2
                or not all(type(value) in (int, float) and math.isfinite(value) for value in span)
                or not 0 <= span[0] < span[1]):
            raise ValueError('Record the interval actually listened to for the music review')
        if 'FAIL' in statuses:
            return 'FAIL'
        duration = float(probe(bound(films[0]))['format']['duration'])
        if (statuses == {'PASS'} and report.get('full_audio_listened') is True
                and span[0] == 0 and abs(span[1] - duration) <= 1 / joint.FPS):
            return 'PASS'
    return 'UNKNOWN'


def narration_module():
    # Narration is also a standalone script. Keep its code hash and paid caches intact.
    scripts = str(ROOT / 'scripts')
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import narration
    return narration


def verified_sentence(row, narration, profile):
    processed = joint.bound(row['audio'])
    directory = processed.parent
    cache = row['cache']
    raw_key = cache.get('raw_key', '')
    if not isinstance(raw_key, str) or not re.fullmatch(r'[a-f0-9]{64}', raw_key):
        raise ValueError('Neil source requires a sealed raw synthesis key')
    processing_key = digest({'raw': raw_key, 'profile': profile,
                             'processing': codehash('scripts/narration.py')})
    if (cache.get('key') != processing_key
            or processed.resolve() != (narration.STORE / 'sentences' / processing_key / 'narration.wav').resolve()
            or not narration.valid(directory, ['narration.wav', 'processing.json'])):
        raise ValueError('Neil processed WAV is missing, changed or outside the approved synthesis cache')
    processing = json.loads((directory / 'processing.json').read_text())
    if processing['raw_key'] != raw_key or processing['alignment']['post_speed_factor'] != 1:
        raise ValueError('Neil processing receipt differs from the measured utterance')
    raw = narration.STORE / 'raw' / raw_key
    if not narration.valid(raw, ['source.wav', 'request.json', 'response.json']):
        raise ValueError('Neil raw synthesis output or source receipt is missing or changed')
    request = json.loads((raw / 'request.json').read_text())
    response = json.loads((raw / 'response.json').read_text())
    payload = narration.request_payload(row['text'], profile)
    endpoint = narration.validate_endpoint(profile, request.get('endpoint'))
    effective = narration.synthesis_config(profile, endpoint)
    if any('effective_synthesis' in entry and entry['effective_synthesis'] != effective
           for entry in (cache, processing)):
        raise ValueError('Neil effective synthesis configuration differs from the sealed request')
    if (request != {'endpoint': endpoint, 'payload': payload} or digest(request) != raw_key
            or response.get('http_status') != 200):
        raise ValueError('Neil source does not match the approved endpoint, voice or exact text')
    source = raw / 'source.wav'
    with wave.open(str(source), 'rb') as wav:
        frames = round(float(response['duration']) * wav.getframerate())
        frame_bytes = wav.getnchannels() * wav.getsampwidth()
        streamed = frame_bytes == 2 and wav.getnframes() == STREAMING_WAV_FRAMES
        if (frames <= 0 or (wav.getnframes() != frames and not streamed)
                or frames * frame_bytes > source.stat().st_size
                or int(response['sample_rate']) != wav.getframerate()
                or response.get('bytes') != source.stat().st_size):
            raise ValueError('Neil raw WAV is incomplete')
        if len(wav.readframes(frames + 1)) != frames * frame_bytes:
            raise ValueError('Neil raw WAV is incomplete')
    levels = narration.measure_loudness(processed, profile)
    check_levels(levels, profile, 'Neil utterance ' + row['id'])
    inputs = [row['audio'], binding(directory / 'processing.json'), binding(directory / 'complete.json')]
    inputs.extend(binding(raw / name) for name in ('source.wav', 'request.json', 'response.json', 'complete.json'))
    return {'id': row['id'], 'samples': [row['start_sample'], row['end_sample']],
            'loudness_lufs': float(levels['input_i']), 'true_peak_dbtp': float(levels['input_tp']),
            'inputs': inputs}


def check_levels(levels, profile, label, *, reference_lufs=None):
    limits = profile['loudness']
    target = limits['integrated_lufs'] if reference_lufs is None else reference_lufs
    if (abs(float(levels['input_i']) - target) > 1.0
            or float(levels['input_tp']) > limits['true_peak_dbtp'] + 0.2):
        raise ValueError(label + ' exceeds the configured loudness or true-peak tolerance')


def verify_build(media, timeline, blueprint, measured):
    manifest_ref = timeline.get('media_provenance')
    if manifest_ref is None:
        manifest_ref = binding(Path(media['path']).with_suffix('.media-provenance.json'))
    manifest = json.loads(bound(manifest_ref).read_text())
    proof_ref = manifest['build_proof']
    proof = json.loads(bound(proof_ref).read_text())
    build = proof['build']
    if (any(row.get('sha256') != media['sha256'] or Path(row['path']).resolve() != Path(media['path']).resolve()
            for row in (manifest['media'], proof['media']))
            or build.get('narration') != measured['narration_audio']
            or build['visual_config'].get('measured_timeline') != blueprint['measured_timeline']
            or build['visual_config'].get('timeline') != blueprint['timeline']):
        raise ValueError('Neil master and subtitles must bind the exact final build and Blueprint')
    props_ref = build['props']
    props = json.loads(bound(props_ref).read_text())
    if props['cues'] != joint.cues(measured):
        raise ValueError('Composed subtitle intervals differ from the measured Neil timeline')
    return build['visual_config'], props, [manifest_ref, proof_ref, props_ref]


def verify_composed_track(props, track_binding):
    track = Path(props['narrationTrack'])
    if (len(track.parts) != 2 or track.parts[0] != 'cache' or '\\' in str(track)
            or any(row.get('audio') for row in props['shots'])):
        raise ValueError('Final build audio input differs from the bound master')
    cache = (ROOT / 'remotion/public/cache').resolve()
    path = (cache / track.name).resolve()
    if path.parent != cache or filehash(path) != track_binding['sha256']:
        raise ValueError('Final build audio input differs from the bound master')
    return binding(path)


def decode_aac(path, expected_samples):
    streams = probe(path)['streams']
    tracks = [stream for stream in streams if stream['codec_type'] == 'audio']
    if len(tracks) != 1 or tracks[0]['codec_name'] != 'aac':
        raise ValueError('Final MP4 must have one unambiguous AAC audio track')
    audio = tracks[0]
    rate, channels = int(audio['sample_rate']), int(audio['channels'])
    duration = float(audio['duration'])
    if (rate != joint.SAMPLE_RATE or channels not in (1, 2)
            or abs(float(audio['start_time'])) > 1 / rate
            or not math.isfinite(duration) or abs(round(duration * rate) - expected_samples) > AAC_FRAME):
        raise ValueError('Final AAC start, format or duration differs from the complete measured timeline')
    data = check_output(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:a:0',
                                    '-f', 'f32le', '-acodec', 'pcm_f32le', '-'])
    samples = memoryview(data).cast('f')
    count = len(samples) // channels
    if not expected_samples <= count <= expected_samples + 2 * AAC_FRAME:
        raise ValueError('Final AAC decode is truncated or has unexpected samples')
    return samples, {'audio_pcm_sha256': hashlib.sha256(data).hexdigest(),
                     'audio_pcm_format': {'format': 'f32le', 'sample_rate': rate, 'channels': channels},
                     'decoded_sample_count': count, 'stream_duration': duration}


def wav_samples(wav, frames):
    samples = array('h')
    samples.frombytes(wav.readframes(frames))
    if len(samples) != frames:
        raise ValueError('Bound audio WAV is truncated')
    return samples


def compare_waveforms(master_path, samples, channels, measured, expected_samples, mix=False):
    """Compare local energy and residual so global loudness cannot hide a lost tail."""
    peak = 0.
    minimum_snr = math.inf
    energy = 0.
    channel_gains = [1.] * channels if channels == 1 else [None] * channels
    with wave.open(str(master_path), 'rb') as master:
        for start in range(0, expected_samples, WINDOW):
            end = min(start + WINDOW, expected_samples)
            reference = [sample / 32768 for sample in wav_samples(master, end - start)]
            ref_power = math.sumprod(reference, reference)
            for channel in range(channels):
                actual = list(samples[start * channels + channel:end * channels:channels])
                local_peak = max(map(abs, actual))
                if not math.isfinite(local_peak) or local_peak >= .9999:
                    raise ValueError(f'Final AAC clips at {start / joint.SAMPLE_RATE:.3f}s')
                peak = max(peak, local_peak)
                actual_power = math.sumprod(actual, actual)
                energy += actual_power
                if ref_power / len(reference) <= SILENCE_LEVEL ** 2:
                    if actual_power / len(actual) > (2 * SILENCE_LEVEL) ** 2:
                        raise ValueError(f'Unexpected final audio at {start / joint.SAMPLE_RATE:.3f}s')
                    continue
                # AAC may carry a mono source as dual mono at unity or at -3 dB.
                # Whole-track loudness is evaluated separately and sample timing is never shifted.
                gain = math.sumprod(reference, actual) / ref_power
                if channel_gains[channel] is None:
                    channel_gains[channel] = 1. if gain >= .84 else math.sqrt(.5)
                ratio = gain / channel_gains[channel]
                error = max(0, actual_power - gain * gain * ref_power)
                snr = 10 * math.log10(max(gain * gain * ref_power, 1e-20) / max(error, 1e-20))
                if not .84 <= ratio <= 1.19 or not snr >= 12:
                    raise ValueError(f'Final AAC differs from the bound audio near {start / joint.SAMPLE_RATE:.3f}s')
                minimum_snr = min(minimum_snr, snr)
    tail = max(map(abs, samples[expected_samples * channels:]), default=0.)
    if not tail < .05:
        raise ValueError('Unexpected audio beyond the measured film timeline')
    if not math.isfinite(minimum_snr):
        if measured['speech'] or peak > 1e-5:
            raise ValueError('Final AAC has no measurable match to the bound audio')
        with wave.open(str(master_path), 'rb') as master:
            if any(master.readframes(expected_samples)):
                raise ValueError('Final AAC has no measurable match to the bound audio')
        minimum_snr = None
    last_end = measured['speech'][-1]['end_sample'] if measured['speech'] else None
    return {'sample_peak': peak, 'rms': math.sqrt(energy / (expected_samples * channels)),
            'minimum_reference_snr_db': minimum_snr, 'last_utterance_end_sample': last_end,
            'comparison': 'sample-aligned AAC versus bound ' + ('mix' if mix else 'Neil master')}


def verify_speech_silence(master, speech):
    with wave.open(str(master), 'rb') as wav:
        for row in speech:
            start, end = row['samples']
            wav.setpos(start)
            quiet = 0
            for offset in range(start, end, joint.SAMPLE_RATE // 100):
                pcm = wav_samples(wav, min(joint.SAMPLE_RATE // 100, end - offset))
                quiet = quiet + len(pcm) if max(map(abs, pcm)) < 32768 * SILENCE_LEVEL else 0
                if quiet >= SILENCE_LIMIT:
                    raise ValueError(f'Unexpected silence inside Neil utterance {row["id"]} near {offset / joint.SAMPLE_RATE:.3f}s')


def envelope_points(row, start, end):
    points = row.get('envelope')
    if points is None:
        return None
    if (row['kind'] != 'bgm' or not isinstance(points, list) or len(points) < 2
            or any(not isinstance(p, list) or len(p) != 2 or type(p[0]) is not int
                   or type(p[1]) not in (int, float) or not 0 <= p[1] <= 1 for p in points)
            or points[0] != [start, 0] or points[-1] != [end - 1, 0]
            or any(a[0] >= b[0] for a, b in zip(points, points[1:]))):
        raise ValueError('BGM envelope needs ordered sample points, linear amplitude and silent boundaries')
    return points


def apply_envelope(samples, first, gain, points):
    if points is None:
        return [gain * sample for sample in samples]
    from bisect import bisect_right
    index = bisect_right(points, first, key=lambda point: point[0]) - 1
    result = []
    for offset, sample in enumerate(samples, first):
        if index + 1 < len(points) - 1 and offset >= points[index + 1][0]:
            index += 1
        left, before = points[index]
        right, after = points[index + 1]
        amplitude = before + (after - before) * (offset - left) / (right - left)
        result.append(gain * amplitude * sample)
    return result


def process_mix(stem_rows, master_path, expected_samples, *, destination=None, reference=None,
                check_masking=True, output_gain_db=0):
    """Stream the same declared source windows and gain law for rendering and verification."""
    from .audio_library import open_pcm
    if type(output_gain_db) not in (int, float) or not -3 <= output_gain_db <= 0:
        raise ValueError('Mix headroom trim must be between -3 and 0 dB')
    output_gain = 10 ** (output_gain_db / 20)
    inputs = []
    with ExitStack() as stack:
        narration = stack.enter_context(wave.open(str(master_path), 'rb'))
        mixed = stack.enter_context(wave.open(str(reference), 'rb')) if reference else None
        output = stack.enter_context(wave.open(str(destination), 'wb')) if destination else None
        if output:
            output.setparams((1, 2, joint.SAMPLE_RATE, 0, 'NONE', 'not compressed'))
        sources, stems, music_peaks = {}, [], {}
        for row in stem_rows:
            validate_rights(row)
            source = bound(row['source'])
            if source not in sources:
                sources[source] = stack.enter_context(open_pcm(source))
            wav = sources[source]
            start, end, offset, gain = (row[key] for key in ('start_sample','end_sample','source_start_sample','gain_db'))
            if (row['kind'] not in {'bgm', 'sfx'} or not all(type(v) is int for v in (start, end, offset))
                    or not 0 <= start < end <= expected_samples or offset < 0
                    or offset + end - start > wav.getnframes()
                    or type(gain) not in {int, float} or not math.isfinite(gain) or not -80 <= gain <= 12):
                raise ValueError('Unverified audio stem interval, format or gain')
            inputs.extend((row['source'], row['license']['proof']))
            cue = row.get('cue_id') if row['kind'] == 'bgm' else None
            if cue is not None:
                music_peaks[cue] = 0.
            stems.append((wav, start, end, offset, 10 ** (gain / 20), envelope_points(row, start, end), cue))
        stems.sort(key=lambda stem: stem[1])
        active, cursor = [], 0
        for start in range(0, expected_samples, WINDOW):
            end = min(start + WINDOW, expected_samples)
            voice = wav_samples(narration, end - start)
            background = [0.] * len(voice)
            active = [stem for stem in active if stem[2] > start]
            while cursor < len(stems) and stems[cursor][1] < end:
                active.append(stems[cursor])
                cursor += 1
            independent_background_power = 0.
            for wav, left, right, offset, gain, points, cue in active:
                first, stop = max(left, start), min(right, end)
                wav.setpos(offset + first - left)
                stem = apply_envelope(wav_samples(wav, stop - first), first, gain, points)
                if cue is not None:
                    music_peaks[cue] = max(music_peaks[cue], max(map(abs, stem)))
                independent_background_power += math.sumprod(stem, stem)
                for index, sample in enumerate(stem, first - start):
                    background[index] += sample
            power = math.sumprod(voice, voice)
            if (check_masking and power / len(voice) > (32768 * .01) ** 2
                    and max(independent_background_power, math.sumprod(background, background))
                    > power / (10 ** (MIN_MIX_MARGIN_DB / 10))):
                raise ValueError(f'Potential BGM or effect masking near {start / joint.SAMPLE_RATE:.3f}s requires audio review')
            values = [(speech + bed) * output_gain for speech, bed in zip(voice, background, strict=True)]
            if (any(abs(value) >= 32767 for value in values)
                    or (mixed and any(abs(actual - expected) > 2 for actual, expected
                                     in zip(wav_samples(mixed, end - start), values, strict=True)))):
                raise ValueError(f'Bound mix clips or differs from the declared stem gains near {start / joint.SAMPLE_RATE:.3f}s')
            if output:
                output.writeframesraw(array('h', map(round, values)).tobytes())
        if any(peak < 32768 * 10 ** (-66 / 20) for peak in music_peaks.values()):
            raise ValueError('A selected BGM cue is electrically silent or below the minimum level')
    return list({(ref['path'], ref['sha256']): ref for ref in inputs}.values())


def verify_mix(mix, master_path, expected_samples, *, check_masking=True):
    """Verify bound PCM against the measured Neil master and source gain envelopes."""
    if mix is None:
        return master_path, []
    if (not isinstance(mix, dict) or not isinstance(mix.get('stems'), list)
            or not mix['stems'] and not (mix.get('schema_version') == 1 and mix.get('output_gain_db', 0) < 0)):
        raise ValueError('A final BGM/effects mix needs bound sources and gains for audio verification')
    mixed_path = bound(mix['master'])
    if joint.pcm_frames(mixed_path) != expected_samples:
        raise ValueError('Bound audio mix does not cover the measured timeline')
    inputs = process_mix(mix['stems'], master_path, expected_samples, reference=mixed_path,
                         check_masking=check_masking, output_gain_db=mix.get('output_gain_db', 0))
    return mixed_path, [mix['master'], *inputs]


def verify(timeline, blueprint):
    """Produce acceptance evidence from files, never from the reviewer's asserted PASS."""
    media, = [row for row in timeline['media'] if Path(row['path']).suffix.lower() == '.mp4']
    final = bound(media)
    plan = joint.validate(blueprint['timeline'], blueprint['shots'])
    reference = blueprint['measured_timeline']
    measured = joint.receipt(plan, reference)
    from . import director_audio
    music = director_audio.enabled(blueprint)
    if not measured['speech'] and not music:
        raise ValueError('Technical audio acceptance requires verified Neil utterances')
    narration = narration_module()
    profile_ref = binding(ROOT / 'config/narration-neil.json')
    profile = narration.effective_profile({'narration_profile': profile_ref['path']})
    approval = json.loads(narration.DEFAULTS.read_text())
    audition = ROOT / approval['approved_audition']
    inputs = [reference, measured['narration_audio'], profile_ref, binding(narration.DEFAULTS),
              binding(audition), binding(audition.parent / 'audition.wav')]
    sample_count = plan['frame_count'] * joint.SAMPLES_PER_FRAME
    samples, identity = decode_aac(final, sample_count)
    if measured['speech'] and round(identity['stream_duration'] * joint.SAMPLE_RATE) + 1 < measured['speech'][-1]['end_sample']:
        raise ValueError('Final AAC ends before the last measured Neil utterance')
    master = joint.bound(measured['narration_audio'])
    config, props, build_inputs = verify_build(media, timeline, blueprint, measured)
    if music != director_audio.enabled(config):
        raise ValueError('Final build changed the pinned music policy')
    arrangement = director_audio.validate_arrangement(config, blueprint=blueprint, measured=measured, require_ready=True)
    if arrangement is not None:
        design, audio_inputs = arrangement
        inputs.extend(audio_inputs)
    mix = config.get('audio_mix')
    if 'audio_mix' in timeline and timeline['audio_mix'] != mix:
        raise ValueError('Timeline mix differs from the bound final composition')
    track, mix_inputs = verify_mix(mix, master, sample_count)
    inputs.extend(mix_inputs)
    inputs.extend(build_inputs)
    inputs.append(verify_composed_track(props, binding(track)))
    speech = [verified_sentence(row, narration, profile) for row in measured['speech']]
    verify_speech_silence(master, speech)
    comparison = compare_waveforms(track, samples, identity['audio_pcm_format']['channels'], measured,
                                   sample_count, mix=bool(mix_inputs))
    levels = narration.measure_loudness(final, profile)
    reference_lufs = float(narration.measure_loudness(track, profile)['input_i'])
    check_levels(levels, profile, 'Final AAC', reference_lufs=reference_lufs)
    if music and float(levels['input_tp']) > profile['loudness']['true_peak_dbtp']:
        raise ValueError('Final AAC exceeds the configured true-peak ceiling')
    if filehash(final) != media['sha256']:
        raise ValueError('Final MP4 changed during audio verification')
    return dict(identity, **comparison, media_sha256=media['sha256'], verified_sample_range=[0, sample_count],
                integrated_lufs=float(levels['input_i']), reference_loudness_lufs=reference_lufs,
                true_peak_dbtp=float(levels['input_tp']),
                silence_threshold_dbfs=-48, silence_limit_seconds=SILENCE_LIMIT / joint.SAMPLE_RATE,
                subtitle_sync='measured utterance intervals',
                mix_check={'stem_count': len(mix['stems']) if mix_inputs else 0,
                           'minimum_speech_to_mix_db': MIN_MIX_MARGIN_DB if mix_inputs else None,
                           **({'music_status': design['status'],
                               'music_cues': len(design['selections']),
                               'direction': config['audio_direction']} if arrangement else {})},
                inputs=inputs, utterances=speech)


def check_evidence(report, media, *, require_music=False):
    evidence = report.get('audio_technical_evidence', {})
    if report.get('audio_technical_status') != 'PASS':
        reason = evidence.get('reason', 'verified Neil audio evidence is missing')
        raise ValueError('Technical audio acceptance requires review: ' + reason)
    if ({evidence.get('media_sha256')} != {row['sha256'] for row in media}
            or (not require_music and not evidence.get('utterances')) or not evidence.get('inputs')
            or not re.fullmatch(r'[a-f0-9]{64}', evidence.get('audio_pcm_sha256', ''))):
        raise ValueError('Technical audio evidence must bind the exact final MP4 and measured Neil sources')
    for ref in evidence['inputs']:
        bound(ref)
    if require_music:
        mix = evidence['mix_check']
        bound(mix['direction'])
        if not (mix['music_status'] == 'SILENCE_DESIGNED'
                or mix['music_status'] == 'READY' and mix['music_cues'] > 0):
            raise ValueError('Formal delivery requires verified BGM or documented intentional silence')
    for row in evidence['utterances']:
        for ref in row['inputs']:
            bound(ref)
