"""Compose the existing correction-tape workprint with an evidence-bound recap."""
import argparse
import json
import time

from common import ROOT, filehash, run, writejson
from produce import expose, validate_video
from mechanical_video_next.provenance import binding, bound, write_remotion_proof
from mechanical_video_next.remotion_build import render
from mechanical_video_next.three_d import validate_config
from mechanical_video_next.workflow import lock


BASELINE = 'correction-tape-principle-preview-v6-final'
DEMO = 'correction-tape-visual-narrative-demo-v2'


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=lambda path: ROOT / path, help='Existing preview-v6/render-config.json')
    args = parser.parse_args()
    output = ROOT / 'output'
    baseline = output / (BASELINE + '.mp4')
    proof = read(baseline.with_suffix('.3d-provenance.json'))
    props = read(baseline.with_suffix('.props.json'))
    prior = bound(proof['media'])
    cfg = read(args.config)
    if cfg.get('id') != 'correction-tape-principle-preview-v6':
        raise ValueError('This regression fixture requires the existing correction-tape v6 config')
    cfg.update(id=DEMO, visual_policy_version=2, production_scope='pipeline-test')
    cfg.pop('local_preview_shots', None)
    cfg['render']['encode_profile'] = 'witness-v1'
    props['encode_profile'] = 'witness-v1'
    props['visual_policy_version'] = 2
    designs = [
        ('mechanical_cutaway', 'medium', '斜前方', '压头与纸面', '压头压住纸面，转印位置随壳体移动。'),
        ('state_change', 'wide', '开壳斜俯视', '放卷与收卷的位置', '外壳打开后，底膜绕压头回到收卷盘。'),
        ('annotated_detail', 'macro', '摩擦环斜俯视', '摩擦环与放卷轮缘', '观察摩擦环相对于轮缘发生滑动。'),
    ]
    for row, (kind, scale, angle, focus, action) in zip(cfg['storyboard'], designs, strict=True):
        shot = cfg['shots'][row['shot']]
        shot['visual'] = dict(knowledge_goal=row['note'], visual_type=kind, visual_focus=focus,
            visual_action=action, render_engine='blender', camera=dict(preset='reveal', scale=scale, angle=angle),
            transition=dict(kind='cut', link='沿底膜路径从压头进入壳体，再看收卷传动。'),
            assets=[cfg['asset']], evidence=shot['science']['basis'], duration=row['seconds'],
            mechanical_role='core', knowledge_ids=[row['id']], progression=dict(kind='new', reason=action))
    diagram = 'film-route'
    seconds = 3
    graphic = dict(type='diagram', title='白色涂层与底膜在这里分开', items=[
        dict(label='放卷', detail='带着白色涂层'),
        dict(label='压头', detail='白色涂层留在纸上'),
        dict(label='收卷', detail='底膜返回壳内'),
    ])
    cfg['shots'][diagram] = dict(template='editorial', seconds=seconds, graphic=graphic,
        visual=dict(knowledge_goal='回顾底膜的去向', visual_type='abstract_phenomenon',
            visual_focus='压头前后底膜与涂层的去向', visual_action='依次高亮放卷、转印和收卷',
            render_engine='remotion', camera=dict(scale='diagram', angle='流程横向'),
            transition=dict(kind='cut', link='把刚看见的卷盘和压头对应到路径，再回到收卷驱动。'),
            assets=[], evidence=cfg['shots']['apply']['science']['basis'] + cfg['shots']['reveal']['science']['basis'],
            duration=seconds, mechanical_role='support', knowledge_ids=['apply', 'reveal'],
            progression=dict(kind='recap', reason='确认涂层留纸与底膜返回的位置关系。')))
    cfg['storyboard'].insert(2, dict(id=diagram, shot=diagram, seconds=seconds,
        narration=['白色涂层留在纸上，底膜返回壳内。'], subtitles=[]))
    validate_config(cfg)
    media = {s['shot_id']: (bound(s['render_output']), 'video', s['cache_key']) for s in proof['shots']}
    assets = proof['shots'][0]['model_assets']
    target = output / (DEMO + '.mp4')
    props_path = target.with_suffix('.props.json')
    started = time.monotonic()
    with lock(ROOT / 'work/production.lock'):
        silence = output / (DEMO + '-pause.m4a')
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anullsrc=r=48000:cl=stereo',
             '-t',str(seconds),'-c:a','aac',silence], target.with_suffix('.silence.log'))
        props['shots'].insert(2, dict(id=diagram, kind='graphic', seconds=seconds, graphic=graphic,
                                    audio=expose(silence, filehash(silence))))
        for cue in props['cues']:
            if cue['start'] >= 8:
                cue['start'] += seconds
                cue['end'] += seconds
        props['duration'] += seconds
        writejson(props_path, props)
        render(props_path, target, target.with_suffix('.render.log'), visual=True, encode_profile='witness-v1')
        validate_video(target, cfg, props['cues'])
        write_remotion_proof(target.with_suffix('.3d-provenance.json'), target, props_path,
                             cfg, media, bound(assets[0]), bound(assets[1]))
    writejson(target.with_suffix('.comparison.json'), {
        'baseline': binding(prior), 'demo': binding(target),
        'baseline_seconds': 15, 'demo_seconds': 18, 'scene_count': [3, 4],
        'blender_clips_reused': len(media), 'blender_render_seconds_this_run': 0,
        'composition_and_validation_seconds': round(time.monotonic()-started, 3),
        'native_agent_calls': 0, 'native_agent_cost': None, 'comprehension': 'UNKNOWN',
        'exact_whole_shot_reuse_within_each_film': [0, 0],
        'recap_seconds': 3, 'accepted': False,
    })


if __name__ == '__main__':
    main()
