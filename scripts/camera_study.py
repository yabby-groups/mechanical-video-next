#!/usr/bin/env -S uv run python
"""Reproducible correction-tape camera experiment using the existing shot producer."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, Metrics, filehash, writejson, run
from clean import production_lock
from produce import make_shot

OUT = ROOT / 'output/camera-study'
ASSEMBLY = ROOT / 'output/tasks/workflow-acceptance-20261118/asset/spring-assembly.v1.json'
ASSET = ROOT / 'work/cache/assets/249fccc0ceb05ea37fe46e86eab37e076b7fc3b5e387fea02d08d9a5c2ece5af/assembly.blend'
BASE = ROOT / 'remotion/public/cache/3947031e9a2082d48501914ea3a9c11f5fdfc40d76fde3d251d43c3a0881abc1.mp4'


def prepare():
    original = json.loads((OUT / 'A.shot.json').read_text())
    for version in ('B', 'C'):
        shot = copy.deepcopy(original)
        shot['scene_artifact_dir'] = str(OUT / 'scenes')
        spec = shot['science']
        spec.pop('camera_clip', None)
        spec['camera_rig'] = dict(version=1, mode='DOLLY', lens_mm=55, clip=[.0001, 2],
                                  inspect_markers=['Belt_witness', 'Supply_witness'])
        direction = [.04, -.40, 1]
        if version == 'B':
            # Editorial Boolean cutaway of the same static shell: no invented
            # disassembly and no stochastic transparent-surface noise.
            shot['visible_parts'].append('Housing_cover')
            shot['section_plane']=dict(axis='y',side='negative',offset=-.014,parts=['Housing_cover'],
                                       offset_keys=[[0,-.014],[.22,.04],[1,.04]])
            values = [(0, [-.003, -.002, .007], .125),
                      (.22, [-.018, -.0177, .0085], .034),
                      (.86, [-.018, -.0177, .0085], .034),
                      (1, [-.008, -.008, .008], .075)]
        else:
            values = [(0, [-.018, -.014, .0085], .060),
                      (.16, [-.018, -.0177, .0085], .037),
                      (.88, [-.018, -.0177, .0085], .037),
                      (1, [-.010, -.010, .008], .065)]
            spec['camera_rig']['follow'] = dict(object='Supply_witness', weight=.4)
        spec['camera_path'] = [dict(progress=t, target=c, direction=direction, width=w) for t,c,w in values]
        writejson(OUT / f'{version}.shot.json', shot)
    writejson(OUT / 'experiment.json', dict(
        status='EXPERIMENTAL', knowledge_ids=['K07'], source_interval=[78.26666666666667,90.7],
        baseline=str(ROOT / 'output/audience-film/neil-revision-final.mp4'),
        baseline_sha256=filehash(ROOT / 'output/audience-film/neil-revision-final.mp4'),
        source_media=str(BASE), source_sha256=filehash(BASE), asset=str(ASSET), asset_sha256=filehash(ASSET),
        source_shot_sha256=filehash(OUT/'A.shot.json'), frame_count=373, fps=30,
        audio='All three comparisons silent; full-film candidate retains measured Neil',
        comparison_scope='Same complete prescribed 7.5 mm short contact interval; not a whole-life slip rate or physical simulation',
        tokens=None, cost=None))


def render(version, phase):
    shot = json.loads((OUT/f'{version}.shot.json').read_text())
    input_source = OUT/f'{version}.shot.json'
    if version=='C' and phase=='final':
        input_source=OUT/'production-config.candidate.json'
        compiled=json.loads(input_source.read_text())['shots']['slip']
        for key in ('tracks','mesh_tracks','visible_parts','science'):
            if compiled.get(key) != shot.get(key):
                raise ValueError('Blueprint compiled shot differs from experiment: '+key)
        shot=compiled
    render_spec = dict(width=1920 if phase=='final' else 960, height=1080 if phase=='final' else 540,
                       fps=30, framing='fullframe', preview_native=True, chunk_frames=3 if phase=='final' else 6)
    metrics = Metrics(f'camera-study/{version}-{phase}')
    with production_lock():
        media, kind, key = make_shot(shot, 'keys' if phase=='keys' else 'final', ASSET, metrics, render_spec, ASSEMBLY)
    record = dict(version=version, phase=phase, cache_key=key, media=str(media),
                  checks=str(media.parent/'checks.json'), source_shot_sha256=filehash(OUT/f'{version}.shot.json'),
                  production_input=str(input_source), production_input_sha256=filehash(input_source))
    if phase != 'keys':
        target = OUT/f'{version}{"-preview" if phase=="preview" else "-native"}.mp4'
        shutil.copy2(media, target)
        record.update(export=str(target), sha256=filehash(target))
    writejson(OUT/f'{version}-{phase}.json', record)
    metrics.finish(tokens=None, cost=None, quality_accepted=False)
    return record


def comparable():
    for version in ('A','B','C'):
        render_data_clip('final',version)
    for version in ('A','B','C'):
        source=OUT/f'{version}-data-render.mp4'
        filters = 'fps=30,setsar=1'
        run(['ffmpeg','-v','error','-y','-i',source,'-an','-vf',filters,
             '-frames:v','373','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p',
             '-movflags','+faststart',OUT/f'{version}.mp4'], OUT/f'{version}-encode.log')
        run(['ffmpeg','-v','error','-xerror','-i',OUT/f'{version}.mp4','-f','null','-'],OUT/f'{version}-decode.log')


def data_information(phase):
    receipt=json.loads((OUT/f'C-{phase}.json').read_text())
    path=Path(receipt['checks'])
    rows=json.loads(path.read_text())['checks']['camera_rig']['frames']
    duration=len(rows)/30
    result=[]
    for name,label,box in [('Supply_witness','轮缘标记',[64,802,940,914]),
                            ('Belt_witness','环带标记',[980,802,1856,914])]:
        result.append(dict(type='value',prefix=label,unit=' mm',digits=2,time=[0,duration],box=box,
                           samples=[[i/len(rows),row['markers'][name]['path_m']*1000]
                                    for i,row in enumerate(rows)]+[[1,rows[-1]['markers'][name]['path_m']*1000]],
                           basis=dict(path=str(path),sha256=filehash(path),
                                      position='Every-frame evaluated mesh-centroid path_m; prescribed model, not measured slip')))
    return result


def render_data_clip(phase,version='C'):
    from mechanical_video_next.remotion_build import render
    from produce import expose
    props=json.loads((ROOT/'output/audience-film/neil-revision-final.props.json').read_text())
    raw=BASE if version=='A' else OUT/(f'{version}-preview.mp4' if phase=='preview' else f'{version}-native.mp4')
    silent=OUT/'silent.m4a'
    if not silent.exists():
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t',str(373/30),
             '-c:a','aac',silent],OUT/'silent.log')
    source=next(s for s in props['shots'] if s['id']=='slip')
    source.update(media=expose(raw,filehash(raw)),audio=expose(silent,filehash(silent)),
                  information=data_information(phase) if version=='C' else [],
                  scienceLabel='模型行程 · 非实测' if version=='C' else None)
    props.update(title='轮缘与环带',fullframe_credit='',fullframe_caption='',shots=[source],cues=[],duration=373/30,
                 text_layout_items=[])
    path=OUT/f'{version}-data-{phase}.props.json'
    target=OUT/(f'{version}-preview-data-v2.mp4' if phase=='preview' else f'{version}-data-render.mp4')
    marker=target.with_suffix('.inputs.json')
    from common import digest
    identity=digest(props)
    if target.exists() and marker.exists():
        bound=json.loads(marker.read_text())
        if bound.get('props_digest')==identity and bound.get('sha256')==filehash(target): return
    writejson(path,props)
    with production_lock():
        render(path,target,OUT/f'{version}-data-{phase}.render.log',preview=phase=='preview',
               encode_profile=None if phase=='preview' else 'progression-witness-v1',visual=True,progression=True)
    writejson(marker,dict(props_digest=identity,sha256=filehash(target),props_path=str(path),props_sha256=filehash(path)))


def full_plan():
    """Compile a draft of the current Blueprint; no acceptance/promotion is implied."""
    from mechanical_video_next.blueprint import compile_config
    source=ROOT/'output/tasks/workflow-acceptance-20261118/handoffs/creative-blueprint.v11.json'
    blueprint=json.loads(source.read_text())['payload']
    props=json.loads((ROOT/'output/audience-film/neil-revision-final.props.json').read_text())
    narration=json.loads((ROOT/'output/audience-film/neil-revision.json').read_text())
    # Current measured audio subdivides sentences differently from the source script.
    # Bind the actual utterance/caption segmentation used by the baseline render.
    for shot in blueprint['shots']:
        narration[shot['shot_id']]=[c['text'] for c in props['cues']
                                  if shot['time_range'][0] <= c['start'] < shot['time_range'][1]]
    base=ROOT/'output/tasks/workflow-acceptance-20261118/production-config.json'
    # The existing source assembly identity is preserved; only camera settings change.
    cfg=json.loads(base.read_text())
    original=json.loads((OUT/'A.shot.json').read_text())
    # The latest task config contains a later spring repair. The audience baseline
    # reuses the earlier exact slip clip, so bind its actual source explicitly.
    original['visual']=cfg['shots']['slip']['visual']
    original['scene_artifact_dir']=str(OUT/'scenes')
    cfg['shots']['slip']=original
    identity=cfg['asset']
    base_copy=OUT/'baseline-config.bound.json'
    writejson(base_copy,cfg)
    del cfg
    blueprint['status']='DRAFT'
    blueprint['presentation_style']='natural_science'
    new=json.loads((OUT/'C.shot.json').read_text())
    decisions=[]
    for shot in blueprint['shots']:
        sid=shot['shot_id']
        shot['narration']=narration[sid]
        shot['comprehension']['narration']=narration[sid][0]
        shot['subtitles']=[c['text'] for c in props['cues']
                           if shot['time_range'][0] <= c['start'] < shot['time_range'][1]]
        shot['overlays']=[s for s in shot['overlays'] if '原理示意' not in s and '教学动画' not in s]
        if shot['render_engine']=='blender': shot['asset']=identity
        action='RETAIN'
        reason='Retain baseline composition/action; no observed camera defect justifies changing this shot'
        if sid=='slip':
            shot['camera'].update(preset='follow', settings={'science':{
                key:new['science'][key] for key in ('camera_path','camera_rig')}})
            shot['direction']['composition']='Observe the same lower wrap; follow only 40% of the actual blue marker motion, with initial and final wider context'
            shot['direction']['continuity']='Preserve contact side and screen direction; fixed 55 mm perspective; no orbit or camera crossing'
            action='EXPERIMENTAL_REPLACEMENT'
            reason='Full-context evaluation of tracking and parameter overlay; no claim C beats A; sensory QA UNKNOWN'
        decisions.append(dict(shot_id=sid,action=action,reason=reason,time_range=shot['time_range']))
    blueprint['camera_study']={'status':'EXPERIMENTAL','candidate':'C','winner':None,
                               'source_blueprint':str(source),'source_sha256':filehash(source),
                               'baseline_props_sha256':filehash(ROOT/'output/audience-film/neil-revision-final.props.json')}
    def current_narration(value):
        if isinstance(value,dict):
            sid=value.get('shot_id')
            if sid in narration and isinstance(value.get('narration'),str) and value['narration'] not in narration[sid]:
                value['narration']=narration[sid][0]
            for item in value.values(): current_narration(item)
        elif isinstance(value,list):
            for item in value: current_narration(item)
    current_narration(blueprint['growth_goals'])
    # The actual revised hook asks the question; it does not speak the old answer.
    answer=blueprint['growth_goals']['retention']['first_answer']
    answer.update(shot_id='slip',time_range=[82.34966666666666,86.08566666666667],
                  narration='这点相对滑动，让收卷速度能跟上底膜。',
                  knowledge_point='相对滑动允许收卷速度匹配底膜',
                  planned_action='Same two painted surfaces advance at different rates in the verified contact wrap',
                  visual_proof='Continuous native surface markers; independent viewing remains UNKNOWN')
    blueprint['growth_goals']['retention']['first_answer_time']=82.34966666666666
    blueprint['first_answer_time']=82.34966666666666
    writejson(OUT/'creative-blueprint.candidate.json',blueprint)
    writejson(OUT/'shot-decisions.json',{'shots':decisions,'promotion':'NONE'})
    result=compile_config(OUT/'creative-blueprint.candidate.json',base_copy,OUT/'production-config.candidate.json',draft=True)
    writejson(OUT/'blueprint-compilation.json',result)


def full_film(preview):
    """Use the same Remotion renderer and exact measured narration/cues as baseline."""
    from mechanical_video_next.remotion_build import render
    from produce import expose
    props=json.loads((ROOT/'output/audience-film/neil-revision-final.props.json').read_text())
    # Native text/value components use the existing CJK font path and collision rules.
    # The earlier libass experiment is retained as failed evidence, never reused.
    media=OUT/('C-preview.mp4' if preview else 'C-native.mp4')
    for shot in props['shots']:
        if shot['id']=='slip':
            shot.update(media=expose(media,filehash(media)),information=data_information('preview' if preview else 'final'),
                        scienceLabel='模型行程 · 非实测')
    # Rebuild derived text receipts from current cues, rather than old copied labels.
    props['text_layout_items']=[item for item in props.get('text_layout_items',[]) if item.get('layer')!='subtitle']
    path=OUT/('animatic-v2.props.json' if preview else 'candidate.props.json')
    writejson(path,props)
    segment=OUT/('animatic-v2-segment.mp4' if preview else 'candidate-segment.mp4')
    target=OUT/('animatic-v2.mp4' if preview else 'correction-tape-camera-candidate.mp4')
    with production_lock():
        render(path,segment,
               OUT/('animatic-v2.log' if preview else 'candidate-render.log'),preview=preview,
               encode_profile=None if preview else 'progression-witness-v1',visual=True,progression=True,
               frame_range=[2348,2720])
        scale=',scale=960:540' if preview else ''
        graph=(f'[0:v]trim=end_frame=2348,setpts=PTS-STARTPTS{scale}[before];'
               f'[1:v]setpts=PTS-STARTPTS[replacement];'
               f'[0:v]trim=start_frame=2721,setpts=PTS-STARTPTS{scale}[after];'
               '[before][replacement][after]concat=n=3:v=1:a=0[out]')
        baseline=ROOT/'output/audience-film/neil-revision-final.mp4'
        run(['ffmpeg','-v','error','-y','-i',baseline,'-i',segment,'-filter_complex',graph,
             '-map','[out]','-map','0:a:0','-c:v','libx264','-preset','fast','-crf','25' if preview else '12',
             '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',target],
            OUT/('animatic-v2-splice.log' if preview else 'candidate-splice.log'))
        run(['ffmpeg','-v','error','-xerror','-i',target,'-f','null','-'],target.with_suffix('.decode.log'))
    writejson(target.with_suffix('.build.json'),dict(status='EXPERIMENTAL_UNACCEPTED',
              baseline=dict(path=str(baseline),sha256=filehash(baseline)),
              replacement=dict(path=str(segment),sha256=filehash(segment),source_interval_frames=[2348,2721]),
              props=dict(path=str(path),sha256=filehash(path)),
              output=dict(path=str(target),sha256=filehash(target)),
              audio='Exact baseline AAC packets copied; no speed or time change',
              method='Existing Remotion renders the changed Blueprint shot in full timeline context; FFmpeg reuses the other 12 shots and concatenates on the exact 30 fps frame grid'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['prepare','keys','preview','final','compare','full-plan','animatic','film','data-preview'])
    p.add_argument('--version', choices=['B','C'])
    a=p.parse_args()
    if a.phase=='prepare': prepare()
    elif a.phase=='compare': comparable()
    elif a.phase=='full-plan': full_plan()
    elif a.phase=='data-preview': render_data_clip('preview')
    elif a.phase in {'animatic','film'}: full_film(a.phase=='animatic')
    else:
        if not a.version: p.error('--version required')
        print(json.dumps(render(a.version,a.phase)))


if __name__=='__main__': main()
