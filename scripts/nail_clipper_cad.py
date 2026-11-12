"""Reuse authored nail-clipper CAD and prepare timeline-bound EAS shots.

Use uv run --extra cad python this_file --generate
to regenerate solids. No Blender processes are launched by this tool.
"""
import argparse
import copy
import hashlib
import json
import runpy
import bisect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets/assemblies/nail-clipper-cad-v5'


def read(p):
    return json.loads(p.read_text())


def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n')


def smooth(t):
    t = max(0., min(1., t))
    return t*t*(3-2*t)


def phase(ident, t):
    if ident == 'return':
        return smooth(t/.18) if t < .18 else 1. if t < .35 else 1-smooth((t-.35)/.65)
    return smooth(t/.30) if t < .30 else 1. if t < .65 else 1-smooth((t-.65)/.35)


def mix(a, b, t):
    if isinstance(a, list):
        return [mix(x, y, t) for x, y in zip(a, b)]
    return a*(1-t)+b*t


def sample_track(track, ident):
    source = track['poses']
    qs = [p['progress'] for p in source]
    poses = []
    for i in range(121):
        t = i/120
        q = phase(ident, t)
        hi = min(len(qs)-1, max(1, bisect.bisect_left(qs, q)))
        lo = hi-1
        ratio = (q-qs[lo])/(qs[hi]-qs[lo])
        pose = {'progress': t}
        for key in source[lo]:
            if key != 'progress':
                pose[key] = mix(source[lo][key], source[hi][key], ratio)
        poses.append(pose)
    return dict(object=track['object'], poses=poses)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--generate', action='store_true')
    ap.add_argument('--timeline', type=Path)
    ap.add_argument('--output', type=Path, default=ROOT/'output/nail-clipper/3d/config')
    args = ap.parse_args()
    if args.generate:
        runpy.run_path(str(ASSET/'generate.py'), run_name='__main__')
    if not args.timeline:
        return
    timeline = read(args.timeline)
    motion = read(ASSET/'motion.json')
    style_path = ROOT/'config/nail-clipper-studio-style.json'
    style = read(style_path)
    manifest = []
    combined_shots = {}
    combined_storyboard = []
    for item in timeline['shots']:
        shot_id = item['id']
        kind = 'exploded' if shot_id == 'parts' else 'open' if shot_id == 'return' else 'close'
        cfg = read(ROOT/f'config/nail-clipper-diagnostic-v5-{kind}.json')
        # Bound 1080p transient PNG batches while retaining one Blender process.
        cfg['render']['chunk_frames'] = 8
        shot = cfg['shots'][kind]
        shot['seconds'] = item['seconds']
        if shot_id in ('hook', 'lever', 'cut', 'summary', 'return'):
            # q(t) is shared with the 2D route. Source geometry is sampled in q,
            # then interpolated into 121 temporal positions, including hold poses.
            for channel in ('tracks', 'mesh_tracks'):
                shot[channel] = [sample_track(track, shot_id) for track in motion.get(channel, [])]
            shot['phase_contract'] = '121 temporal samples; shared smoothstep close/hold/open q(t); prescribed deformation'
        if shot_id == 'cut':
            shot.update(camera_view='oblique', camera_direction=[0, -1, .15],
                        section_plane={'axis': 'y', 'side': 'negative', 'offset': 0},
                        observation_view='Longitudinal Boolean section exposing cam bearing and opposed jaws; teaching cutaway')
        if shot_id == 'parts':
            # Explosion followed by reassembly; visualization offsets, not removal physics.
            for track in shot['tracks']:
                poses = track['poses']
                poses[0]['progress'] = 0
                poses[-1]['progress'] = .5
                track['poses'].append(dict(copy.deepcopy(poses[0]), progress=1))
        shot['studio_lighting'] = copy.deepcopy(style['studio_lighting'])
        shot.update(copy.deepcopy(style['shots'][shot_id]))
        shot['visual_style_source'] = {'path': str(style_path.relative_to(ROOT)),
                                      'sha256': hashlib.sha256(style_path.read_bytes()).hexdigest()}
        shot['id'] = shot_id
        cfg.update(id='nail-clipper-three-routes-3d-'+shot_id,
                   local_preview_shots=[shot_id], shots={shot_id: shot})
        cfg['storyboard'] = [dict(id=shot_id, shot=shot_id, seconds=item['seconds'],
                                 narration=[item.get('narration', '原理示意')],
                                 subtitles=['原理示意'])]
        path = args.output/(shot_id+'.json')
        dump(path, cfg)
        combined_shots[shot_id] = shot
        combined_storyboard.extend(cfg['storyboard'])
        manifest.append({'shot_id': shot_id, 'config': str(path.relative_to(ROOT)),
                         'seconds': item['seconds'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    cfg.update(id='nail-clipper-three-routes-3d', shots=combined_shots,
               storyboard=combined_storyboard, local_preview_shots=list(combined_shots))
    dump(args.output/'full.json', cfg)
    dump(args.output/'manifest.json', {'asset': str(ASSET.relative_to(ROOT)), 'shots': manifest,
         'render_command': 'uv run python scripts/produce.py output/nail-clipper/3d/config/full.json --phase local',
         'full_duration_seconds': sum(s['seconds'] for s in combined_storyboard),
         'boundary': 'Full configuration must satisfy existing 30..45s local-production duration validation. Short diagnostics remain separate <=5s configs.',
         'scope': 'Prescribed spring bending and geometric cam seat; no contact or flexible-material simulation'})


if __name__ == '__main__':
    main()
