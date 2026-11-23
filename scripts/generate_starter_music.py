"""Render the original, CC0 Quiet Link theme and its four arrangements."""
from array import array
from math import exp, pi, sin
from pathlib import Path
from tempfile import TemporaryDirectory
import wave

from scripts.common import ROOT, execute, filehash, writejson

RATE = 48000
FOLDER = ROOT / 'assets/audio/bgm/starter'
CATALOG = ROOT / 'assets/audio/metadata'
VARIANTS = {
    'curiosity': (88, .30, ('mysterious', 'anticipation'), .18, .28, .05),
    'technology': (100, .40, ('focused', 'precise'), .29, .21, .11),
    'mechanical_asmr': (74, .18, ('precise', 'intimate'), .08, .36, .00),
    'discovery': (104, .52, ('bright', 'resolved'), .27, .33, .08),
}
CHORDS = ((50, 57, 64, 65), (46, 53, 60, 64), (53, 60, 67, 69), (48, 55, 62, 64))
MELODY = (69, 72, 76, 74, 65, 69, 72, 74, 72, 77, 79, 76, 67, 74, 76, 72)


def note(samples, beat, start, duration, pitch, volume, attack, decay, harmonic):
    first = round(start * beat * RATE)
    count = round(duration * beat * RATE)
    phase = 2 * pi * 440 * 2 ** ((pitch - 69) / 12) / RATE
    for offset in range(min(count, len(samples) - first)):
        seconds = offset / RATE
        level = min(1., seconds / attack, (count - offset) / (RATE * .09)) * exp(-seconds / decay)
        samples[first + offset] += volume * level * (sin(phase * offset) + harmonic * sin(phase * offset * 2))


def render(path, variant):
    bpm, _, _, pulse, pad, bass = variant
    beat = 60 / bpm
    samples = array('d', [0]) * round(16 * beat * RATE)
    for bar, chord in enumerate(CHORDS):
        for pitch in chord:
            note(samples, beat, bar * 4, 4, pitch, pad / len(chord), .38, 4., .03)
        for step in (0, 2.5):
            note(samples, beat, bar * 4 + step, 1.25, chord[0] - 12, bass, .024, .36, .12)
    for step, pitch in enumerate(MELODY):
        note(samples, beat, step + .22, .72, pitch, pulse, .018, .22, .18)
    with TemporaryDirectory() as folder:
        wav = Path(folder) / 'music.wav'
        with wave.open(str(wav), 'wb') as target:
            target.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            target.writeframes(array('h', (round(sample * 32767) for sample in samples)).tobytes())
        execute(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-map_metadata', '-1', '-c:a', 'flac', str(path)], check=True)


def ref(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': filehash(path)}


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    proof = dict(ref(FOLDER / 'CC0.md'), position='Quiet Link authorship and CC0 dedication')
    for mode, variant in VARIANTS.items():
        bpm, energy, mood, *_ = variant
        music_id = 'quiet-link-' + mode.replace('_', '-')
        path = FOLDER / (music_id + '.flac')
        render(path, variant)
        writejson(CATALOG / (music_id + '.json'), {
            'id': music_id, 'title': 'Quiet Link · ' + mode.replace('_', ' ').title(), 'theme': 'quiet-link',
            'style': [mode], 'mood': list(mood), 'energy': energy, 'bpm': bpm,
            'speech_fit': .85, 'sfx_fit': .9, 'loopable': True, 'tier': 'original',
            'source_type': 'GENERATED', 'source_url': 'repo:scripts/generate_starter_music.py', 'source': ref(path),
            'license_status': 'VERIFIED', 'license': {'status': 'VERIFIED', 'name': 'CC0 1.0 Universal',
            'holder': 'Original Quiet Link contribution', 'editing_and_distribution': True,
            'commercial_use': True, 'proof': proof},
            'credit': 'Quiet Link · Mechanical Video Next', 'usage_restrictions': [],
        })


if __name__ == '__main__':
    main()
