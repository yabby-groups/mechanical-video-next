"""Run a short regression fixture, never create or approve a production task."""

import argparse
import json
from pathlib import Path
import sys
import threading
import time

from produce import ROOT, asset, compose, make_shot
from common import Metrics, budget, filehash, writejson
from narration import effective_profile, load_env
from mechanical_video_next.three_d import validate_config
from mechanical_video_next.workflow import lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['voice', 'preview', 'final', 'control'])
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    config_path = ROOT/'tests/fixtures/production/science-demo.json'
    cfg = json.loads(config_path.read_text())
    validate_config(cfg)
    load_env(args.env_file)
    metrics = Metrics('science-template-demo-' + args.phase)
    stopped = threading.Event()
    errors = []

    def monitor():
        while not stopped.wait(.5):
            try:
                metrics.peak = max(metrics.peak, budget())
            except RuntimeError as error:
                errors.append(str(error))
                return

    status = 'failed'
    with lock(ROOT/'work/production.lock'):
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        try:
            if args.phase == 'voice':
                from produce import tts
                for row in cfg['storyboard']:
                    tts(row, effective_profile(cfg), metrics)
            else:
                if args.phase == 'control':
                    cfg['id'] += '-control'
                    for row in cfg['storyboard']:
                        row.pop('information', None)
                quality = 'preview' if args.phase == 'preview' else 'final'
                assembly = cfg['assembly_config']
                model = asset(metrics, assembly)
                media = {name: make_shot(shot, quality, model, metrics, cfg['render'], assembly)
                         for name, shot in cfg['shots'].items()}
                compose(cfg, quality, media, metrics)
                target = ROOT/'output'/f'{cfg["id"]}-{quality}.mp4'
                bound = lambda path: {'path': str(path), 'sha256': filehash(path)}
                writejson(target.with_suffix('.scene-receipt.json'), {
                    'config': bound(config_path), 'assembly': bound(ROOT/assembly), 'media': bound(target),
                    'props': bound(target.with_suffix('.props.json')), 'formal_acceptance': False,
                    'scientific_review': 'UNKNOWN', 'visual_review': 'UNKNOWN', 'listening': 'UNKNOWN',
                    'shots': {name: {'render': bound(path), 'checks': bound(path.parent/'checks.json'),
                                     'scene': json.loads((path.parent/'checks.json').read_text())['scene_artifact']}
                              for name, (path, _, _) in media.items()},
                })
            if errors:
                raise RuntimeError(errors[0])
            status = 'passed'
        finally:
            stopped.set()
            thread.join()
            writejson(ROOT/'output/runs'/f'{metrics.name}-{time.time_ns()}.json',
                      metrics.finish(status=status, formal_acceptance=False, provider_cost=None))


if __name__ == '__main__':
    main()
