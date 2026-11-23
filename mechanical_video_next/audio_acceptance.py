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

from scripts.common import ROOT, check_output, digest, filehash, probe
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
    endpoint = profile['base_url'].rstrip('/') + '/audio/speech'
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
        raise ValueError('Final AAC has no measurable match to the bound audio')
    last_end = measured['speech'][-1]['end_sample']
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


def verify_mix(mix, master_path, expected_samples, *, check_masking=True):
    """Check an existing mono mix using bound PCM sources, placement and static gains."""
    if mix is None:
        return master_path, []
    if not isinstance(mix, dict) or not isinstance(mix.get('stems'), list) or not mix['stems']:
        raise ValueError('A final BGM/effects mix needs bound sources and gains for audio verification')
    inputs = [mix['master']]
    mixed_path = bound(mix['master'])
    if joint.pcm_frames(mixed_path) != expected_samples:
        raise ValueError('Bound audio mix does not cover the measured timeline')
    with ExitStack() as stack:
        narration = stack.enter_context(wave.open(str(master_path), 'rb'))
        mixed = stack.enter_context(wave.open(str(mixed_path), 'rb'))
        stems = []
        for row in mix['stems']:
            validate_rights(row)
            source = bound(row['source'])
            start, end, offset, gain = (row[key] for key in ('start_sample','end_sample','source_start_sample','gain_db'))
            if (row['kind'] not in {'bgm', 'sfx'} or not all(type(v) is int for v in (start, end, offset))
                    or not 0 <= start < end <= expected_samples or offset < 0
                    or offset + end - start > joint.pcm_frames(source)
                    or type(gain) not in {int, float} or not math.isfinite(gain) or not -80 <= gain <= 12):
                raise ValueError('Unverified audio stem interval, format or gain')
            wav = stack.enter_context(wave.open(str(source), 'rb'))
            inputs.extend((row['source'], row['license']['proof']))
            stems.append((wav, start, end, offset, 10 ** (gain / 20)))
        for start in range(0, expected_samples, WINDOW):
            end = min(start + WINDOW, expected_samples)
            voice = wav_samples(narration, end - start)
            background = [0.] * len(voice)
            independent_background_power = 0.
            for wav, left, right, offset, gain in stems:
                first, stop = max(left, start), min(right, end)
                if first >= stop:
                    continue
                wav.setpos(offset + first - left)
                stem = wav_samples(wav, stop - first)
                independent_background_power += gain ** 2 * math.sumprod(stem, stem)
                for index, sample in enumerate(stem, first - start):
                    background[index] += gain * sample
            power = math.sumprod(voice, voice)
            if (check_masking and power / len(voice) > (32768 * .01) ** 2
                    and max(independent_background_power, math.sumprod(background, background))
                    > power / (10 ** (MIN_MIX_MARGIN_DB / 10))):
                raise ValueError(f'Potential BGM or effect masking near {start / joint.SAMPLE_RATE:.3f}s requires audio review')
            for speech, bed, output in zip(voice, background, wav_samples(mixed, end - start), strict=True):
                if abs(speech + bed) >= 32767 or abs(output - (speech + bed)) > 2:
                    raise ValueError(f'Bound mix clips or differs from the declared stem gains near {start / joint.SAMPLE_RATE:.3f}s')
    return mixed_path, inputs


def verify(timeline, blueprint):
    """Produce acceptance evidence from files, never from the reviewer's asserted PASS."""
    media, = [row for row in timeline['media'] if Path(row['path']).suffix.lower() == '.mp4']
    final = bound(media)
    plan = joint.validate(blueprint['timeline'], blueprint['shots'])
    reference = blueprint['measured_timeline']
    measured = joint.receipt(plan, reference)
    if not measured['speech']:
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
    if round(identity['stream_duration'] * joint.SAMPLE_RATE) + 1 < measured['speech'][-1]['end_sample']:
        raise ValueError('Final AAC ends before the last measured Neil utterance')
    master = joint.bound(measured['narration_audio'])
    config, props, build_inputs = verify_build(media, timeline, blueprint, measured)
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
    if filehash(final) != media['sha256']:
        raise ValueError('Final MP4 changed during audio verification')
    return dict(identity, **comparison, media_sha256=media['sha256'], verified_sample_range=[0, sample_count],
                integrated_lufs=float(levels['input_i']), reference_loudness_lufs=reference_lufs,
                true_peak_dbtp=float(levels['input_tp']),
                silence_threshold_dbfs=-48, silence_limit_seconds=SILENCE_LIMIT / joint.SAMPLE_RATE,
                subtitle_sync='measured utterance intervals',
                mix_check={'stem_count': len(mix['stems']) if mix_inputs else 0,
                           'minimum_speech_to_mix_db': MIN_MIX_MARGIN_DB if mix_inputs else None},
                inputs=inputs, utterances=speech)


def check_evidence(report, media):
    evidence = report.get('audio_technical_evidence', {})
    if report.get('audio_technical_status') != 'PASS':
        reason = evidence.get('reason', 'verified Neil audio evidence is missing')
        raise ValueError('Technical audio acceptance requires review: ' + reason)
    if ({evidence.get('media_sha256')} != {row['sha256'] for row in media}
            or not evidence.get('utterances') or not evidence.get('inputs')
            or not re.fullmatch(r'[a-f0-9]{64}', evidence.get('audio_pcm_sha256', ''))):
        raise ValueError('Technical audio evidence must bind the exact final MP4 and measured Neil sources')
    for ref in evidence['inputs']:
        bound(ref)
    for row in evidence['utterances']:
        for ref in row['inputs']:
            bound(ref)
