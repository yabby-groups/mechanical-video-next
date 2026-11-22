"""Render low-cost visual studies under the shared production lock."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.common import ROOT, filehash, writejson
from mechanical_video_next.blender_runtime import run_blender
from mechanical_video_next.workflow import lock


SAMPLES = {'nautical': (2, 7, 11, 16), 'optics': (1, 6.8, 11, 16.9)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--samples', action='store_true')
    parser.add_argument('--topic', choices=tuple(SAMPLES), action='append')
    options = parser.parse_args()
    source = ROOT/'blender/visual_story_studies.py'
    with lock(ROOT/'work/production.lock'):
        for topic in options.topic or SAMPLES:
            folder = options.output.resolve()/topic
            folder.mkdir(parents=True, exist_ok=False)
            command = ['--factory-startup', '--threads', '6', '--python-exit-code', '1',
                       '--python', str(source), '--', topic, str(folder)]
            if options.samples:
                for t in SAMPLES[topic]:
                    command.extend(('--sample', str(t)))
            start = time.monotonic()
            run_blender(command, log=folder/'render.log', name='visual-study')
            seconds = time.monotonic()-start
            print(f'{topic}: {seconds:.3f} seconds', flush=True)
            writejson(folder/'render-receipt.json', {
                'source': {'path': str(source), 'sha256': filehash(source)},
                'blend': {'path': str(folder/'scene.blend'), 'sha256': filehash(folder/'scene.blend')},
                'render_wall_seconds': round(seconds, 3),
                'sample_times': SAMPLES[topic] if options.samples else None,
                'frame_count': len(list(folder.glob('*.jpg'))),
            })


if __name__ == '__main__':
    main()
