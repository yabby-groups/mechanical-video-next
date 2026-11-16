"""Executable scene/render/build proof, separate from mechanical and perceptual QA.

Validation opens every scene in Blender, rejects planar mechanical substitutes,
rerenders sampled frames and compares them with the recorded raw render. It then
replays the restricted full-film composition and compares *all* decoded frames.
No arbitrary shell command from a provenance document is ever executed.
"""
import argparse
import json
from pathlib import Path
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


def compose(build, output):
    """Compose only real 3D renders with subtitles and narration."""
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
                   f'concat=n={len(segments)}:v=1:a=0,ass={ass}:fontsdir={fontdir},fps=30,format=yuv420p[v]')
    cmd=['ffmpeg','-v','error','-y',*inputs,'-i',str(audio),'-filter_complex_threads','1','-filter_complex',';'.join(filters),
         '-map','[v]','-map',f'{len(segments)}:a:0','-frames:v',str(cursor),'-c:v','libx264',
         '-preset','fast','-crf','18','-threads','2','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)]
    subprocess.run(cmd,check=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],check=True)
    return cmd


def decoded_hash(path, kind='v'):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map',f'0:{kind}:0',
        '-f','hash','-hash','sha256','-'],text=True).strip()


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
    if not document.get('shots'):
        raise ValueError('Unique core mechanical shots required')
    for shot in document['shots']:
        if not shot.get('model_assets') or not shot.get('product_references'):
            raise ValueError('Traceable model and product reference evidence required')
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
    if len(ids)!=len(shots) or not shots:raise ValueError('Unique core mechanical shots required')
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
    cursor=0
    for segment in segments:
        bound(segment['render_output'])
        if segment.get('start_frame')!=cursor or type(segment.get('frame_count'))!=int or segment['frame_count']<=0:
            raise ValueError('Build timeline has gap/overlap or invalid frame count')
        cursor+=segment['frame_count']
        role=segment.get('media_kind','mechanical-3d')
        if role!='mechanical-3d':
            raise ValueError('3D-only production requires mechanical 3D segments')
    if cursor!=build['frame_count']:raise ValueError('Incomplete build timeline')
    if stage!='preview':
        subprocess.run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'],check=True)
    checks=[]
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
                   shot.get('shot_role')!='structural_detail' for row,shot in zip(checks,shots)):
            raise ValueError('A mechanical film cannot consist only of static structure details')
        if replay:
            recomposed=temp/'replayed.mp4';compose(build,recomposed)
            if decoded_hash(final)!=decoded_hash(recomposed) or decoded_hash(final,'a')!=decoded_hash(recomposed,'a'):
                raise ValueError('Final MP4 differs from full verified 3D build replay')
    return {'status':'PASS' if replay else 'SCENE_INSPECTED_NOT_RENDER_VERIFIED',
            'media':binding(final),'shots':checks,'full_build_replayed':replay,
            'provenance':binding(path),
            'verifier':[binding(__file__),binding(ROOT/'blender/provenance_audit.py')],
            'scope':'Sampled scene-to-raw render witnesses; full raw-to-final decoded replay. Mechanical truth, product identity and viewing/listening remain separate QA.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('provenance',type=Path);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--stage', choices=['preview','workprint','final'], default='final')
    a=p.parse_args();result=validate(a.provenance,stage=a.stage);a.report.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
