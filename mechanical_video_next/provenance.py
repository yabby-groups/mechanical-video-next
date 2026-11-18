"""Executable scene/render/build proof, separate from mechanical and perceptual QA.

Validation opens every scene in Blender, rejects planar mechanical substitutes,
rerenders sampled frames and compares them with the recorded raw render. It then
replays the restricted full-film composition and compares *all* decoded frames.
No arbitrary shell command from a provenance document is ever executed.
"""
import argparse
import json
from pathlib import Path
import math
import re
import subprocess
import tempfile
import shutil

from scripts.common import ROOT, BLENDER, filehash, probe, digest, writejson


def verification_key(doc, stage, replay):
    """Rehash every bound dependency, including inputs nested in receipts."""
    def visit(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                bound(value)
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(doc)
    return digest(dict(document=doc, stage=stage, replay=replay,
        verifier=filehash(__file__), audit=filehash(ROOT/'blender/provenance_audit.py'),
        remotion_build=filehash(ROOT/'mechanical_video_next/remotion_build.py') if doc.get('build', {}).get('renderer') == 'remotion-v1' else None,
        blender=subprocess.check_output([BLENDER, '--version'], text=True),
        ffmpeg=subprocess.check_output(['ffmpeg', '-version'], text=True)))


def binding(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':filehash(path)}


def bound(value):
    p=Path(value.get('path',''))
    if not p.is_file() or filehash(p)!=value.get('sha256'):
        raise ValueError('Missing/stale 3D provenance source: '+str(p))
    return p


def verify_remotion_inputs(build):
    from .remotion_build import sources_for
    from .visual_narrative import VERSION, editorial_props, match_policy, validate_footage, version
    props_file = bound(build['props'])
    props = json.loads(props_file.read_text())
    sources = {bound(row).resolve() for row in build['render_sources']}
    visual = version(build) == VERSION
    match_policy(build, props)
    if sources != {(ROOT/name).resolve() for name in sources_for(build)}:
        raise ValueError('Unexpected or incomplete Remotion renderer sources')
    if (props.get('presentation') != 'mechanism-fullframe'
            or [props.get(key) for key in ('width', 'height', 'fps')] != [1920, 1080, 30]):
        raise ValueError('Remotion proof requires native fullframe 3D composition')
    if len(props['shots']) != len(build['segments']):
        raise ValueError('Remotion timeline must match verified 3D segments')
    if visual:
        from .three_d import validate_config
        config = build['visual_config']
        match_policy(build, config)
        validate_config(config)
    cursor = 0
    for index, (row, segment) in enumerate(zip(props['shots'], build['segments'])):
        role = segment.get('media_kind', 'mechanical-3d')
        if role != 'licensed-footage' and ('splitScreen' in row or segment.get('supplemental_sources')):
            raise ValueError('Split screen requires licensed footage')
        if (row['id'] != segment['chapter_id'] or row['kind'] != ('graphic' if role == 'information' else 'video')
                or round(row['seconds'] * 30) != segment['frame_count']):
            raise ValueError('Remotion chapter is not the verified 3D segment')
        if visual:
            chapter = config['storyboard'][index]
            spec = config['shots'][chapter['shot']]
            expected_role = {'blender': 'mechanical-3d', 'remotion': 'information', 'footage': 'licensed-footage'}[spec['visual']['render_engine']]
            if (role != expected_role or segment['shot_id'] != chapter['shot'] or row['id'] != chapter['id']
                    or row['seconds'] != spec['seconds'] or segment['start_frame'] != cursor
                    or {k: row[k] for k in ('graphic', 'footage', 'chapter') if k in row} != editorial_props(spec)):
                raise ValueError('Timeline diverges from the approved visual shot')
            if role == 'licensed-footage':
                validate_footage(spec['footage'], seconds=spec['seconds'])
                if bound(segment['render_output']).resolve() != (ROOT / spec['footage']['path']).resolve():
                    raise ValueError('Footage asset differs from the licensed source')
                if 'split_screen' in spec:
                    sources = spec['split_screen']['sources']
                    exposed_sources = row.get('splitScreen', {}).get('sources', [])
                    bindings = segment.get('supplemental_sources', [])
                    if len(sources) != 2 or sources[0] != spec['footage'] or len(exposed_sources) != 2 or len(bindings) != 2:
                        raise ValueError('Split screen requires two bound sources')
                    for source, exposed_source, source_binding in zip(sources, exposed_sources, bindings, strict=True):
                        source_path = validate_footage(source, seconds=spec['seconds'])
                        relative = Path(exposed_source.get('media', ''))
                        if (relative.parts[:1] != ('cache',) or len(relative.parts) != 2
                                or '\\' in exposed_source['media']
                                or exposed_source.get('credit') != source['credit']
                                or exposed_source.get('startFrame') != source['start_frame']
                                or bound(source_binding).resolve() != source_path.resolve()):
                            raise ValueError('Split screen source differs from approved footage')
                        exposed = ROOT/'remotion/public'/relative
                        if (not exposed.resolve().is_relative_to((ROOT/'remotion/public/cache').resolve())
                                or filehash(exposed) != filehash(source_path)):
                            raise ValueError('Split screen public media differs from source')
                elif 'splitScreen' in row or segment.get('supplemental_sources'):
                    raise ValueError('Unapproved split screen media')
            elif role == 'information' and ('media' in row or 'render_output' in segment):
                raise ValueError('Information graphic cannot substitute unbound media')
        elif role != 'mechanical-3d' or {'graphic', 'footage', 'chapter'} & row.keys():
            raise ValueError('Legacy 3D-only composition cannot include editorial media')
        cursor += segment['frame_count']
        inputs = [('audio', 'audio')]
        if role != 'information':
            inputs.append(('media', 'render_output'))
        for key, binding_key in inputs:
            relative = Path(row[key])
            if (relative.parts[:1] != ('cache',) or len(relative.parts) != 2
                    or relative.name in {'..', '.'} or '\\' in row[key]):
                raise ValueError('Remotion media must use the local content cache')
            exposed = ROOT/'remotion/public'/relative
            if (not exposed.resolve().is_relative_to((ROOT/'remotion/public/cache').resolve())
                    or filehash(exposed) != filehash(bound(segment[binding_key]))):
                raise ValueError('Remotion media or audio differs from the verified inputs')
    if visual and (cursor != build['frame_count'] or len(config['storyboard']) != len(props['shots'])
                   or round(props['duration'] * 30) != cursor):
        raise ValueError('Incomplete visual timeline')
    return props_file


def write_remotion_proof(path, final, props_path, config, media, assembly, model):
    from .remotion_build import sources_for
    from .knowledge_progression import FIELD, enabled
    from .visual_narrative import VERSION, version
    visual = version(config) == VERSION
    props = json.loads(props_path.read_text())
    shots, segments = {}, []
    cursor = 0
    from .media_policy import FIELD as MEDIA_FIELD, enabled as asset_first
    hybrid = asset_first(config)
    has_blender = not visual or any(s['visual']['render_engine'] == 'blender' for s in config['shots'].values())
    model_assets = ([dict(binding(assembly), source='assembly configuration'),
                     dict(binding(model), source='actual Blender assembly input', cache_key=model.parent.name)]
                    if has_blender else [])
    for row, chapter in zip(props['shots'], config['storyboard'], strict=True):
        shot_id = chapter['shot']
        spec = config['shots'][shot_id]
        count = round(row['seconds'] * 30)
        segment = dict(shot_id=shot_id, chapter_id=row['id'],
                       audio=binding(ROOT/'remotion/public'/row['audio']), start_frame=cursor, frame_count=count)
        segments.append(segment)
        cursor += count
        if visual:
            engine = spec['visual']['render_engine']
            if engine == 'remotion':
                segment['media_kind'] = 'information'
                continue
            if engine == 'footage':
                segment.update(media_kind='licensed-footage', render_output=binding(media[shot_id][0]))
                if 'split_screen' in spec:
                    segment['supplemental_sources'] = [binding(ROOT/source['path']) for source in spec['split_screen']['sources']]
                continue
        raw, kind, cache_key = media[shot_id]
        basis = spec.get('science', {}).get('basis')
        if kind != 'video' or not basis:
            raise ValueError('Each chapter of a science proof needs a native 3D clip and located evidence')
        checks_file = raw.parent/'checks.json'
        checks = json.loads(checks_file.read_text())
        raw_ref = binding(raw)
        if shot_id not in shots:
            shots[shot_id] = dict(shot_id=shot_id, render_output=raw_ref, scene=checks['scene_artifact'],
                motion_data=binding(checks_file), executable_shot=checks['source_shot'], cache_key=cache_key,
                model_assets=model_assets,
                product_references=[dict(binding(ROOT/ref['path']), position=ref['position']) for ref in basis],
                shot_role=spec.get('science', {}).get('role', 'core'),
                verification_frames=sorted({1, round((1+count)/2), count}))
        segment['render_output'] = raw_ref
    build = dict(renderer='remotion-v1', frame_count=cursor, segments=segments,
                 props=binding(props_path), render_sources=[binding(ROOT/name) for name in sources_for(config)])
    if visual:
        build.update(visual_policy_version=VERSION, visual_config=config)
    if enabled(config):
        build[FIELD] = config[FIELD]
    if hybrid:
        build[MEDIA_FIELD] = config[MEDIA_FIELD]
    if config['render'].get('encode_profile') is not None:
        build['encode_profile'] = config['render']['encode_profile']
    verify_remotion_inputs(build)
    document = dict(schema_version=1, media=binding(final), render_route='3d',
        shots=list(shots.values()), build=build, formal_acceptance=False)
    if hybrid:
        document.update(media_policy_version=1, visual_policy_version=2,
                        media_contract='asset-first-hybrid-v1', original_3d_only_acceptance=False)
    writejson(path, document)


def compose(build, output):
    """Compose only real 3D renders with subtitles and narration."""
    if build.get('renderer') == 'remotion-v1':
        from .remotion_build import render
        from .knowledge_progression import enabled
        render(verify_remotion_inputs(build), output, output.with_suffix('.remotion.log'),
               encode_profile=build.get('encode_profile'), visual=build.get('visual_policy_version') == 2,
               progression=enabled(build))
        return
    audio=bound(build['narration']);ass=bound(build['subtitles'])
    for font in build.get('fonts',[]): bound(font)
    segments=build['segments']
    if not segments: raise ValueError('Complete 3D timeline required')
    inputs=[];filters=[];cursor=0
    for i,segment in enumerate(segments):
        role = segment.get('media_kind', 'mechanical-3d')
        if role != 'mechanical-3d':
            raise ValueError('3D-only production requires mechanical 3D segments')
        src=bound(segment['render_output'])
        start=segment.get('source_start_frame',0);count=segment['frame_count']
        if type(start)!=int or type(count)!=int or start<0 or count<=0:
            raise ValueError('Positive integer segment frame range required')
        if segment['start_frame']!=cursor: raise ValueError('3D build timeline has gap/overlap')
        inputs+=['-threads','2','-i',str(src)]
        filters.append(f'[{i}:v]trim=start_frame={start}:end_frame={start+count},setpts=PTS-STARTPTS[v{i}]')
        cursor+=count
    if cursor!=build['frame_count']:raise ValueError('Incomplete 3D build timeline')
    # Restrict filter paths to prevent authored ASS paths from injecting filters.
    for p in [ass,*[Path(v['path']) for v in build.get('fonts',[])]]:
        if any(c in str(p) for c in "'[];,:\\"):
            raise ValueError('Unsupported subtitle/font path')
    fontdir=Path(build['fonts'][0]['path']).parent if build.get('fonts') else ass.parent
    filters.append(''.join(f'[v{i}]' for i in range(len(segments)))+
                   f'concat=n={len(segments)}:v=1:a=0,setpts=N/(30*TB),ass={ass}:fontsdir={fontdir},fps=30:eof_action=pass,format=yuv420p[v]')
    cmd=['ffmpeg','-v','error','-y',*inputs,'-i',str(audio),'-filter_complex_threads','1','-filter_complex',';'.join(filters),
         '-map','[v]','-map',f'{len(segments)}:a:0','-frames:v',str(cursor),'-c:v','libx264',
         '-preset','fast','-crf','18','-threads','2','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)]
    subprocess.run(cmd,check=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],check=True)
    return cmd


def decoded_hash(path, kind='v'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map',f'0:{kind}:0',
        '-f','hash','-hash','sha256','-'],text=True).strip()


def verify_remotion_replay(original, replayed, frames):
    original_video, replay_video = (next(stream for stream in probe(path)['streams'] if stream['codec_type'] == 'video')
                                    for path in (original, replayed))
    fields = ('width', 'height', 'avg_frame_rate', 'start_time', 'nb_frames', 'pix_fmt')
    if (any(original_video.get(key) != replay_video.get(key) for key in fields)
            or int(replay_video['nb_frames']) != frames or decoded_hash(original, 'a') != decoded_hash(replayed, 'a')):
        raise ValueError('Remotion replay video format or decoded narration differs')
    if decoded_hash(original) == decoded_hash(replayed):
        return {'method': 'exact_decoded_hash', 'frames': frames, 'audio_exact': True}
    comparison = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(original), '-i', str(replayed),
                                 '-filter_complex', '[0:v][1:v]psnr=stats_file=-:shortest=1',
                                 '-an', '-f', 'null', '-'], capture_output=True, text=True, check=True)
    values = [float(value) for value in re.findall(r'\bpsnr_avg:([^\s]+)', comparison.stdout)]
    threshold = 45.0
    if len(values) != frames or any(not value >= threshold for value in values):
        raise ValueError('Remotion replay exceeds per-frame codec tolerance')
    lowest = min(values)
    return {'method': 'psnr_per_decoded_frame', 'frames': frames, 'audio_exact': True,
            'threshold_db': threshold, 'minimum_db': lowest if math.isfinite(lowest) else None}


