#!/usr/bin/env -S uv run python
"""Inspect one existing EAS shot before committing to an entire style render."""
import argparse
import copy
import json
from pathlib import Path
import sys
import threading

import produce
from common import ROOT, Metrics, budget, filehash, writejson
sys.path.insert(0,str(ROOT))
from mechanical_video_next.workflow import lock


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('config',type=Path)
    ap.add_argument('--shot',default='motion')
    ap.add_argument('--phase',choices=['keys','preview','final'],default='keys')
    args=ap.parse_args()
    cfg=json.loads(args.config.read_text())
    cfg['id'] += '-'+args.shot+'-lookdev'
    cfg['storyboard']=[copy.deepcopy(next(s for s in cfg['storyboard'] if s['shot']==args.shot))]
    cfg['shots']={args.shot:cfg['shots'][args.shot]}
    metrics=Metrics(cfg['id']+'-'+args.phase)
    stopped=threading.Event()
    errors=[]
    def sample():
        while not stopped.wait(0.5):
            try: metrics.peak=max(metrics.peak,budget())
            except Exception as error: errors.append(str(error)); return
    thread=threading.Thread(target=sample,daemon=True)
    thread.start()
    status='passed'
    try:
        with lock(ROOT/'work/production.lock'):
            model=produce.asset(metrics)
            result=produce.make_shot(cfg['shots'][args.shot],args.phase,model,metrics,cfg['render'])
            if args.phase!='keys': produce.compose(cfg,args.phase,{args.shot:result},metrics)
            if errors: raise RuntimeError(errors[0])
            writejson(ROOT/'output/style-review'/f'{cfg["id"]}-{args.phase}.json',
                      {'config':str(args.config),'config_sha256':filehash(args.config),
                       'model':str(model),'model_sha256':filehash(model),
                       'shot_cache_key':result[2],'phase':args.phase,
                       'quality_acceptance':'UNKNOWN'})
    except Exception:
        status='failed'
        raise
    finally:
        stopped.set()
        thread.join()
        metrics.finish(status=status,quality_acceptance='UNKNOWN')


if __name__=='__main__': main()
