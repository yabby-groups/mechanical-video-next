#!/usr/bin/env -S uv run python
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
import sys
import threading
import time
from common import ROOT, BLENDER, Metrics, budget, codehash, digest, filehash, probe, run, writejson, work_budget_limit

# Direct script execution otherwise exposes only scripts/, while diagnostic
# stages also need the project's evidence helpers without a duration import.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CACHE = ROOT/'work/cache'
PUBLIC = ROOT/'remotion/public/cache'
# Freeze the unchanged legacy say/FFmpeg audio recipe identity. Text-only edits
# must retain existing audio keys; bump this only when that recipe changes.
LEGACY_AUDIO_PROCESSING = '499692624f28ded76480fdd5a7519bfd2d2095d73d9fccd50fae3ec1295fbade'

def cached(folder, files):
    marker = folder/'complete.json'
    if not marker.exists():
        return False
    try:
        m = json.loads(marker.read_text())
        valid = set(files)<=set(m) and all((folder/f).is_file() and filehash(folder/f)==h for f,h in m.items())
        if valid and (folder/'checks.json').is_file():
            checks = json.loads((folder/'checks.json').read_text())
            scene_ref = checks.get('scene_artifact')
            if scene_ref:
                scene_path = Path(scene_ref['path'])
                valid = scene_path.is_file() and filehash(scene_path) == scene_ref['sha256']
            source_ref = checks.get('source_shot')
            if source_ref:
                source_path = Path(source_ref['path'])
                valid = valid and source_path.is_file() and filehash(source_path) == source_ref['sha256']
        if valid:
            (folder/'.last-used').touch()
        return valid
    except (KeyError, ValueError, OSError):
        return False

def complete(folder, files):
    writejson(folder/'complete.json',{f:filehash(folder/f) for f in files})

def assembly_spec(path=None):
    return json.loads((ROOT / (path or 'config/assembly.json')).read_text())

