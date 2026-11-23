"""Local-first music catalog using the existing commercial media rights evidence."""
import argparse
from array import array
from contextlib import contextmanager
import json
import math
import math
from pathlib import Path
import re
import shutil
from subprocess import CalledProcessError
from tempfile import NamedTemporaryFile, TemporaryDirectory
import wave

from scripts.common import ROOT, execute, filehash
from . import joint_timeline as joint
from .media_policy import binding, bound, validate_rights

LIBRARY = ROOT / 'assets/audio/metadata'
RETIREMENTS = LIBRARY.parent / 'catalog-retirements.json'
AUDIO_SUFFIXES = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.opus'}
RIGHTS_REVIEW_REQUIRED = 'RIGHTS_REVIEW_REQUIRED'


@contextmanager
def pcm_path(path, *, downmix=None):
    """Expose 48 kHz mono PCM and remove decoded copies as soon as they are used."""
    if downmix not in (None, 'stereo_average'):
        raise ValueError('Unsupported music PCM conversion')
    if downmix is None and path.suffix.lower() == '.wav':
        with wave.open(str(path), 'rb') as wav:
            canonical = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (joint.SAMPLE_RATE, 1, 2)
        if canonical:
            yield path
            return
    with TemporaryDirectory(prefix='music-pcm-') as folder:
        decoded = Path(folder) / 'audio.wav'
        filters = ['-af', 'pan=mono|c0=0.5*c0+0.5*c1'] if downmix else []
        execute(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:a:0',
                 *filters, '-ac', '1', '-ar', str(joint.SAMPLE_RATE), '-c:a', 'pcm_s16le', str(decoded)], check=True)
        yield decoded


@contextmanager
def open_pcm(path, *, downmix=None):
    with pcm_path(path, downmix=downmix) as decoded, wave.open(str(decoded), 'rb') as wav:
        yield wav


def inspect_audio(row):
    for key in ('id', 'title', 'theme', 'source_url'):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError('Music metadata requires ' + key)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', row['id']):
        raise ValueError('Music catalog ID must be a simple filename')
    for key in ('style', 'mood'):
        if not isinstance(row.get(key), list) or not row[key] or any(
                not isinstance(tag, str) or not tag.strip() for tag in row[key]):
            raise ValueError('Music metadata requires searchable tags for ' + key)
    limits = {'energy': (0, 1), 'bpm': (20, 300), 'speech_fit': (0, 1), 'sfx_fit': (0, 1)}
    for key, (low, high) in limits.items():
        if type(row.get(key)) not in (int, float) or not low <= row[key] <= high:
            raise ValueError('Music metadata has an invalid ' + key)
    if type(row.get('loopable')) is not bool or row.get('tier', 'local') not in ('local', 'registered', 'original'):
        raise ValueError('Music metadata requires an explicit loop decision and valid source tier')
    source = bound(row['source'])
    if source.suffix.lower() not in AUDIO_SUFFIXES:
        raise ValueError('Unsupported music file format')
    downmix = row.get('pcm_downmix')
    if {'sample_rate', 'channels', 'duration_seconds'} & row.keys() and source.suffix.lower() == '.wav':
        with wave.open(str(source), 'rb') as wav:
            expected = {'sample_rate': wav.getframerate(), 'channels': wav.getnchannels(),
                        'duration_seconds': wav.getnframes() / wav.getframerate()}
            if any(row.get(key, actual) != actual for key, actual in expected.items()):
                raise ValueError('Music metadata differs from decoded WAV parameters')
            if downmix and wav.getnchannels() != 2:
                raise ValueError('Stereo average requires a two-channel music source')
    with open_pcm(source, downmix=downmix) as wav:
        count = wav.getnframes()
    loop = row.get('loop_samples', [0, count])
    if (not isinstance(loop, list) or len(loop) != 2 or any(type(x) is not int for x in loop)
            or not 0 <= loop[0] < loop[1] <= count
            or row['loopable'] and loop[1] - loop[0] < joint.SAMPLE_RATE):
        raise ValueError('Music loop points must fit the decoded source')
    result = dict(row, sample_count=count, loop_samples=loop)
    if 'loop_crossfade_samples' in row:
        result['loop_analysis'] = analyze_loop(source, loop, row['loop_crossfade_samples'], row['bpm'], downmix=downmix)
    return result


