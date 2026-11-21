"""The fixed Remotion invocation shared by production and 3D replay."""

from pathlib import Path
import json
import math

from scripts.common import ROOT, run


SOURCES = ('remotion/src/index.tsx', 'remotion/src/TextOverlay.tsx',
           'remotion/src/ShotInformation.tsx', 'remotion/package-lock.json', 'config/text-style.json')
VISUAL_SOURCES = SOURCES[1:] + (
    'remotion/src/visualEntry.tsx', 'remotion/src/VisualNarrative.tsx', 'remotion/src/EvidenceGraphic.tsx')
PROGRESSION_SOURCES = SOURCES[1:] + (
    'remotion/src/progressionEntry.tsx', 'remotion/src/EvidenceGraphic.tsx', 'remotion/src/VisualNarrative.tsx')


def validate_phone_text(text, width, *, size=86):
    """Preflight a single line at the smallest supported 360 px preview size.

    Browser layout remains authoritative for the actual installed font and box.
    Width and size are in 1920 px composition coordinates.
    """
    from .text_layout import measure_text
    if (not isinstance(text, str) or not text.strip() or '\n' in text or '\r' in text
            or not isinstance(width, (int, float)) or not math.isfinite(width) or width <= 0
            or size < 86 or measure_text(text, size=size)['width'] > width):
        raise ValueError('Text must fit on one line at phone-readable size')


def sources_for(document):
    from .knowledge_progression import enabled
    if enabled(document):
        return PROGRESSION_SOURCES
    return VISUAL_SOURCES if document.get('visual_policy_version') == 2 else SOURCES


def render(props, output, log, *, preview=False, encode_profile=None, visual=False, progression=False, frame_range=None):
    document = json.loads(Path(props).read_text())
    if 'frameCount' in document:
        from .joint_timeline import FPS, frame_number
        count = document['frameCount']
        if (document['fps'] != FPS or type(count) is not int or count < 1
                or frame_number(document['duration']) != count
                or sum(frame_number(shot['seconds']) for shot in document['shots']) != count):
            raise ValueError('Remotion composition duration differs from the complete picture track')
    chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    entry = 'progressionEntry' if progression else 'visualEntry' if visual else 'index'
    concurrency = '1' if encode_profile == 'progression-witness-v1' else '2'
    args = [ROOT/'remotion/node_modules/.bin/remotion', 'render',
            f'src/{entry}.tsx', 'Mechanical',
            Path(output).resolve(), '--props', Path(props).resolve(), '--codec', 'h264', '--audio-codec', 'aac',
            '--pixel-format', 'yuv420p', '--concurrency', concurrency, '--browser-executable', chrome,
            '--gl', 'angle', '--log', 'error']
    if frame_range is not None:
        if (not isinstance(frame_range, (list, tuple)) or len(frame_range) != 2
                or any(type(f) is not int for f in frame_range) or not 0 <= frame_range[0] <= frame_range[1]):
            raise ValueError('Render frame range requires inclusive nonnegative integer endpoints')
        args += ['--frames', f'{frame_range[0]}-{frame_range[1]}']
    if preview:
        args += ['--scale', '0.5', '--crf', '25']
    elif encode_profile == 'witness-v1':
        args += ['--image-format', 'png', '--crf', '12', '--timeout', '120000']
    elif encode_profile == 'progression-witness-v1' and progression:
        args += ['--image-format', 'png', '--crf', '6', '--timeout', '120000']
    elif encode_profile is not None:
        raise ValueError('Unknown Remotion encode profile')
    run(args, log, cwd=ROOT/'remotion')