def asset_key(assembly_path=None, *, source_exact=False):
    cfg = assembly_spec(assembly_path)
    from mechanical_video_next.science_shots import validate_asset
    validate_asset(cfg)
    sources = {s['path']:filehash(ROOT/s['path']) for s in cfg.get('source_files', [])}
    for s in cfg.get('source_files', []):
        if sources[s['path']] != s['sha256']:
            raise ValueError('Assembly source hash mismatch: '+s['path'])
    renderer = (codehash('blender/scene.py','blender/vendor',equivalents=False) if source_exact or cfg.get('reuse')
                else codehash('blender/scene.py','blender/vendor'))
    return digest({'config':cfg,'source':renderer,
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
    return ((width//2, height//2, 30 if render.get('full_rate_preview') else 15)
            if quality!='final' and not render.get('preview_native', False)
            else (width,height,30))

def bounded_chunk_frames(requested, needed, width, height, used_bytes):
    """Shrink the batch, never the image, when retained caches fill work space."""
    per_frame = width * height * 3 * 1.12
    # Keep space for encoded chunks, concatenation and metadata as well as PNGs.
    reserve = max(8 * 1024**2, needed * width * height * 3 // 4)
    available = min(work_budget_limit() - used_bytes - 8 * 1024**2, shutil.disk_usage(ROOT).free - 3 * 1024**3 - reserve)
    capacity = math.floor(available / per_frame)
    if capacity < 1:
        raise RuntimeError('Insufficient work budget for one frame and encoding reserve')
    return min(requested, needed, capacity)

def shot_key(shot, quality, render=None, assembly_path=None, *, model=None):
    render = render or {'width':1080,'height':1920}
    # Native previews and final shots use identical Blender/encoding arguments.
    # Reuse their verified render rather than render the same frames twice.
    if quality == 'final' and panel_spec(render,'preview') == panel_spec(render,'final'):
        quality = 'preview'
    if shot.get('template') == 'layered':
        from layered import sources
        return digest({'sources':sources(shot), 'shot':shot, 'panel':panel_spec(render,quality),
                       'quality':quality, 'renderer':codehash('scripts/layered.py')})
    assembly_key=asset_key(assembly_path,source_exact=True) if shot.get('science') else asset_key(assembly_path)
    inputs={'asset':assembly_key,'shot':{k:v for k,v in shot.items() if k != 'visual'},'quality':quality,'panel':panel_spec(render,quality)}
    if model is not None:
        # The verified canonical builder already binds the source assembly.
        canonical = CACHE/'assets'/(asset_key(assembly_path) if shot.get('science') else assembly_key)
        if (Path(model).resolve() != (canonical/'assembly.blend').resolve()
                or not cached(canonical, ['assembly.blend', 'assembly.inventory.json'])):
            inputs['external_model_sha256'] = filehash(model)
    inputs['provenance_renderer'] = codehash('blender/render_with_provenance.py')
    if shot.get('visual_profile'):
        inputs['visual_style_source']=codehash('blender/studio_style.py')
    if shot.get('science'):
        science_files = ['blender/scene.py', 'blender/science_scene.py', 'mechanical_video_next/science_shots.py']
        if {'camera_path', 'stage_rotation', 'guides', 'print_marks', 'constraints'} & shot['science'].keys():
            science_files.append('blender/science_guides.py')
        inputs['science_renderer'] = codehash(*science_files, equivalents=False)
    return digest(inputs)

def prepare_shot_evidence(folder):
    from mechanical_video_next.qa_images import prepare_image, visual_packet
    frames = sorted(folder.glob('key-*.png')) or sorted((folder/'frames').glob('*.png'))
    if frames:
        indices = sorted({round(i*(len(frames)-1)/3) for i in range(4)})
        writejson(folder/'qa-images.json', visual_packet([prepare_image(frames[i]) for i in indices]))


def shot_input_file(folder, key, shot):
    """Retain exact render inputs beside opt-in archived scenes, outside work."""
    archive = shot.get('scene_artifact_dir')
    target = Path(archive)/(key+'.shot.json') if archive else folder/'shot.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(shot, ensure_ascii=False, separators=(',', ':'), sort_keys=True)+'\n'
    if archive and target.exists():
        if target.read_text() != text:
            raise ValueError('Archived shot input changed; preserve it for diagnosis')
    else:
        target.write_text(text)
    return target


def make_shot(shot, quality, model, metrics, render=None, assembly_path=None):
    shot = {k: v for k, v in shot.items() if k != 'visual'}
    from mechanical_video_next.three_d import validate_config
    from mechanical_video_next.science_shots import validate_assembly_shot
    validate_config({'shots': {'shot': shot}})
    if shot.get('science'):
        validate_assembly_shot(shot, assembly_spec(assembly_path))
    start=time.time()
    render = render or {'width':1080,'height':1920}
    width,height,fps = panel_spec(render,quality)
    if quality=='checks':
        fps=shot.get('diagnostic_fps',fps)
    key=shot_key(shot,quality,render,assembly_path,model=model)
    folder=CACHE/'shots'/key
    if shot.get('template') == 'layered':
        from layered import render as render_layers
        files = ['checks.json'] + ([f'key-{i}.png' for i in range(3)] if quality in {'keys','checks'} else ['media.mp4'])
        hit = cached(folder, files)
        if not hit:
            render_layers(shot, folder, width, height, fps, quality)
            complete(folder, files)
        metrics.record(quality+':layered', start, hit, key=key)
        prepare_shot_evidence(folder)
        return folder/'media.mp4', 'video', key
    kind='image' if shot['template'] in ['overall','detail','exploded'] and not shot.get('science') else 'video'
    filename='media.png' if kind=='image' else 'media.mp4'
    files=['checks.json'] + ([] if shot.get('scene_artifact_dir') else ['frames/scene.blend'])
    if quality not in {'keys','checks'}:
        files.insert(0, filename)
    hit=cached(folder,files)
    if hit and shot.get('scene_artifact_dir'):
        hit = bool(json.loads((folder/'checks.json').read_text()).get('scene_artifact'))
    if not hit:
        folder.mkdir(parents=True,exist_ok=True)
        shot_path = shot_input_file(folder, key, shot)
        frames=folder/'frames'
        args=[BLENDER,'-b','--factory-startup','--python-exit-code','1','--python',ROOT/'blender/render_with_provenance.py','--','shot','--asset',model,'--shot',shot_path,'--out',frames,'--width',width,'--height',height,'--fps',fps]
        args += ['--assembly-config',ROOT/(assembly_path or 'config/assembly.json')]
        if quality=='keys': args+=['--keys']
        if quality=='checks': args+=['--checks-only']
        # Resume encoding without rerendering an already complete local frame sequence.
        expected = len(list((frames).glob('*.png')))
        needed = 1 if kind=='image' else round(shot['seconds']*fps)
        ready = quality not in {'keys','checks'} and (frames/'checks.json').exists() and expected==needed
        chunk_frames = int(render.get('chunk_frames', 16)) if kind=='video' and quality not in {'keys','checks'} else 0
        chunked = bool(chunk_frames and not ready)
        if chunked:
            assert chunk_frames > 0
            chunk_frames = bounded_chunk_frames(chunk_frames, needed, width, height, budget())
            args += ['--chunk-frames', chunk_frames, '--video-output', folder/filename]
        if not ready:
            # Conservative upper bound for an uncompressed RGB frame sequence plus PNG overhead.
            projected_frames = (0 if quality=='checks' else min(needed, 3) if quality=='keys'
                                else min(needed, chunk_frames) if chunked else needed)
            projected = budget() + width*height*3*projected_frames*1.12
            if projected > work_budget_limit():
                raise RuntimeError('Projected temporary frame sequence exceeds work budget')
            run(args,folder/'blender.log')
        shutil.copy2(frames/'checks.json',folder/'checks.json')
        if shot.get('scene_artifact_dir'):
            scene_ref = json.loads((folder/'checks.json').read_text())['scene_artifact']
            scene_path = Path(scene_ref['path']).resolve()
            assert scene_path.is_relative_to(Path(shot['scene_artifact_dir']).resolve())
            assert scene_path.is_file() and filehash(scene_path) == scene_ref['sha256']
        if quality not in {'keys','checks'}:
            if kind=='image': shutil.copy2(next(frames.glob('*.png')),folder/filename)
            else:
                if chunked:
                    chunk_report=json.loads((frames/'chunk-result.json').read_text())
                    assert chunk_report['status']=='PASS' and chunk_report['final_decode']=='PASS', chunk_report
                    writejson(folder/'chunk-result.json',chunk_report)
                    metrics.cleanup_rows = getattr(metrics, 'cleanup_rows', []) + [chunk_report]
                    files.append('chunk-result.json')
                else:
                    run(['ffmpeg','-v','error','-y','-framerate',fps,'-i',frames/'%05d.png','-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',folder/filename],folder/'encode.log')
                    run(['ffmpeg','-v','error','-i',folder/filename,'-f','null','-'],folder/'decode.log')
                v=probe(folder/filename)['streams'][0]
                assert int(v['width'])==width and abs(float(v['duration'])-shot['seconds'])<0.1
            # Exact owned files only. Keyframes and originals are never removed here.
            if not chunked:
                for p in frames.glob('*.png'): p.unlink()
        elif quality=='keys':
            files += [str(p.relative_to(folder)) for p in sorted(frames.glob('*.png'))]
        complete(folder,files)
    metrics.record(quality+':'+shot['template'],start,hit,key=key)
    prepare_shot_evidence(folder)
    return folder/filename,kind,key

def tts(shot, voice, metrics):
    start=time.time()
    if isinstance(voice,dict):
        from narration import synthesize_shot
        path,cues,key,hit=synthesize_shot(shot,voice)
        metrics.record('tts:'+shot['id'],start,hit,key=key,model=voice['model'],voice=voice['voice'])
        return path,cues,key
    key=digest({'cues':shot['narration'],'voice':voice,'seconds':shot['seconds'],'rate':235,'audio_pipeline':1,
                'processing':LEGACY_AUDIO_PROCESSING})
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
    expected_frames=sum(round(s['seconds']*30) for s in config['storyboard'])
    duration=expected_frames/30
    assert (v['width'],v['height'],v['codec_name'],v['avg_frame_rate'])==(config['render']['width'],config['render']['height'],'h264','30/1')
    assert a['codec_name']=='aac' and int(a['sample_rate'])>=44100
    assert abs(float(p['format']['duration'])-duration)<0.1
    assert int(v['nb_frames'])==expected_frames
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
    from mechanical_video_next.production_contract import enabled as science_contract
    if science_contract(config):
        result.update(status='TECHNICAL_PASS_UNACCEPTED_WORKPRINT',
                      production_contract_version=config['production_contract_version'],
                      production_contract=config['production_contract'],
                      repair_policy='Validator stops on failure; the existing Producer diagnoses and repairs until pass or an evidenced external boundary. Preserve defect history and change unsuccessful strategies; no fixed round limit.',
                      repair_counter_scope='This deterministic validation call only; not whole-workflow attempts')
        result['unverified'][2] = 'Scientific assumptions, contact and force behavior beyond the bound teaching model'
    writejson(path.with_suffix('.validation.json'),result)
    return result

def composition_key(props, quality):
    from mechanical_video_next.remotion_build import sources_for
    if quality not in ['preview', 'final']:
        raise ValueError('Unsupported composition quality')
    sources = sources_for(props if isinstance(props, dict) else {})
    return digest({'props':props,'quality':quality,
                   'remotion':codehash(*sources),
                   'composition_code':codehash('scripts/produce.py', 'mechanical_video_next/text_layout.py', 'mechanical_video_next/science_information.py', 'mechanical_video_next/remotion_build.py', 'config/text-style.json')})

def composition_cached_media(folder):
    if cached(folder, ['video.mp4']):
        return folder/'video.mp4'
    try:
        receipt = json.loads((folder/'external-media.json').read_text())
        output, props = Path(receipt['media']['path']), folder/'props.json'
        if (receipt.get('schema_version') == 1 and receipt.get('decode') == 'PASS'
                and output.is_file() and not output.is_symlink()
                and output.resolve().is_relative_to((ROOT/'output').resolve())
                and receipt['props']['path'] == str(props.resolve())
                and filehash(props) == receipt['props']['sha256']
                and filehash(output) == receipt['media']['sha256']):
            (folder/'.last-used').touch()
            return output
    except (OSError, KeyError, ValueError, TypeError):
        pass
    return None


def compose(cfg, quality, media, metrics):
    from narration import effective_profile
    from mechanical_video_next.science_information import information_props, observation_overlay_findings
    from mechanical_video_next.remotion_build import render
    from mechanical_video_next.knowledge_progression import FIELD, enabled
    from mechanical_video_next.visual_narrative import VERSION, version
    from mechanical_video_next import joint_timeline as joint
    from mechanical_video_next.production_contract import (
        NATURAL_SCIENCE, PRESENTATION_STYLE, audience_caption, validate_audience_copy,
    )
    natural = cfg.get(PRESENTATION_STYLE, NATURAL_SCIENCE) == NATURAL_SCIENCE
    if cfg.get(PRESENTATION_STYLE) == NATURAL_SCIENCE:
        validate_audience_copy(cfg)
        for row in cfg['storyboard']:
            validate_audience_copy(row)
            validate_audience_copy(cfg['shots'][row['shot']])
    visual = version(cfg) == VERSION
    shared = joint.enabled(cfg)
    locked = shared and joint.integrity(cfg['timeline'])
    if shared:
        plan = joint.validate(cfg['timeline'])
        measured = joint.receipt(plan, cfg['measured_timeline'])
        picture = {s['id']: s for s in plan['shots']}
        master = joint.bound(measured['narration_audio'])
        voice = None
    else:
        voice=effective_profile(cfg) or cfg['voice']
    start=time.time()
    render_shots=[]
    audio_sources=[]
    cues=[]
    offset=0
    for s in cfg['storyboard']:
        spec = cfg['shots'][s['shot']]
        path,kind,key=media.get(s['shot'], (None,'graphic',None))
        row = {k:s[k] for k in ['id','label','note','seconds','accent']} | {
            'formula':s.get('formula'), 'kind':kind}
        if not shared:
            audio,sc,_=tts(s,voice,metrics)
            audio_sha = filehash(audio)
            audio_sources.append(audio_sha)
            row['audio'] = expose(audio,audio_sha)
        if path is not None:
            row['media'] = expose(path,key)
        if shared:
            cut = picture[s['id']]
            count = cut['end_frame'] - cut['start_frame']
            if s['seconds'] != count / 30 or cut['start_frame'] != round(offset * 30):
                raise ValueError('Compiled storyboard drifted from the joint picture track')
            if kind == 'video':
                trim = cut.get('source_start_frame', 0)
                if spec.get('footage') and trim != spec['footage']['start_frame']:
                    raise ValueError('Joint picture offset differs from licensed footage interval')
                joint.validate_source_clip(path, trim, count)
                if locked and cut.get('action_views') and not spec.get('footage'):
                    source = next(row for row in probe(path)['streams'] if row['codec_type'] == 'video')
                    if source['avg_frame_rate'] != '30/1' or source['r_frame_rate'] != '30/1':
                        raise ValueError('Mechanical event needs native 30 fps source frames: ' + s['id'])
                row['mediaStartFrame'] = trim
            elif kind == 'image' or cut.get('source_start_frame'):
                raise ValueError('Joint dynamic storyboard needs moving media or an original graphic')
        if spec.get('science') or s.get('information'):
            row.update(information_props(spec, s, path, kind, natural=natural))
        if visual:
            from mechanical_video_next.visual_narrative import editorial_props, validate_footage
            row.update(editorial_props(spec))
            if 'split_screen' in spec:
                from mechanical_video_next.remotion_build import validate_phone_text
                sources = spec['split_screen']['sources']
                if len(sources) != 2 or spec.get('footage') != sources[0]:
                    raise ValueError('Split screen requires the primary footage and one supplemental source')
                entries = []
                for source in sources:
                    source_path = validate_footage(source, seconds=spec['seconds'])
                    validate_phone_text(source['credit'], 896)
                    entries.append({'media': expose(source_path, filehash(source_path)),
                                    'startFrame': source['start_frame'], 'credit': source['credit']})
                row['splitScreen'] = {'sources': entries}
        render_shots.append(row)
        if not shared:
            subtitles=s.get('subtitles',[c['text'] for c in sc])
            assert len(subtitles)==len(sc), 'One subtitle entry per synthesized utterance'
            sc=[dict(c,text=text) for c,text in zip(sc,subtitles)]
            cues.extend(dict(c,start=round(c['start']+offset,3),end=round(c['end']+offset,3)) for c in sc)
        offset+=s['seconds']
    if shared:
        if len(render_shots) != len(picture) or round(offset * 30) != plan['frame_count']:
            raise ValueError('Compiled storyboard must cover the complete joint timeline')
        cues = joint.cues(measured)
        offset = plan['frame_count'] / 30
        audio_sources = [measured['narration_audio']['sha256']]
    props={'title':cfg['title'],'subtitle':cfg['subtitle'],'shots':render_shots,'cues':cues,'duration':offset,'fps':30,'width':cfg['render']['width'],'height':cfg['render']['height']}
    if shared:
        props[joint.FIELD] = joint.VERSION
        playback = master
        if 'audio_mix' in cfg:
            from mechanical_video_next.audio_acceptance import verify_mix
            playback, _ = verify_mix(cfg['audio_mix'], master, plan['frame_count'] * joint.SAMPLES_PER_FRAME,
                                     check_masking=False)
        props['narrationTrack'] = expose(playback, filehash(playback))
    if locked:
        props['frameCount'] = plan['frame_count']
    props[PRESENTATION_STYLE] = NATURAL_SCIENCE if natural else 'legacy'
    if visual:
        props['visual_policy_version'] = VERSION
    from mechanical_video_next.media_policy import FIELD as MEDIA_FIELD, enabled as asset_first
    if asset_first(cfg):
        props[MEDIA_FIELD] = cfg[MEDIA_FIELD]
    if enabled(cfg):
        props[FIELD] = cfg[FIELD]
    for field in ('production_contract_version','production_contract','subject_kind'):
        if field in cfg:
            props[field]=cfg[field]
    if cfg.get('presentation'):
        if cfg['presentation'] != 'mechanism-fullframe':
            raise ValueError('Unsupported presentation')
        props['presentation']=cfg['presentation']
    for field in ('fullframe_caption','fullframe_credit'):
        if field in cfg:
            if not isinstance(cfg[field],str):
                raise ValueError(f'{field} must be a string')
            value = cfg[field]
            if natural and field == 'fullframe_caption':
                value = audience_caption(value)
            if value or not natural:
                props[field] = value
    from mechanical_video_next.text_layout import prepare_text_props
    from mechanical_video_next.style_lock import verify_lock
    lock = verify_lock(ROOT / 'assets/style-reference/style-lock.json', shared_only=True)
    if lock['status'] != 'PASS':
        workprint = cfg.get('production_scope') in {'pipeline-test', 'source-supported-film', 'mechanism-preview', 'verified-shots'}
        visual_studio = visual and all(
            shot.get('visual_profile') == 'printer-ep03-studio-v1'
            for shot in cfg['shots'].values() if shot['template'] != 'editorial'
        )
        # A historical source-code lock is not a ban on inspecting a new scene.
        # Never replace its hashes or call this a style/visual acceptance pass.
        immutable_refs_ok = all(row['status']=='PASS' for row in lock['files']
                                if row['path'] not in {'blender/scene.py','blender/studio_style.py'})
        if not (workprint or visual_studio) or not immutable_refs_ok:
            raise ValueError('Protected visual reference changed or unavailable; inspect style lock')
    props['annotations'] = cfg.get('text_annotations', [])
    props['critical_boxes'] = cfg.get('text_critical_boxes', [])
    props['platform_insets'] = cfg.get('platform_insets')
    props['subtitle_alignment'] = cfg.get('subtitle_alignment')
    props = prepare_text_props(props, audio_sha256=digest(audio_sources))
    encode_profile = cfg['render'].get('encode_profile') if quality == 'final' else None
    if encode_profile is not None:
        props['encode_profile'] = encode_profile
    cues = props['cues']
    key=composition_key(props, quality)
    suffix='preview' if quality=='preview' else 'final'
    target=ROOT/'output'/f'{cfg["id"]}-{suffix}.mp4'
    cachedir=CACHE/'compositions'/key
    cachedir.mkdir(parents=True,exist_ok=True)
    from mechanical_video_next.production_contract import enabled as science_contract
    external = science_contract(cfg)
    cached_media = composition_cached_media(cachedir)
    hit = cached_media is not None
    if not hit:
        writejson(cachedir/'props.json',props)
        cached_media = target if external else cachedir/'video.mp4'
        candidate = cached_media.with_suffix('.unverified.mp4') if locked else cached_media
        render(cachedir/'props.json', candidate, cachedir/'render.log',
               preview=quality=='preview', encode_profile=encode_profile, visual=visual, progression=enabled(cfg))
        if locked:
            joint.validate_rendered_film(candidate, plan)
            joint.validate_rendered_audio(candidate, plan, measured, playback, mix='audio_mix' in cfg)
            candidate.replace(cached_media)
        if quality=='final': validate_video(cached_media,cfg,cues)
        else: run(['ffmpeg','-v','error','-i',cached_media,'-f','null','-'],cachedir/'decode.log')
        if not external:
            complete(cachedir,['video.mp4'])
    if locked and hit:
        joint.validate_rendered_film(cached_media, plan)
        joint.validate_rendered_audio(cached_media, plan, measured, playback, mix='audio_mix' in cfg)
    if cached_media.resolve() != target.resolve():
        shutil.copy2(cached_media,target)
    if external:
        from clean import retain_composition_export
        retain_composition_export(cachedir, target,
                                  remove_duplicate=cached_media == cachedir/'video.mp4')
    writejson(target.with_suffix('.props.json'),props)
    if locked:
        from mechanical_video_next import video_review
        bindings = {}
        for shot in cfg['storyboard']:
            cut = picture[shot['id']]
            if not cut.get('action_views'):
                continue
            path, kind, _ = media[shot['shot']]
            if kind != 'video':
                raise ValueError('A mechanical event requires actual source video')
            entry = {'video': joint.binding(path)}
            checks = path.parent / 'checks.json'
            if checks.is_file() and not cfg['shots'][shot['shot']].get('footage'):
                entry['blender_checks'] = joint.binding(checks)
            bindings[shot['id']] = entry
        video_review.write_report(target.with_suffix('.review-sources.json'), {
            'media': joint.binding(target),
            'props': joint.binding(target.with_suffix('.props.json')),
            'shots': bindings,
        })
    observation_windows = {row['id']: window for row in cfg['storyboard']
                           if (window := cfg['shots'][row['shot']].get('science', {}).get('observation_window'))}
    if observation_windows:
        writejson(target.with_suffix('.observation-overlays.json'), {
            'media_sha256': filehash(target),
            'scope': 'Projected datum inside an active overlay rectangle; pixel occlusion requires review',
            'findings': observation_overlay_findings(props, observation_windows)})
    target.with_suffix('.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
    if quality=='final':
        validation=validate_video(target,cfg,cues)
        validation['source_style_lock']=lock
        writejson(target.with_suffix('.validation.json'),validation)
        if any(shot.get('science') for shot in cfg['shots'].values()) or asset_first(cfg):
            from mechanical_video_next.provenance import write_remotion_proof
            assembly = cfg.get('assembly_config')
            proof = target.with_suffix('.hybrid-build.json' if asset_first(cfg) else '.3d-provenance.json')
            matched_models = [s['visual']['selected_asset'] for s in cfg['shots'].values()
                              if asset_first(cfg) and s['visual']['reuse_decision'] == 'REUSE_MODEL']
            from mechanical_video_next.media_policy import bound as media_bound
            proof_model = (media_bound(matched_models[0]) if matched_models and Path(matched_models[0]['path']).suffix == '.blend'
                           else CACHE/'assets'/asset_key(assembly)/'assembly.blend' if assembly else None)
            write_remotion_proof(proof, target, target.with_suffix('.props.json'),
                                 cfg, media, ROOT/assembly if assembly else None,
                                 proof_model)
            if asset_first(cfg):
                from mechanical_video_next.media_policy import write_manifest
                write_manifest(target.with_suffix('.media-provenance.json'), target, cfg, proof)
    metrics.record('composition:'+quality,start,hit,key=key,output=str(target.relative_to(ROOT)))

def validate_stage_duration(cfg, phase):
    if phase == 'asset':
        return
    if cfg.get('production_scope') == 'verified-shots':
        if phase not in {'keys', 'checks', 'local'}:
            raise ValueError('Partial shots are not a complete film')
        assert all(0 < s['seconds'] <= 15 for s in cfg['shots'].values())
        return
    if phase in {'keys', 'checks', 'local'} and cfg.get('production_scope') == 'mechanism-preview':
        selected = cfg.get('local_preview_shots', [])
        assert selected and all(name in cfg['shots'] for name in selected)
        assert 10 <= sum(cfg['shots'][name]['seconds'] for name in selected) <= 15
        assert all(shot.get('template') == 'motion' for shot in cfg['shots'].values())
        return
    duration = sum(s['seconds'] for s in cfg['storyboard'])
    if cfg.get('content_policy_version') == 1:
        from mechanical_video_next.growth import duration_bounds
        minimum, maximum = duration_bounds(cfg)
    else:
        minimum, maximum = 30, 45
    assert minimum <= duration <= maximum, 'Storyboard duration outside its content policy'


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
        from mechanical_video_next.workflow import load, require_animatic, check_qa, require_source_supported_render, active_media_repair
        if args.task is None:
            ap.error('Full rendering requires --task with frozen blueprint and independent animatic QA')
        task_data = load(args.task)
        technical_render = require_source_supported_render(args.task, args.config)
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
            repair_final = args.phase == 'final' and active_media_repair(task_data, final=True)
            if not (technical_render or repair_final) and task_data['state'] not in allowed_states[args.phase]:
                ap.error('Task state does not authorize this full render')
            require_animatic(args.task)
            if args.phase == 'final' and not technical_render:
                check_qa(args.task, 'preview-qa', acceptance=False)
        elif not args.legacy_workprint:
            ap.error('Old task requires explicit --legacy-workprint; migrate new production to v2')
    from narration import load_env,effective_profile
    load_env(args.env_file or (ROOT/'.env.local' if (ROOT/'.env.local').exists() else None))
    cfg=json.loads(args.config.read_text())
    if args.task is not None:
        from mechanical_video_next.workflow import load
        from mechanical_video_next.production_contract import PRESENTATION_STYLE
        task_style = load(args.task).get(PRESENTATION_STYLE)
        if task_style is not None:
            cfg[PRESENTATION_STYLE] = task_style
    if cfg.get('production_scope') == 'verified-shots':
        from mechanical_video_next.workflow import require_source_supported_render
        if args.task is None or args.phase not in {'keys', 'checks', 'local'}:
            ap.error('Verified shots require a task and a scoped local stage')
        require_source_supported_render(args.task, args.config)
    from mechanical_video_next.three_d import validate_config
    from mechanical_video_next.visual_narrative import validate_footage
    validate_config(cfg)
    from mechanical_video_next.media_policy import enabled as asset_first
    needs_geometry = not asset_first(cfg) or any(s['visual']['render_engine'] == 'blender' for s in cfg['shots'].values())
    effective_profile(cfg)
    assembly_path=cfg.get('assembly_config')
    illustrated = cfg.get('render_route', '3d') in {'2d', '2.5d'}
    if illustrated:
        from layered import sources
        for shot in cfg['shots'].values():
            assert shot['template']=='layered' and shot['render_route']==cfg['render_route']
            sources(shot)
    elif needs_geometry:
        assembly=assembly_spec(assembly_path)
        assert cfg['asset']==assembly['id'], 'Video and assembly identity differ'
        assert set(cfg['components'])<=set(assembly['required_parts']), 'Unknown requested component'
        assert cfg['motion_template']==assembly['motion']['template'], 'Unverified motion template'
        if assembly.get('kind') == 'source-mesh-assembly-v1':
            assert cfg['motion_template']=='data-keyframes-v1'
            assert cfg['explosion_sequence']==[], 'Imported source disassembly is not automatically validated'
            assert all(s.get('science') or s['template'] in {'overall','detail','motion','editorial'} for s in cfg['shots'].values())
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
        validate_stage_duration(cfg, args.phase)
    assert len({s['id'] for s in cfg['storyboard']})==len(cfg['storyboard'])
    from mechanical_video_next import joint_timeline as joint
    if not joint.enabled(cfg):
        for s in cfg['storyboard']:
            assert s['seconds'] == cfg['shots'][s['shot']]['seconds']
    elif joint.integrity(cfg['timeline']):
        cfg['render']['full_rate_preview'] = True
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
        models = [s['visual']['selected_asset'] for s in cfg['shots'].values()
                  if asset_first(cfg) and s['visual']['reuse_decision'] == 'REUSE_MODEL']
        if models and all(Path(m['path']).suffix == '.blend' for m in models):
            from mechanical_video_next.media_policy import bound as media_bound
            if len({m['sha256'] for m in models}) != 1:
                raise ValueError('This assembly execution requires one matched native model')
            model = media_bound(models[0])
        else:
            model=None if illustrated or not needs_geometry else asset(metrics,assembly_path)
        if args.phase=='asset': return
        names=list(dict.fromkeys(s['shot'] for s in cfg['storyboard']))
        if args.diagnostic:
            names=cfg['local_preview_shots']
        elif args.phase == 'local':
            selected = cfg.get('local_preview_shots', [])
            assert selected and set(selected) <= set(names), 'Explicit local preview shots required'
            names = selected
        editorial = [name for name in names if cfg['shots'][name]['template'] == 'editorial']
        names = [name for name in names if name not in editorial]
        supplements = {}
        from mechanical_video_next.media_policy import enabled as asset_first, bound as media_bound
        if asset_first(cfg):
            reused = [n for n in names if cfg['shots'][n]['visual']['reuse_decision'] == 'REUSE']
            for name in reused:
                spec = cfg['shots'][name]
                visual = spec['visual']
                path = media_bound(visual['selected_asset'])
                if visual['source_time_range'] != [0, spec['seconds']] or not (path.parent/'checks.json').is_file():
                    raise ValueError('Native 3D reuse needs a complete original clip with scene/checks provenance')
                supplements[name] = (path, 'video', visual['selected_asset']['sha256'])
            names = [n for n in names if n not in reused]
        for name in editorial:
            shot = cfg['shots'][name]
            if 'footage' in shot:
                path = validate_footage(shot['footage'], seconds=shot['seconds'])
                supplements[name] = (path, 'video', shot['footage']['sha256'])
        if args.phase=='checks':
            selected=cfg.get('local_preview_shots',[])
            assert selected and set(selected)<=set(names)
            for name in selected:
                make_shot(cfg['shots'][name],'checks',model,metrics,cfg['render'],assembly_path)
            return
        for name in names: make_shot(cfg['shots'][name],'keys',model,metrics,cfg['render'],assembly_path)
        if args.phase=='keys': return
        if args.phase=='local':
            if editorial and cfg.get('production_scope') not in {'verified-shots', 'mechanism-preview'}:
                clips = {n: make_shot(cfg['shots'][n], 'preview', model, metrics, cfg['render'], assembly_path) for n in names}
                compose(cfg, 'preview', clips | supplements, metrics)
                return
            selected=cfg.get('local_preview_shots',[])
            assert selected and set(selected)<=set(names), 'Explicit local preview shots required'
            clips=[]
            for name in selected:
                clips.append(make_shot(cfg['shots'][name],'preview',model,metrics,cfg['render'],assembly_path)[0])
            if cfg.get('production_scope') == 'verified-shots':
                folder = ROOT/'output'/cfg['id']
                folder.mkdir(parents=True, exist_ok=True)
                media = {}
                for name, clip in zip(selected, clips):
                    target = folder/(name+'.mp4')
                    shutil.copy2(clip, target)
                    checks = json.loads((clip.parent/'checks.json').read_text())
                    media[name] = dict(media=dict(path=str(target), sha256=filehash(target)),
                        scene=checks['scene_artifact'], checks=dict(path=str(clip.parent/'checks.json'),
                        sha256=filehash(clip.parent/'checks.json')))
                writejson(folder/'verified-shots.json', dict(config_sha256=filehash(args.config),
                    shots=media, formal_acceptance=False))
            if cfg.get('production_scope') == 'mechanism-preview':
                folder=ROOT/'output'/cfg['id']
                folder.mkdir(parents=True,exist_ok=True)
                listing=folder/'preview-segments.txt'
                if any("'" in str(p) or '\n' in str(p) for p in clips):
                    raise ValueError('Unsupported preview segment path')
                listing.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in clips))
                target=folder/'candidate-preview.mp4'
                run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',listing,
                     '-c','copy','-movflags','+faststart',target],folder/'concat.log')
                run(['ffmpeg','-v','error','-i',target,'-f','null','-'],folder/'decode.log')
                writejson(folder/'candidate-preview.json',dict(media={'path':str(target),'sha256':filehash(target)},
                    config={'path':str(args.config.resolve()),'sha256':filehash(args.config)},
                    segments=[{'path':str(p),'sha256':filehash(p)} for p in clips],
                    formal_acceptance=False,visual_review='UNKNOWN',audio_review='UNKNOWN'))
            return
        if args.phase != 'final':
            preview={n:make_shot(cfg['shots'][n],'preview',model,metrics,cfg['render'],assembly_path) for n in names}
            compose(cfg,'preview',preview | supplements,metrics)
            if args.phase=='preview': return
        final={n:make_shot(cfg['shots'][n],'final',model,metrics,cfg['render'],assembly_path) for n in names}
        compose(cfg,'final',final | supplements,metrics)
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
