#!/usr/bin/env python3
"""Local deterministic production: asset -> keyframes -> preview -> shots -> Remotion.

Only transient PNG sequences owned by this run are removed after valid MP4 encoding.
No retry loops: a failed subprocess or assertion stops this invocation.
"""
import argparse
import array
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from common import ROOT, BLENDER, Metrics, budget, codehash, digest, filehash, probe, run, writejson

CACHE = ROOT/'work/cache'
PUBLIC = ROOT/'remotion/public/cache'

def cached(folder, files):
    marker = folder/'complete.json'
    if not marker.exists():
        return False
    try:
        m = json.loads(marker.read_text())
        return set(files)<=set(m) and all((folder/f).is_file() and filehash(folder/f)==h for f,h in m.items())
    except (KeyError, ValueError):
        return False

def complete(folder, files):
    writejson(folder/'complete.json',{f:filehash(folder/f) for f in files})

def assembly_spec(path=None):
    return json.loads((ROOT / (path or 'config/assembly.json')).read_text())

def asset_key(assembly_path=None):
    cfg = assembly_spec(assembly_path)
    sources = {s['path']:filehash(ROOT/s['path']) for s in cfg.get('source_files', [])}
    for s in cfg.get('source_files', []):
        if sources[s['path']] != s['sha256']:
            raise ValueError('Assembly source hash mismatch: '+s['path'])
    return digest({'config':cfg,'source':codehash('blender/scene.py','blender/vendor'),
                   'asset_sources':sources})

def asset(metrics, assembly_path=None):
    start=time.time()
    folder=CACHE/'assets'/asset_key(assembly_path)
    target=folder/'assembly.blend'
    files=['assembly.blend','assembly.inventory.json']
    hit=cached(folder,files)
    if not hit:
        folder.mkdir(parents=True,exist_ok=True)
        run([BLENDER,'-b','--factory-startup','--python-exit-code','1','--python',ROOT/'blender/scene.py','--','asset','--out',target,
             '--assembly-config',ROOT/(assembly_path or 'config/assembly.json')],folder/'build.log')
        inv=json.loads(target.with_suffix('.inventory.json').read_text())
        cfg=assembly_spec(assembly_path)
        assert set(cfg['required_parts']) <= {p['name'] for p in inv['parts']}
        assert inv['independent_meshes'] and all(p['vertices']>0 for p in inv['parts'])
        complete(folder,files)
    metrics.record('asset',start,hit,key=folder.name)
    return target

