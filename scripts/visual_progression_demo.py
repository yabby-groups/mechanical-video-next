"""Reproduce the correction-tape progression demonstration from local 3D sources."""
import argparse
import importlib.util
import json
from pathlib import Path

from common import ROOT, Metrics, filehash, run, writejson
from produce import expose, make_shot, validate_video
from mechanical_video_next.provenance import binding, bound, write_remotion_proof
from mechanical_video_next.remotion_build import render
from mechanical_video_next.three_d import validate_config
from mechanical_video_next.workflow import lock


DEMO = 'correction-tape-visual-progression-demo'
DELIVERY = DEMO + '-v2'
OUTPUT = ROOT / 'output'


def read(path):
    return json.loads(path.read_text())


def configure(task):
    base = read(task / 'preview-v6/render-config.json')
    original = read(task / 'preview-v2/render-config.json')
    module_spec = importlib.util.spec_from_file_location('correction_tape_preview', task / 'preview-v3.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    reveal, slip = (base['shots'][name] for name in ('reveal', 'slip'))
    for shot in (reveal, slip):
        shot['scene_artifact_dir'] = str(OUTPUT / DEMO / 'scenes')
    for category in ('tracks', 'mesh_tracks'):
        lid = [t for t in reveal[category] if t['object'] == 'Housing_cover']
        active = [(0, 0), (.15, 0), (.94, .73), (1, .73)]
        reveal[category] = lid + [
            module.retime(track, active) for track in original['shots']['reveal'][category]
            if track['object'] != 'Housing_cover'
        ]
    module.set_camera(reveal, module.pose(0, (0, 0, 4), [.08, -.28, 1], 108),
                      module.pose(.16, (-4, 0, 4), [.03, -.20, 1], 81),
                      module.pose(1, (-4, 0, 4), [.03, -.20, 1], 81))
    for i, guide in enumerate(reveal['science']['guides']):
        guide['window'] = [.10, .56] if i < 2 else [.16, 1]
        if i >= 2:
            guide['width'] *= 1.35
    slip['seconds'] = 6
    module.set_camera(slip, module.pose(0, (-18, -7, 8), [.04, -.26, 1], 54),
                      module.pose(1, (-18, -7, 8), [.04, -.26, 1], 54))
    slip['science']['guides'] = slip['science']['guides'][:2]
    for guide in slip['science']['guides']:
        guide['width'] *= 1.3
        guide['points'][0]['local'][2] += .003
    center = module.point('Supply_core', (0, 0, 12.5))
    for name, color in [('Supply_witness', module.BLUE), ('Belt_witness', module.ORANGE)]:
        tip = module.point(name, (0, 0, 4.06))
        slip['science']['guides'].append(module.guide('arrow', color, .53, [0, 1], center, tip))
    slip['science']['scope'] += '; both radial guides share the supply axis and end at evaluated marker positions'
    return json.loads(json.dumps(base))


def compose_demo(cfg, old, work, proof, assembly, model):
    props = read(old.with_suffix('.props.json'))
    cfg.update(id=DELIVERY, visual_policy_version=2, knowledge_progression_version=1,
               production_scope='pipeline-test')
    profile = 'progression-witness-v1'
    cfg['render']['encode_profile'] = profile
    cfg.pop('local_preview_shots', None)
    diagram = {
        'type': 'angular_comparison', 'title': '同样带长，转角不同',
        'travel': 3.141592653589793,
        'items': [{'label': '小半径', 'radius': 1}, {'label': '大半径', 'radius': 2}],
    }
    diagram_id = 'angle'
    cfg['shots'][diagram_id] = {'template': 'editorial', 'seconds': 3, 'graphic': diagram}
    cfg['storyboard'].insert(2, dict(id=diagram_id, shot=diagram_id, seconds=3,
        narration=['同样带长，小半径转过的角度更大。'], subtitles=[]))
    basis = cfg['shots']['slip']['science']['basis']
    derivation = work / 'angular-derivation.md'
    derivation.write_text(
        'Ideal geometry comparison. For a circular effective radius r and no slip at the ribbon layer, '
        'the traversed arc length is s = r times theta. The same illustrative arc length pi at '
        'dimensionless radii 1 and 2 gives angles pi and pi/2. The two bars show equal travelled '
        'length. These values illustrate the relation and are not Sanford product dimensions, '
        'operating angles, or a contact simulation. US8746316B2 Figs. 4B–4C discuss changing roll '
        'diameters and slipping of rim 109 relative to loop 104.\n')
    claims = [
        ('transfer', '纸上的白条随压头移动而延长', '斜前', '压头与纸面', 'change',
         ['压头前是印字', '压头经过后白条覆盖印字'], 'mechanical_cutaway', 'medium'),
        ('radii', '放卷缩小，收卷增大', '开壳斜俯', '供带和收带的边界', 'change',
         ['两卷与各自初始标尺齐平', '左卷边缘向内退，右卷边缘越过基准'], 'state_change', 'wide'),
        ('angle', '同一段带在不同半径上转过不同角度', '正视', '等长带与转角', 'comparison',
         ['两指针对准各自起点', '等长条同步走完，两指针分别转半圈和四分之一圈'], 'design_comparison', 'diagram'),
        ('slip', '轮缘与摩擦环产生相对位移', '同轴斜俯', '供卷轮缘和摩擦环', 'cause',
         ['两个同轴标记带着初始角差移动', '蓝标相对橙标继续前移，角差扩大'], 'annotated_detail', 'macro'),
    ]
    prior = []
    for row, (claim, goal, angle, focus, kind, states, visual_type, scale) in zip(cfg['storyboard'], claims, strict=True):
        shot = cfg['shots'][row['shot']]
        row['seconds'] = shot['seconds']
        graphic = claim == 'angle'
        camera = {'scale': scale, 'angle': angle}
        if not graphic:
            camera['preset'] = 'reveal'
        window = [0, round(row['seconds'] * 30)]
        shot['visual'] = dict(
            knowledge_goal=goal, knowledge_ids=[claim], visual_type=visual_type, visual_focus=focus,
            visual_action='；'.join(states), camera=camera, duration=row['seconds'],
            render_engine='remotion' if graphic else 'blender', mechanical_role='support' if graphic else 'core',
            transition={'kind': 'cut', 'link': '沿底膜回带，解释换径后的转角需求和摩擦环相对位移。'},
            assets=[] if graphic else [cfg['asset']],
            evidence=basis + [dict(binding(derivation), position='s = rθ and equal arc length')]
            if graphic else shot['science']['basis'],
            progression=dict(kind='new', reason=goal, previous_ids=prior, observable=[
                dict(knowledge_id=claim, kind=kind, frames=window, states=states,
                     proof='animated_model' if graphic else 'physical_action')]))
        prior = [claim]
    validate_config(cfg)
    writejson(work / 'render-config.json', cfg)
    props.update(visual_policy_version=2, knowledge_progression_version=1, duration=17, encode_profile=profile)
    media = {'apply': (bound(proof['shots'][0]['render_output']), 'video', proof['shots'][0]['cache_key'])}
    for name, row in read(work / 'clips.json').items():
        media[name] = (Path(row['path']), row['kind'], row['key'])
    silence = work / 'comparison-pause.m4a'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
         '-t', '3', '-c:a', 'aac', silence], work / 'comparison-audio.log')
    for row in props['shots']:
        name = row['id']
        path, _, key = media[name]
        row['media'] = expose(path, key)
        row['seconds'] = cfg['shots'][name]['seconds']
        if name != 'apply':
            row['information'] = []
    props['shots'].insert(2, dict(id=diagram_id, kind='graphic', seconds=3, graphic=diagram,
                                audio=expose(silence, filehash(silence))))
    for cue in props['cues']:
        if cue['start'] >= 8:
            cue['start'] += 3
            cue['end'] += 3
    target = OUTPUT / (DELIVERY + '.mp4')
    props_path = target.with_suffix('.props.json')
    writejson(props_path, props)
    render(props_path, target, work / 'remotion-v2.log', visual=True, progression=True, encode_profile=profile)
    validate_video(target, cfg, props['cues'])
    write_remotion_proof(target.with_suffix('.3d-provenance.json'), target, props_path,
                         cfg, media, assembly, model)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', type=Path)
    parser.add_argument('phase', choices=('keys', 'clips', 'final'))
    args = parser.parse_args()
    work = OUTPUT / DEMO
    work.mkdir(parents=True, exist_ok=True)
    cfg = configure(args.task)
    old = OUTPUT / 'correction-tape-principle-preview-v6-final'
    proof = read(old.with_suffix('.3d-provenance.json'))
    assets = proof['shots'][0]['model_assets']
    model = bound(assets[1])
    assembly = cfg['assembly_config']
    metrics = Metrics(DEMO + '-' + args.phase)
    with lock(ROOT / 'work/production.lock'):
        if args.phase == 'final':
            compose_demo(cfg, old, work, proof, bound(assets[0]), model)
        else:
            quality = 'keys' if args.phase == 'keys' else 'final'
            shots = {}
            for name in ('reveal', 'slip'):
                path, kind, key = make_shot(cfg['shots'][name], quality, model, metrics, cfg['render'], assembly)
                shots[name] = {'path': str(path), 'kind': kind, 'key': key}
            writejson(work / (args.phase + '.json'), shots)
        writejson(work / (args.phase + '-metrics.json'), metrics.finish(status='passed'))


if __name__ == '__main__':
    main()