def frame_rgb(path, frame, crop=None):
    region=''
    if crop:
        x,y,right,bottom=crop
        width,height=round((right-x)*1920)//2*2,round((bottom-y)*1080)//2*2
        if min(width,height)<8:raise ValueError('Mechanical subject is not visibly framed')
        region=f'crop={width}:{height}:{round(x*1920)//2*2}:{round(y*1080)//2*2},'
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf',
        f'select=eq(n\\,{frame}),{region}scale=320:320','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])


def validate(path, media=None, *, replay=True, stage='final'):
    # Reject malformed evidence without acquiring the heavy-production lock.
    # A missing film must not be obscured by another legitimate Blender job.
    document=json.loads(Path(path).read_text())
    if stage not in {'preview', 'workprint', 'final'}:
        raise ValueError('Unknown provenance verification stage')
    if stage != 'final': replay = False
    bound(document['media'])
    from .media_policy import enabled as asset_first
    if not document.get('shots') and not asset_first(document):
        raise ValueError('Unique core mechanical shots required')
    for shot in document['shots']:
        if not shot.get('model_assets') or not shot.get('product_references'):
            raise ValueError('Traceable model and product reference evidence required')
    if document.get('build', {}).get('renderer') == 'remotion-v1':
        verify_remotion_inputs(document['build'])
    from .workflow import lock
    key = digest(dict(inputs=verification_key(document, stage, replay), provenance=str(Path(path).resolve())))
    receipt = ROOT/'work/cache/provenance'/(key+'.json')
    if receipt.is_file():
        cached = json.loads(receipt.read_text())
        if cached.get('verification_key') == key:
            if media is not None and media != document['media']:
                raise ValueError('3D proof belongs to a different final MP4')
            return dict(cached, cache_hit=True)
    # Cache hits never start Blender and must not contend with a real render.
    with lock(ROOT/'work/production.lock'):
        result = _validate(path,media,replay=replay,stage=stage)
        result.update(verification_key=key, cache_hit=False, stage=stage)
        writejson(receipt,result)
        return result