def panel_spec(render, quality):
    landscape = render['width'] > render['height']
    width, height = ((render['width'],render['height']) if render.get('framing')=='fullframe'
                     else (1120, 720) if landscape else (1080, 1250))
    return ((width//2, height//2, 15)
            if quality!='final' and not render.get('preview_native', False)
            else (width,height,30))

def shot_key(shot, quality, render=None, assembly_path=None):
    render = render or {'width':1080,'height':1920}
    inputs={'asset':asset_key(assembly_path),'shot':shot,'quality':quality,'panel':panel_spec(render,quality)}
    if shot.get('visual_profile'):
        inputs['visual_style_source']=codehash('blender/studio_style.py')
    return digest(inputs)

def make_shot(shot, quality, model, metrics, render=None, assembly_path=None):
    start=time.time()
    render = render or {'width':1080,'height':1920}
    width,height,fps = panel_spec(render,quality)
    if quality=='checks':
        fps=shot.get('diagnostic_fps',fps)
    key=shot_key(shot,quality,render,assembly_path)
    folder=CACHE/'shots'/key
    kind='image' if shot['template'] in ['overall','detail','exploded'] else 'video'
    filename='media.png' if kind=='image' else 'media.mp4'
    files=['checks.json'] if quality in {'keys','checks'} else [filename,'checks.json']
    hit=cached(folder,files)
    if not hit:
        folder.mkdir(parents=True,exist_ok=True)
        writejson(folder/'shot.json',shot)
        frames=folder/'frames'
        args=[BLENDER,'-b','--factory-startup','--python-exit-code','1','--python',ROOT/'blender/scene.py','--','shot','--asset',model,'--shot',folder/'shot.json','--out',frames,'--width',width,'--height',height,'--fps',fps]
        args += ['--assembly-config',ROOT/(assembly_path or 'config/assembly.json')]
        if quality=='keys': args+=['--keys']
        if quality=='checks': args+=['--checks-only']
        # Resume encoding without rerendering an already complete local frame sequence.
        expected = len(list((frames).glob('*.png')))
        needed = 1 if kind=='image' else round(shot['seconds']*fps)
        ready = quality not in {'keys','checks'} and (frames/'checks.json').exists() and expected==needed
        if not ready:
            # Conservative upper bound for an uncompressed RGB frame sequence plus PNG overhead.
            projected = budget() + width*height*3*needed*1.12
            if projected > 2*1024**3:
                raise RuntimeError('Projected temporary frame sequence exceeds 2 GiB work budget')
            run(args,folder/'blender.log')
        shutil.copy2(frames/'checks.json',folder/'checks.json')
        if quality not in {'keys','checks'}:
            if kind=='image': shutil.copy2(next(frames.glob('*.png')),folder/filename)
            else:
                run(['ffmpeg','-v','error','-y','-framerate',fps,'-i',frames/'%05d.png','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',folder/filename],folder/'encode.log')
                run(['ffmpeg','-v','error','-i',folder/filename,'-f','null','-'],folder/'decode.log')
                v=probe(folder/filename)['streams'][0]
                assert int(v['width'])==width and abs(float(v['duration'])-shot['seconds'])<0.1
            # Exact owned files only. Keyframes and originals are never removed here.
            for p in frames.glob('*.png'): p.unlink()
        elif quality=='keys':
            files += [str(p.relative_to(folder)) for p in sorted(frames.glob('*.png'))]
        complete(folder,files)
    metrics.record(quality+':'+shot['template'],start,hit,key=key)
    return folder/filename,kind,key

def tts(shot, voice, metrics):
    start=time.time()
    if isinstance(voice,dict):
        from narration import synthesize_shot
        path,cues,key,hit=synthesize_shot(shot,voice)
        metrics.record('tts:'+shot['id'],start,hit,key=key,model=voice['model'],voice=voice['voice'])
        return path,cues,key
    key=digest({'cues':shot['narration'],'voice':voice,'seconds':shot['seconds'],'rate':235,'audio_pipeline':1,
                'processing':codehash('scripts/produce.py')})
    folder=CACHE/'audio'/key
    files=['audio.m4a','cues.json']
    hit=cached(folder,files)
    if not hit:
        folder.mkdir(parents=True,exist_ok=True)
        cues=[]
        cursor=0.15
        inputs=[]
        for i,text in enumerate(shot['narration']):
            aiff=folder/f'{i}.aiff'
            run(['say','-v',voice,'-r','235','-o',aiff,text],folder/f'{i}-tts.log')
            duration=float(probe(aiff)['format']['duration'])
            assert duration>0.15, 'TTS returned empty audio'
            cues.append({'text':text,'start':round(cursor,3),'end':round(cursor+duration,3)})
            inputs+=['-i',aiff]
            cursor+=duration+0.12
        assert cursor<=shot['seconds']-0.1, f'Narration too long ({cursor:.2f}s > {shot["seconds"]}s), shorten only this shot'
        filters=[]
        for i,c in enumerate(cues):
            delay=round(c['start']*1000)
            filters.append(f'[{i}:a]adelay={delay}:all=1[a{i}]')
        filters.append(''.join(f'[a{i}]' for i in range(len(cues)))+f'amix=inputs={len(cues)}:normalize=0,apad[out]')
        run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',';'.join(filters),'-map','[out]','-t',shot['seconds'],'-c:a','aac','-b:a','160k',folder/'audio.m4a'],folder/'encode.log')
        writejson(folder/'cues.json',cues)
        for i in range(len(cues)): (folder/f'{i}.aiff').unlink()
        complete(folder,files)
    metrics.record('tts:'+shot['id'],start,hit,key=key)
    return folder/'audio.m4a',json.loads((folder/'cues.json').read_text()),key

def expose(path, key):
    PUBLIC.mkdir(parents=True,exist_ok=True)
    name=key+path.suffix
    dest=PUBLIC/name
    if not dest.exists():
        shutil.copy2(path,dest)
    elif filehash(dest)!=filehash(path):
        raise RuntimeError('Content addressed public cache was modified')
    return 'cache/'+name

def srt_time(t):
    ms=round(t*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def validate_video(path, config, cues):
    p=probe(path)
    v=next(s for s in p['streams'] if s['codec_type']=='video')
    a=next(s for s in p['streams'] if s['codec_type']=='audio')
    duration=sum(s['seconds'] for s in config['storyboard'])
    assert (v['width'],v['height'],v['codec_name'],v['avg_frame_rate'])==(config['render']['width'],config['render']['height'],'h264','30/1')
    assert a['codec_name']=='aac' and int(a['sample_rate'])>=44100
    assert abs(float(p['format']['duration'])-duration)<0.1
    assert int(v['nb_frames'])==duration*30
    for i,c in enumerate(cues):
        assert 0<=c['start']<c['end']<=duration
        if i: assert cues[i-1]['end']<=c['start']
    run(['ffmpeg','-v','error','-i',path,'-f','null','-'],path.with_suffix('.decode.log'))
    samples=array.array('f')
    samples.frombytes(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1']))
    peak=max(abs(x) for x in samples)
    rms=math.sqrt(sum(x*x for x in samples)/len(samples))
    assert 0.001<rms and 0.01<peak<0.9999, 'Silent or clipped narration track'
    utterances=[]
    for c in cues:
        segment=samples[round(c['start']*16000):round(c['end']*16000)]
        level=math.sqrt(sum(x*x for x in segment)/max(1,len(segment)))
        assert level>0.001, 'Silent subtitle interval'
        utterances.append(round(20*math.log10(level),2))
    result={'status':'TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO','sha256':filehash(path),'probe':p,
            'audio':{'peak':peak,'rms':rms,'utterance_rms_dbfs':utterances},
            'subtitle_timing':'Exact synthesized utterance intervals; not phoneme alignment',
            'unverified':['Independent full viewing/listening','Occlusion and subjective clarity','Tooth contact and forces','Voice redistribution terms and organization Remotion eligibility before publishing'],
            'automatic_repair_attempts':0,'repair_policy':'No automatic repair; stop on first failure. Any future repair must use <=2 distinct strategies, <=2 attempts each, with measured improvement.'}
    writejson(path.with_suffix('.validation.json'),result)
    return result

def composition_key(props, quality):
    if quality not in ['preview', 'final']:
        raise ValueError('Unsupported composition quality')
    return digest({'props':props,'quality':quality,
                   'remotion':codehash('remotion/src/index.tsx','remotion/package-lock.json'),
                   'composition_code':codehash('scripts/produce.py')})

def compose(cfg, quality, media, metrics):
    from narration import effective_profile
    voice=effective_profile(cfg) or cfg['voice']
    start=time.time()
    render_shots=[]
    cues=[]
    offset=0
    for s in cfg['storyboard']:
        audio,sc,_=tts(s,voice,metrics)
        path,kind,key=media[s['shot']]
        render_shots.append({k:s[k] for k in ['id','label','note','seconds','accent']}|{'formula':s.get('formula'),'media':expose(path,key),'kind':kind,'audio':expose(audio,filehash(audio))})
        subtitles=s.get('subtitles',[c['text'] for c in sc])
        assert len(subtitles)==len(sc), 'One subtitle entry per synthesized utterance'
        sc=[dict(c,text=text) for c,text in zip(sc,subtitles)]
        cues.extend(dict(c,start=round(c['start']+offset,3),end=round(c['end']+offset,3)) for c in sc)
        offset+=s['seconds']
    props={'title':cfg['title'],'subtitle':cfg['subtitle'],'shots':render_shots,'cues':cues,'duration':offset,'fps':30,'width':cfg['render']['width'],'height':cfg['render']['height']}
    if cfg.get('presentation'):
        if cfg['presentation'] != 'mechanism-fullframe':
            raise ValueError('Unsupported presentation')
        props['presentation']=cfg['presentation']
    for field in ('fullframe_caption','fullframe_credit'):
        if field in cfg:
            if not isinstance(cfg[field],str):
                raise ValueError(f'{field} must be a string')
            props[field]=cfg[field]
    key=composition_key(props, quality)
    suffix='preview' if quality=='preview' else 'final'
    target=ROOT/'output'/f'{cfg["id"]}-{suffix}.mp4'
    cachedir=CACHE/'compositions'/key
    cachedir.mkdir(parents=True,exist_ok=True)
    hit=cached(cachedir,['video.mp4'])
    if not hit:
        writejson(cachedir/'props.json',props)
        chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        args=[ROOT/'remotion/node_modules/.bin/remotion','render','src/index.tsx','Mechanical',cachedir/'video.mp4','--props',cachedir/'props.json','--codec','h264','--audio-codec','aac','--pixel-format','yuv420p','--concurrency','2','--browser-executable',chrome,'--gl','angle','--log','error']
        if quality=='preview': args+=['--scale','0.5','--crf','25']
        run(args,cachedir/'render.log',cwd=ROOT/'remotion')
        if quality=='final': validate_video(cachedir/'video.mp4',cfg,cues)
        else: run(['ffmpeg','-v','error','-i',cachedir/'video.mp4','-f','null','-'],cachedir/'decode.log')
        complete(cachedir,['video.mp4'])
    shutil.copy2(cachedir/'video.mp4',target)
    writejson(target.with_suffix('.props.json'),props)
    target.with_suffix('.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
    if quality=='final': validate_video(target,cfg,cues)
    metrics.record('composition:'+quality,start,hit,key=key,output=str(target.relative_to(ROOT)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('config',type=Path)
    ap.add_argument('--phase',choices=['asset','checks','keys','local','preview','final','all'],default='all')
    ap.add_argument('--env-file',type=Path,help='Optional local TTS credentials file; never copy credentials into video JSON')
    ap.add_argument('--task', type=Path, help='Evidence-led production task for full preview/final')
    ap.add_argument('--legacy-workprint', action='store_true', help='Explicit existing v1 task only; never quality acceptance')
    ap.add_argument('--diagnostic', action='store_true', help='One short candidate shot only; no full composition')
    args=ap.parse_args()
    if args.diagnostic and args.phase not in {'keys', 'checks', 'local'}:
        ap.error('Diagnostic mode cannot render a full video')
    if args.phase in {'preview', 'final', 'all'}:
        import sys
        sys.path.insert(0, str(ROOT))
        from mechanical_video_next.workflow import load, require_animatic, check_qa
        if args.task is None:
            ap.error('Full rendering requires --task with frozen blueprint and independent animatic QA')
        task_data = load(args.task)
        bound_config = task_data.get('config')
        if not bound_config or Path(bound_config).resolve() != args.config.resolve():
            ap.error('Render config must match production task config')
        if task_data.get('protocol_version', 1) >= 2:
            if args.legacy_workprint:
                ap.error('New tasks cannot bypass animatic via legacy mode')
            if args.phase == 'all':
                ap.error('Protocol v2 requires separate preview, independent QA, and final stages')
            allowed_states = {'preview': {'ANIMATING', 'PREVIEW_READY', 'PREVIEW_CHECKING'},
                              'final': {'EDITING', 'FINAL_CHECKING'}}
            if task_data['state'] not in allowed_states[args.phase]:
                ap.error('Task state does not authorize this full render')
            require_animatic(args.task)
            if args.phase == 'final':
                check_qa(args.task, 'preview-qa')
        elif not args.legacy_workprint:
            ap.error('Old task requires explicit --legacy-workprint; migrate new production to v2')
    from narration import load_env,effective_profile
    load_env(args.env_file or (ROOT/'.env.local' if (ROOT/'.env.local').exists() else None))
    cfg=json.loads(args.config.read_text())
    effective_profile(cfg)
    assembly_path=cfg.get('assembly_config')
    assembly=assembly_spec(assembly_path)
    assert cfg['asset']==assembly['id'], 'Video and assembly identity differ'
    assert set(cfg['components'])<=set(assembly['required_parts']), 'Unknown requested component'
    assert cfg['motion_template']==assembly['motion']['template'], 'Unverified motion template'
    if assembly.get('kind') == 'source-mesh-assembly-v1':
        assert cfg['motion_template']=='data-keyframes-v1'
        assert cfg['explosion_sequence']==[], 'Imported source disassembly is not automatically validated'
        assert all(s['template'] in {'overall','detail','motion'} for s in cfg['shots'].values())
    else:
        assert cfg['asset']=='planetary-teaching-v1'
        assert cfg['explosion_sequence']==['Housing_upper','Housing_lower','Ring','Carrier'], 'Only the validated axial sequence is supported in phase one'
    assert {k:cfg['render'][k] for k in ['width','height','fps','video','audio']} in [{'width':w,'height':h,'fps':30,'video':'h264','audio':'aac'} for w,h in [(1080,1920),(1920,1080)]]
    assert cfg['render'].get('framing','panel') in ['panel','fullframe']
    if args.diagnostic:
        selected=cfg.get('local_preview_shots',[])
        assert len(selected)==1 and selected[0] in cfg['shots']
        assert 0<cfg['shots'][selected[0]]['seconds']<=5
    else:
        assert 30<=sum(s['seconds'] for s in cfg['storyboard'])<=45
    assert len({s['id'] for s in cfg['storyboard']})==len(cfg['storyboard'])
    for s in cfg['storyboard']: assert s['seconds']==cfg['shots'][s['shot']]['seconds']
    metrics=Metrics(cfg['id']+'-'+args.phase)
    # Sample temporary use during rendering, including PNG sequences (not merely at stage end).
    stopped=threading.Event()
    def monitor():
        while not stopped.wait(0.5):
            try: metrics.peak=max(metrics.peak,budget())
            except Exception as e:
                # Main stages enforce the budget too; record the overrun and exit after current subprocess.
                metrics.budget_error=str(e)
    thread=threading.Thread(target=monitor,daemon=True)
    thread.start()
    status='passed'
    error=None
    try:
        model=asset(metrics,assembly_path)
        if args.phase=='asset': return
        names=list(dict.fromkeys(s['shot'] for s in cfg['storyboard']))
        if args.diagnostic:
            names=cfg['local_preview_shots']
        if args.phase=='checks':
            selected=cfg.get('local_preview_shots',[])
            assert selected and set(selected)<=set(names)
            for name in selected:
                make_shot(cfg['shots'][name],'checks',model,metrics,cfg['render'],assembly_path)
            return
        for name in names: make_shot(cfg['shots'][name],'keys',model,metrics,cfg['render'],assembly_path)
        if args.phase=='keys': return
        if args.phase=='local':
            selected=cfg.get('local_preview_shots',[])
            assert selected and set(selected)<=set(names), 'Explicit local preview shots required'
            for name in selected:
                make_shot(cfg['shots'][name],'preview',model,metrics,cfg['render'],assembly_path)
            return
        preview={n:make_shot(cfg['shots'][n],'preview',model,metrics,cfg['render'],assembly_path) for n in names}
        compose(cfg,'preview',preview,metrics)
        if args.phase=='preview': return
        final={n:make_shot(cfg['shots'][n],'final',model,metrics,cfg['render'],assembly_path) for n in names}
        compose(cfg,'final',final,metrics)
        if hasattr(metrics,'budget_error'): raise RuntimeError(metrics.budget_error)
    except Exception as e:
        status='failed'
        error=str(e)
        raise
    finally:
        stopped.set()
        thread.join()
        value=metrics.finish(status=status,error=error,human_interventions_observed=None,automatic_repair_attempts=0)
        writejson(ROOT/'output/runs'/f'{cfg["id"]}-{args.phase}-{int(metrics.start*1000)}.json',value)

if __name__=='__main__': main()
