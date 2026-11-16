#!/usr/bin/env -S uv run python
"""Opt-in real Blender integration smoke; never grants content acceptance."""
import json
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, Metrics, filehash, probe, writejson
from produce import asset, make_shot, compose
from mechanical_video_next.workflow import create_task, lock
from mechanical_video_next.provenance import binding, validate as validate_provenance


def main():
    started = time.time()
    folder = ROOT/'output/pipeline-smoke-20261116'
    folder.mkdir(exist_ok=True)
    report = dict(status='RUNNING', formal_acceptance=False, delivered=False)
    try:
        cfg = json.loads((ROOT/'config/planetary-01.json').read_text())
        cfg.update(id='pipeline-smoke-20261116', requested_routes=['3d'], render_route='3d',
                   production_scope='pipeline-test')
        cfg['storyboard'] = [cfg['storyboard'][3]]
        cfg['shots'] = {'motion': dict(cfg['shots']['motion'], pipeline_smoke='20261116')}
        cfg['render']['preview_native'] = True
        writejson(folder/'config.json',cfg)
        report['current_function'] = 'workflow.create_task'
        task = create_task('行星齿轮生产管线测试', root=folder/'tasks', routes='3d',
                           voice='Neil',config=folder/'config.json')
        report['task'] = str(task)
        metrics = Metrics(cfg['id'])
        with lock(ROOT/'work/production.lock'):
            report['current_function'] = 'produce.asset'
            model = asset(metrics)
            report['current_function'] = 'produce.make_shot'
            shot = make_shot(cfg['shots']['motion'],'preview',model,metrics,cfg['render'])
            report['render'] = dict(path=str(shot[0]), sha256=filehash(shot[0]))
            checks = json.loads((shot[0].parent/'checks.json').read_text())
            proof = dict(media=binding(shot[0]), shots=[dict(shot_id='motion',
                scene=checks['scene_artifact'], render_output=binding(shot[0]),
                motion_data=binding(shot[0].parent/'checks.json'), verification_frames=[1,120,240],
                model_assets=[dict(binding(model), source='Original CC0 teaching assembly; config/assembly.json')],
                product_references=[binding(ROOT/'assets/assemblies/planetary-teaching-v1/provenance.json')])],
                build=dict(frame_count=240,segments=[dict(shot_id='motion',start_frame=0,
                    frame_count=240,render_output=binding(shot[0]))]))
            writejson(folder/'3d-provenance.json',proof)
            report['current_function'] = 'produce.compose'
            compose(cfg,'final',{'motion':shot},metrics)
        report['current_function'] = 'provenance.validate(preview)'
        report['preview_provenance'] = validate_provenance(folder/'3d-provenance.json',stage='preview')
        target = ROOT/'output'/f'{cfg["id"]}-final.mp4'
        info = probe(target)
        video = next(s for s in info['streams'] if s['codec_type']=='video')
        report.update(status='TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO',
            media=dict(path=str(target),sha256=filehash(target)),
            duration=float(info['format']['duration']), resolution=[video['width'],video['height']],
            fps=video['avg_frame_rate'], audio=[s for s in info['streams'] if s['codec_type']=='audio'],
            metrics=metrics.finish(status='passed'), failed_function=None)
        report.pop('current_function',None)
    except Exception as error:
        report.update(status='FAIL',error=str(error),failed_function=report.get('current_function'),
                      traceback=traceback.format_exc())
        raise
    finally:
        report['elapsed_seconds'] = round(time.time()-started,3)
        writejson(folder/('result-'+str(time.time_ns())+'.json'),report)
        writejson(folder/'result.json',report)
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
