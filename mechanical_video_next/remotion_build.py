"""The fixed Remotion invocation shared by production and 3D replay."""

from pathlib import Path

from scripts.common import ROOT, run


SOURCES = ('remotion/src/index.tsx', 'remotion/src/TextOverlay.tsx',
           'remotion/src/ShotInformation.tsx', 'remotion/package-lock.json', 'config/text-style.json')
VISUAL_SOURCES = SOURCES[1:] + ('remotion/src/visualEntry.tsx', 'remotion/src/VisualNarrative.tsx')


def render(props, output, log, *, preview=False, encode_profile=None, visual=False):
    chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    args = [ROOT/'remotion/node_modules/.bin/remotion', 'render',
            'src/visualEntry.tsx' if visual else 'src/index.tsx', 'Mechanical',
            Path(output).resolve(), '--props', Path(props).resolve(), '--codec', 'h264', '--audio-codec', 'aac',
            '--pixel-format', 'yuv420p', '--concurrency', '2', '--browser-executable', chrome,
            '--gl', 'angle', '--log', 'error']
    if preview:
        args += ['--scale', '0.5', '--crf', '25']
    elif encode_profile == 'witness-v1':
        args += ['--image-format', 'png', '--crf', '12', '--timeout', '120000']
    elif encode_profile is not None:
        raise ValueError('Unknown Remotion encode profile')
    run(args, log, cwd=ROOT/'remotion')