def analyze_loop(source, loop, overlap, bpm, *, downmix=None):
    """Check a pinned, phase-aligned splice against the PCM used in the mix."""
    first, last = loop
    if type(overlap) is not int or not 2 <= overlap <= min(joint.SAMPLE_RATE // 4, (last - first) // 4):
        raise ValueError('Invalid music loop crossfade length')
    with open_pcm(source, downmix=downmix) as wav:
        wav.setpos(first)
        incoming = array('h', wav.readframes(overlap))
        wav.setpos(last - overlap)
        outgoing = array('h', wav.readframes(overlap))
    if len(incoming) != overlap or len(outgoing) != overlap:
        raise ValueError('Music loop crossfade exceeds the decoded source')
    def alignment(incoming, outgoing):
        a, b = math.sumprod(incoming, incoming), math.sumprod(outgoing, outgoing)
        return (math.sumprod(incoming, outgoing) / math.sqrt(a * b), 10 * math.log10(a / b)) if a and b else (0., math.inf)

    def lowpass(values):
        # Four passes attenuate upper harmonics when comparing bass and drum phase.
        alpha = 1 - math.exp(-2 * math.pi * 180 / joint.SAMPLE_RATE)
        for _ in range(4):
            filtered, state = [], 0.
            for value in values:
                state += alpha * (value - state)
                filtered.append(state)
            values = filtered
        return values

    correlation, level_delta = alignment(incoming, outgoing)
    bass_correlation, _ = alignment(lowpass(incoming), lowpass(outgoing))
    period = last - first - overlap
    beats = period * bpm / (60 * joint.SAMPLE_RATE)
    off_beat = abs(beats - round(beats))
    if min(correlation, bass_correlation) < .8 or abs(level_delta) > 2 or off_beat > .02:
        raise ValueError('Music loop seam failed waveform correlation, level or beat alignment')
    blend = [before + (after - before) * i / (overlap - 1)
             for i, (before, after) in enumerate(zip(outgoing, incoming, strict=True))]
    return {'method': 'phase_matched_linear', 'start_sample': first, 'end_sample': last,
            'overlap_samples': overlap, 'period_samples': period, 'period_beats': round(beats, 6),
            'correlation': round(correlation, 6), 'bass_correlation': round(bass_correlation, 6),
            'incoming_minus_outgoing_db': round(level_delta, 6),
            'max_blended_sample_step': round(max(abs(y - x) for x, y in zip(blend, blend[1:])), 3)}


def inspect(row):
    if row.get('license_status') == RIGHTS_REVIEW_REQUIRED:
        source = ROOT / row['source']['path']
        if not source.is_file():
            raise ValueError('Music source missing: ' + str(source))
        bound(row['source'])
        raise ValueError(RIGHTS_REVIEW_REQUIRED)
    validate_rights(row)
    return inspect_audio(row)


def require_active(row):
    """Keep archived bytes verifiable at their original paths and out of new arrangements."""
    retired = json.loads(RETIREMENTS.read_text())
    if row['id'] in retired or row['source']['sha256'] in retired.values():
        raise ValueError('Music catalog entry is retired from active selection: ' + row['id'])


def records(directory=LIBRARY, *, selected=None):
    eligible, rejected, ids = [], [], set()
    files = [Path(directory) / (selected + '.json')] if selected else sorted(Path(directory).glob('*.json'))
    for path in files:
        try:
            if not path.is_file():
                raise ValueError('Music catalog record missing: ' + path.name)
            raw = json.loads(path.read_text())
            require_active(raw)
            row = inspect(raw)
            if row['id'] in ids or path.stem != row['id']:
                raise ValueError('Music record must use its unique ID as filename')
            eligible.append(dict(row, catalog_record=binding(path)))
            ids.add(row['id'])
        except (ValueError, OSError, KeyError, TypeError, EOFError, wave.Error) as error:
            rejected.append({'record': path.name, 'reason': str(error)})
        except CalledProcessError as error:
            rejected.append({'record': path.name, 'reason': f'Audio decode failed ({error.returncode})'})
    return eligible, rejected


def choose(cue, available, previous=None):
    """Find a length-compatible, rights-checked track, preferring the local theme."""
    duration = cue.get('film_samples', (cue['end_frame'] - cue['start_frame']
                                        + cue.get('crossfade_in_frames', 0)) * joint.SAMPLES_PER_FRAME)
    best = None
    for row in available:
        if row['sample_count'] < duration and not row['loopable']:
            continue
        if 'asset_id' in cue:
            if row['id'] == cue['asset_id']:
                return row, {}
            continue
        styles = set(cue['style']) & set(row['style'])
        same_theme = previous is not None and row['theme'] == previous['theme']
        if not styles and not same_theme:
            continue
        tier = {'local': 0 if styles else 1, 'registered': 2, 'original': 3}[row.get('tier', 'local')]
        score = dict(style=len(styles), mood=len(set(cue['mood']) & set(row['mood'])),
                     energy=1 - abs(cue['energy'] - row['energy']),
                     tempo=max(0, 1 - abs(cue['bpm'] - row['bpm']) / 80),
                     speech=row['speech_fit'], effects=row['sfx_fit'],
                     length=1 if row['sample_count'] >= duration else .5,
                     continuity=int(same_theme))
        weighted = (3 * score['style'] + 2 * score['mood'] + 2 * score['energy'] + score['tempo']
                    + score['speech'] + score['effects'] + score['length'] + 2 * score['continuity'])
        rank = (tier, row['id'] not in cue['suggested_assets'] if cue['suggested_assets'] else False,
                -weighted, row['id'])
        if best is None or rank < best[0]:
            best = (rank, row, score)
    return (best[1], best[2]) if best else (None, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=LIBRARY)
    parser.add_argument('--register', type=Path, help='Register a metadata JSON with existing local sources and proof')
    args = parser.parse_args()
    if args.register:
        from .workflow import lock, write
        raw = json.loads(args.register.read_text())
        require_active(raw)
        row = inspect(raw)
        target = args.catalog / (row['id'] + '.json')
        source = bound(raw['source'])
        blob = args.catalog.parent / 'bgm' / 'blobs' / row['source']['sha256'] / ('music' + source.suffix.lower())
        with lock(target.with_suffix('.lock'), wait=True):
            if target.is_file():
                previous = json.loads(target.read_text())
                if previous != dict(raw, source=previous['source']) or previous['source']['sha256'] != row['source']['sha256']:
                    raise ValueError('Use a new catalog ID for a changed source or license')
            if not blob.is_file():
                blob.parent.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(dir=blob.parent, delete=False) as temporary:
                    candidate = Path(temporary.name)
                try:
                    shutil.copyfile(source, candidate)
                    if filehash(candidate) != row['source']['sha256']:
                        raise ValueError('Music source changed while importing')
                    candidate.replace(blob)
                finally:
                    candidate.unlink(missing_ok=True)
            if filehash(blob) != row['source']['sha256']:
                raise ValueError('Registered music bytes changed')
            write(target, dict(raw, source=binding(blob)))
        print(json.dumps({'path': str(target), 'sha256': filehash(target)}))
    else:
        eligible, rejected = records(args.catalog)
        print(json.dumps({'eligible': eligible, 'rejected': rejected}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