def _validate(path, media=None, *, replay=True, stage='final'):
    doc=json.loads(Path(path).read_text());final=bound(doc['media'])
    if media is not None and (Path(media['path']).resolve()!=final.resolve() or media['sha256']!=filehash(final)):
        raise ValueError('3D proof belongs to a different final MP4')
    shots=doc['shots'];build=doc['build'];ids={s['shot_id'] for s in shots}
    from .media_policy import enabled as asset_first
    hybrid = asset_first(doc)
    if len(ids)!=len(shots) or (not shots and not hybrid):raise ValueError('Unique core mechanical shots required')
    stream=next(s for s in probe(final)['streams'] if s['codec_type']=='video')
    rate=stream['avg_frame_rate'].split('/')
    expected = ([1920,1080,30] if stage == 'final' else
                [build.get('width',1920),build.get('height',1080),build.get('fps',30)])
    # Stream-copy previews may round segment timestamps by a time-base tick.
    rate_tolerance = .001 if stage == 'final' else max(.001, 1/float(stream['duration']))
    if ((stream['width'],stream['height'])!=tuple(expected[:2])
            or abs(float(rate[0])/float(rate[1])-expected[2])>rate_tolerance
            or int(stream['nb_frames'])!=build['frame_count']):
        raise ValueError('Actual final MP4 must match complete native 3D build frame count and format')
    segments=build['segments']
    if {s['shot_id'] for s in segments if s.get('media_kind','mechanical-3d')=='mechanical-3d'}!=ids:
        raise ValueError('All core shots must match the actual MP4 build')
    visual = build.get('visual_policy_version') == 2
    if visual and build.get('renderer') != 'remotion-v1':
        raise ValueError('Visual replay requires the bound Remotion build')
    cursor=0
    for segment in segments:
        role=segment.get('media_kind','mechanical-3d')
        if role != 'information' or not visual:
            bound(segment['render_output'])
        if segment.get('start_frame')!=cursor or type(segment.get('frame_count'))!=int or segment['frame_count']<=0:
            raise ValueError('Build timeline has gap/overlap or invalid frame count')
        cursor+=segment['frame_count']
        if role!='mechanical-3d' and not (visual and role in {'licensed-footage', 'information'}):
            raise ValueError('3D-only production requires mechanical 3D segments')
    if cursor!=build['frame_count']:raise ValueError('Incomplete build timeline')
    if build.get('renderer') == 'remotion-v1':
        verify_remotion_inputs(build)
    if stage!='preview':
        subprocess.run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'],check=True)
    checks=[]
    composition_comparison = None
    with tempfile.TemporaryDirectory(prefix='mvn-3d-') as temporary:
        temp=Path(temporary)
        if replay and shutil.disk_usage(temp).free < 3*1024**3 + final.stat().st_size*2 + 64*1024**2:
            raise ValueError('Insufficient temporary disk space for provenance replay')
        for i,shot in enumerate(shots):
            scene=bound(shot['scene']);raw=bound(shot['render_output'])
            bound(shot['motion_data'])
            if not shot.get('model_assets') or not shot.get('product_references'):
                raise ValueError('Traceable model and product reference evidence required')
            for asset in shot['model_assets']:
                bound(asset)
                if not asset.get('source'):raise ValueError('Model origin required')
            for reference in shot['product_references']:bound(reference)
            for segment in segments:
                if (segment.get('media_kind','mechanical-3d')=='mechanical-3d'
                        and segment['shot_id']==shot['shot_id'] and segment['render_output']!=shot['render_output']):
                    raise ValueError('Timeline substituted another video for verified 3D render')
            frames=shot['verification_frames']
            if len(set(frames))<3:raise ValueError('At least three distinct actual render witness frames required')
            output=temp/f'{i}.json';renders=temp/str(i)
            cmd=[BLENDER,'-b',str(scene),'--python-exit-code','1','--python',str(ROOT/'blender/provenance_audit.py'),
                 '--','--output',str(output),'--frames',*[str(f) for f in frames]]
            if replay:cmd+=['--render-dir',str(renders)]
            with (temp/f'{i}.log').open('w') as log:
                subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
            audit=json.loads(output.read_text())
            if min(frames)<audit['frame_range'][0] or max(frames)>audit['frame_range'][-1]:
                raise ValueError('Render witness outside actual scene timeline')
            if not audit['spatial_motion'] and shot.get('shot_role') != 'structural_detail':
                raise ValueError('Core mechanical shot has no evidenced spatial motion: '+shot['shot_id'])
            if visual and build['visual_config']['shots'][shot['shot_id']]['visual']['mechanical_role'] == 'core' and not audit['spatial_motion']:
                raise ValueError('Planned core shot lacks real spatial motion: '+shot['shot_id'])
            if audit['resolution']!=expected[:2] or audit['fps']!=expected[2]:
                raise ValueError('Actual 3D scene must render native 1920x1080/30')
            errors=[]
            if replay:
                for f in frames:
                    # Compare the mechanical region, so a large plain studio
                    # background cannot conceal a different or missing mechanism.
                    bounds=audit['subject_bounds'].get(str(f))
                    if bounds is None:
                        bounds=audit['subject_bounds'][str(audit['frame_range'][1])]
                    actual=frame_rgb(raw,f-1,bounds);witness=frame_rgb(renders/f'{f:05d}.png',0,bounds)
                    if not actual or len(actual)!=len(witness):raise ValueError('Missing/mismatched rendered witness')
                    mae=sum(abs(a-b) for a,b in zip(actual,witness))/len(actual)
                    if mae>3:raise ValueError(f'Raw MP4 not from claimed scene: {shot["shot_id"]} frame {f}, MAE={mae}')
                    errors.append(mae)
            checks.append(dict(shot_id=shot['shot_id'],audit=audit,witness_mae=errors))
            print('Verified 3D scene/render: '+shot['shot_id'],flush=True)
        if not any(row['audit']['spatial_motion'] and
                   shot.get('shot_role')!='structural_detail' for row,shot in zip(checks,shots)) and not (
                       hybrid and any(s.get('visual', {}).get('mechanical_role') == 'core'
                           and s['visual']['render_engine'] == 'footage'
                           for s in build.get('visual_config', {}).get('shots', {}).values())):
            raise ValueError('A mechanical film cannot consist only of static structure details')
        if replay:
            recomposed=temp/'replayed.mp4';compose(build,recomposed)
            if build.get('renderer') == 'remotion-v1':
                composition_comparison = verify_remotion_replay(final, recomposed, build['frame_count'])
            elif decoded_hash(final)!=decoded_hash(recomposed) or decoded_hash(final,'a')!=decoded_hash(recomposed,'a'):
                raise ValueError('Final MP4 differs from full verified 3D build replay')
    return {'status':('HYBRID_PROVENANCE_PASS' if hybrid else 'PASS') if replay else 'SCENE_INSPECTED_NOT_RENDER_VERIFIED',
            'media':binding(final),'shots':checks,'full_build_replayed':replay,
            'composition_comparison':composition_comparison,
            'provenance':binding(path),
            'verifier':[binding(__file__),binding(ROOT/'blender/provenance_audit.py')],
            'scope':'Sampled scene-to-raw render witnesses; full raw-to-final decoded replay. Mechanical truth, product identity and viewing/listening remain separate QA.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('provenance',type=Path);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--stage', choices=['preview','workprint','final'], default='final')
    a=p.parse_args();result=validate(a.provenance,stage=a.stage);a.report.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
