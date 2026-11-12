#!/usr/bin/env -S uv run python
"""Small authored nail-clipper illustration adapter sharing measured narration.

2D is orthographic geometry; 2.5D projects layered extruded profiles with a
moving camera and a half-width cutaway. Prescribed flexure is not simulation.
"""
import argparse
import fcntl
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont
from common import ROOT, budget, digest, filehash, probe, run, writejson
from narration import load_env, load_profile, sentence, normalize, srt_time

OUT = ROOT / 'output/nail-clipper'
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
SCRIPT = [
    ('hook', '轻轻一按，刀口就合拢。小小的指甲刀，怎样放大手指的力量？', '一按之间，力量去了哪里？'),
    ('parts', '拆开来看，主要是上下两片弹性刀体、支点销，还有上面的压柄。', '四个部件，一条传力链'),
    ('lever', '按下长压柄，凸轮压住上刀体，支点销同时牵住下刀体。', '压柄 → 凸轮与销 → 两片刀体'),
    ('cut', '长端移动一大段，刀口只靠近一点。杠杆用行程，换来更大的剪切力。', '长行程输入 · 短行程输出'),
    ('return', '刀口合拢，剪断指甲。松开手，弹性刀体恢复，刀口重新张开。', '合拢剪切 → 松手复位'),
    ('summary', '省力的秘密，就是杠杆传力、刀口剪切，再由刀体弹性复位。', '传力 · 剪切 · 弹性复位'),
]


def prepare_audio(env_file=None):
    """Synthesize each utterance once; determine all shot lengths from real audio."""
    load_env(env_file or (ROOT/'.env.local' if (ROOT/'.env.local').exists() else None))
    profile = load_profile(ROOT / 'config/narration-neil.json')
    shared = OUT / 'shared'
    shared.mkdir(parents=True, exist_ok=True)
    key = digest({'script': SCRIPT, 'profile': profile, 'audio_code': filehash(ROOT/'scripts/narration.py')})
    path = shared / 'timeline.json'
    if path.exists():
        old = json.loads(path.read_text())
        if old.get('audio_key') == key and (shared/'narration.wav').is_file() and filehash(shared/'narration.wav') == old['audio_sha256']:
            return old
    clips, shots, cursor = [], [], 0.0
    for ident, text, title in SCRIPT:
        clip, receipt = sentence(text, profile)
        duration = float(probe(clip)['format']['duration'])
        seconds = math.ceil((duration + .7) * 30) / 30
        padded = shared / (ident + '.wav')
        run(['ffmpeg', '-v', 'error', '-y', '-i', clip, '-af', 'adelay=200:all=1,apad',
             '-t', seconds, '-ar', '48000', '-ac', '1', padded], shared/(ident+'.audio.log'))
        # Punctuation-sized display cues: timing is utterance proportional, not ASR.
        pieces = [p for p in __import__('re').split('(?<=[，。？])', text) if p]
        total = sum(len(p) for p in pieces)
        cues, local = [], .2
        for piece in pieces:
            end = local + duration*len(piece)/total
            cues.append({'start': round(local, 3), 'end': round(end, 3), 'text': piece})
            local = end
        shots.append({'id': ident, 'start': cursor, 'seconds': seconds, 'narration': text,
                      'title': title, 'cues': cues, 'audio': str(padded.relative_to(ROOT)), 'cache': receipt})
        clips.append(padded)
        cursor += seconds
    (shared/'concat.txt').write_text(''.join(f"file '{p.name}'\n" for p in clips))
    joined = shared/'joined.wav'
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','1','-i',shared/'concat.txt','-c:a','copy',joined],shared/'join.log')
    normalize(joined,shared/'narration.wav',profile)
    cues = [dict(c, start=c['start']+s['start'], end=c['end']+s['start']) for s in shots for c in s['cues']]
    (shared/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
    result = {'topic': '指甲刀', 'voice':'Neil', 'audio_key':key, 'audio_sha256':filehash(shared/'narration.wav'),
              'width':1920, 'height':1080, 'fps':30, 'seconds':round(cursor,6), 'shots':shots,
              'subtitle_alignment':'Punctuation units proportioned within measured utterances; not phoneme alignment',
              'scope':'原理示意：规定弹性弯曲，不是材料或接触仿真'}
    writejson(path,result)
    return result


def smooth(t):
    t = max(0,min(1,t))
    return t*t*(3-2*t)


def phase(ident,t):
    if ident == 'parts': return .0
    if ident == 'return': return smooth(t/.18) if t<.18 else 1-smooth((t-.35)/.65)
    # Closed hold at the middle makes the cutting edge readable.
    return smooth(t/.30) if t<.30 else 1 if t<.65 else 1-smooth((t-.65)/.35)


def body_z(x,upper,q):
    u=max(0,min(1,(x-6)/44)); f=u*u*(3-2*u)
    u30=24/44; f30=u30*u30*(3-2*u30)
    return (1 if upper else -1)*((1-q)*f+.7*min(f/f30,1)*(1 if x<=46 else (50-x)/4))


def geometry(ident,t):
    q=phase(ident,t)
    spread=9*math.sin(math.pi*t)**2 if ident=='parts' else 0
    pieces=[]
    for upper,name,color in [(False,'下刀体',(86,116,139)),(True,'上刀体',(52,170,185))]:
        off=spread*(1 if upper else -1)
        # Closed mouth retains .3 mm schematic clearance (nail thickness omitted).
        profile=[(x,body_z(x,upper,q)+off) for x in range(0,51)]
        profile += [(x,z+(1 if upper else -1)*(1-(.85*max(0,min(1,(x-47)/3))))) for x,z in reversed(profile)]
        pieces.append((name,profile,10,color))
    # Use the exact v5 rigid poses; their seat equation was checked against CAD.
    motion=motion_data()
    tracks={x['object']:x['poses'] for x in motion['tracks']}
    def sample(name,key,index):
        poses=tracks[name]; f=q*(len(poses)-1);i=min(len(poses)-2,int(f));r=f-i
        return (poses[i][key][index]*(1-r)+poses[i+1][key][index]*r)
    pivot=sample('operating_lever_cam','location',2)*1000
    angle=sample('operating_lever_cam','rotation_euler',1)
    dz=sample('pull_post_axle','location',2)*1000
    bottom=-2.6767085900592+dz+spread*1.3
    top=3.4+dz+1.15+spread*1.3
    c=(222,144,79)
    pieces.append(('支点销',[(44.8,bottom),(46.2,bottom),(46.2,top),(44.8,top)],1.4,c))
    pieces.append(('销帽',[(43.7,bottom-.5),(47.3,bottom-.5),(47.3,bottom),(43.7,bottom)],3.6,c))
    pieces.append(('上钩',[(43.8,top-.55),(46.3,top-.55),(46.3,top),(43.8,top)],2,c))
    def tr(x,z):return (44+x*math.cos(angle)+z*math.sin(angle),pivot-x*math.sin(angle)+z*math.cos(angle)+2*spread)
    color=(213,163,71)
    pieces.append(('压柄',[tr(x,z) for x,z in [(-39,0),(-2,0),(-2,1.2),(-39,1.2)]],8,color))
    pieces.append(('压柄叉座',[tr(x,z) for x,z in [(-3,0),(.25,0),(.25,1.2),(-3,1.2)]],1,color))
    pieces.append(('横轴',[tr(.6*math.cos(a*math.pi/16),.6*math.sin(a*math.pi/16)) for a in range(32)],8,color))
    pieces.append(('凸轮颈',[tr(x,z) for x,z in [(-4.5,-2.6),(-3.5,-2.6),(-3.5,.6),(-4.5,.6)]],2.6,color))
    pieces.append(('凸轮',[tr(-4+.6*math.cos(a*math.pi/16),-2.6+.6*math.sin(a*math.pi/16)) for a in range(32)],2.6,color))
    # Integral upper pressure ridge, directly underneath the cam.
    pieces.append(('承压台',[(x,body_z(x,True,q)+z+spread) for x,z in [(38,1),(42,1),(42,1.8),(38,1.8)]],2,(52,170,185)))
    return pieces,q


_MOTION=None
def motion_data():
    global _MOTION
    if _MOTION is None:_MOTION=json.loads((ROOT/'assets/assemblies/nail-clipper-cad-v5/motion.json').read_text())
    return _MOTION


def font(n,scale): return ImageFont.truetype(FONT,max(10,round(n*scale)))


def text(draw,xy,value,size=30,fill='#27394b',scale=1,anchor=None):
    draw.text(xy,value,font=font(size,scale),fill=fill,anchor=anchor)


def arrow(draw,a,b,color,width=5):
    draw.line([a,b],fill=color,width=width)
    angle=math.atan2(b[1]-a[1],b[0]-a[0])
    r=width*3
    draw.polygon([b,(b[0]-r*math.cos(angle-.5),b[1]-r*math.sin(angle-.5)),
                    (b[0]-r*math.cos(angle+.5),b[1]-r*math.sin(angle+.5))],fill=color)


STYLE_PATH = ROOT / 'config/nail-clipper-visual-style.json'
STYLE = json.loads(STYLE_PATH.read_text())
_FRAMING = {}


def frame(route,shot,t,size=(1920,1080),overlay_only=False):
    """EP03 art direction; illustrations retain their own real geometry/projection."""
    w,h=size; sc=w/1920
    im=Image.new('RGBA',size,(0,0,0,0))
    d=ImageDraw.Draw(im)
    def xy(x,y):return (x*sc,y*sc)
    def label(x,y,value,n=28,color=None):
        d.text(xy(x,y),value,font=font(n,sc),fill=color or STYLE['label'],
               stroke_width=max(1,round(sc)),stroke_fill='#293b4b')
    if not overlay_only:
        top=STYLE['background_top'];bottom=STYLE['background_bottom']
        for y in range(h):
            a=y/h
            d.line([(0,y),(w,y)],fill=tuple(round(c*(1-a)+b*a) for c,b in zip(top,bottom)))
        pieces,q=geometry(shot['id'],t)
        iso=route=='2.5d'
        # Each close-up is a camera reframe of the same moving mechanism.
        close = 1 if shot['id']=='cut' else smooth((t-.35)/.25) if shot['id']=='hook' else 0
        yaw=.65+.07*math.sin(t*math.pi) if iso else 0
        key=(shot['id'],iso)
        if key not in _FRAMING:
            points=[]
            for sample_t in (0,.25,.5,.75,1):
                for _,profile,width,_ in geometry(shot['id'],sample_t)[0]:
                    for x,z in profile:
                        for y in (-width/2,width/2):
                            points.append((x+(y*.65 if iso else 0),-z-(x*.12*.72 if iso else 0)+(y*.34 if iso else 0)))
            lo=[min(v[i] for v in points) for i in (0,1)];hi=[max(v[i] for v in points) for i in (0,1)]
            _FRAMING[key]=(min(27,1600/(hi[0]-lo[0]),690/(hi[1]-lo[1])),[(a+b)/2 for a,b in zip(lo,hi)])
        base_unit,center=_FRAMING[key]
        unit=(base_unit*(1-close)+58*close)*sc
        cx=center[0]*(1-close)+40*close
        cy=center[1]*(1-close)-5*close
        def proj(x,y,z):
            return (w*.49+(x+(y*.65 if iso else 0)-cx)*unit,
                    h*.47+(-z-x*.12*yaw+(y*.34 if iso else 0)-cy)*unit)
        if iso:
            shadow=Image.new('RGBA',size,(0,0,0,0));sd=ImageDraw.Draw(shadow)
            sd.ellipse([xy(200,690),xy(1740,820)],fill=(17,30,42,100))
            from PIL import ImageFilter
            im=Image.alpha_composite(im,shadow.filter(ImageFilter.GaussianBlur(23*sc)));d=ImageDraw.Draw(im)
        for name,profile,width,color in pieces:
            group=name if name in STYLE['parts'] else '压柄' if name in ('压柄叉座','横轴','凸轮颈','凸轮') else '支点销'
            color=tuple(STYLE['parts'][group])
            half=iso and shot['id']=='cut' and name=='上刀体'
            y0,y1=(-width/2,0 if half else width/2)
            front=[proj(x,y0,z) for x,z in profile];back=[proj(x,y1,z) for x,z in profile]
            if iso:
                d.polygon(back,fill=tuple(min(255,c+25) for c in color))
                for i in range(len(profile)):
                    j=(i+1)%len(profile)
                    shade=.64 if profile[j][1]<profile[i][1] else .82
                    d.polygon([front[i],back[i],back[j],front[j]],fill=tuple(round(c*shade) for c in color))
            d.polygon(front,fill=color,outline=STYLE['outline'],width=max(1,round(2*sc)))
            if iso:
                d.line(front[:min(len(front),51)],fill=tuple(min(255,c+37) for c in color),width=max(1,round(2*sc)))
        def callout(value,anchor,position,color=None):
            label(position[0],position[1],value,28,color)
            end=xy(position[0]+min(180,len(value)*23),position[1]+35)
            d.line([end,anchor],fill=color or '#c8d7df',width=max(1,round(2*sc)))
            r=3*sc;d.ellipse([anchor[0]-r,anchor[1]-r,anchor[0]+r,anchor[1]+r],fill=color or '#c8d7df')
        if shot['id']=='parts':
            spread=9*math.sin(math.pi*t)**2
            handle=next(p for n,p,_,_ in pieces if n=='压柄')
            cx=sum(x for x,z in handle)/len(handle);cz=sum(z for x,z in handle)/len(handle)
            callout('压柄',proj(cx,0,cz),(260,200))
            callout('支点销',proj(45.5,0,5+spread),(1450,350),'#e5b281')
            callout('上刀体',proj(30,0,body_z(30,True,0)+spread),(1040,240))
            callout('下刀体',proj(17,0,body_z(17,False,0)-spread),(330,800))
        elif shot['id']=='lever':
            handle=next(p for n,p,_,_ in pieces if n=='压柄')
            hx=(handle[0][0]*.9+handle[1][0]*.1);hz=(handle[0][1]*.9+handle[1][1]*.1)
            a=proj(hx,0,hz+8);b=proj(hx,0,hz+.7)
            arrow(d,(a[0],max(85*sc,a[1])),b,'#e2a071',max(2,round(5*sc)))
            callout('凸轮压住上刀体',proj(40,0,body_z(40,True,q)+1.8),(1080,270),'#86c7c8')
            callout('销牵住下刀体',proj(45.5,0,-1),(1270,740),'#e5b281')
        elif shot['id']=='cut':
            callout('刀口靠近',proj(49,0,0),(1280,760),'#a7d8d5')
            if iso:label(100,800,'局部剖示',24,'#c2d2dc')
        elif shot['id']=='return':
            # Nail is drawn at the same projected jaw, not in a separate inset.
            nailz=0;broken=t>.20
            front_y=-7 if iso else -5.4
            a=proj(48.2,front_y,nailz-(2.6 if broken else 0));b=proj(50.0,front_y,nailz-(1.1 if broken else 0))
            c=proj(50.25,front_y,nailz);e=proj(54.8,front_y,nailz)
            d.line([a,b],fill='#e6b9a2',width=max(3,round(11*sc)))
            d.line([c,e],fill='#e6b9a2',width=max(3,round(11*sc)))
            if t>.4:callout('弹性回复',proj(30,0,body_z(30,True,q)),(700,270),'#a7d8d5')
        elif shot['id']=='summary':
            label(660,790,'杠杆传力   ·   剪切   ·   弹性复位',30)
    # The opening and ending exist within the scene rather than title cards.
    if shot['id']=='hook' and t<.32:
        label(90,82,'指甲刀',38)
        label(92,137,'一按之间，力量去了哪里？',26,'#bdcdd7')
    if shot['id']=='summary' and t>.72:label(90,84,'机械的日常 · 指甲刀',28)
    label(90,900,'原理示意 · 弯曲与间隙放大',22,'#bacbd5')
    local=t*shot['seconds']
    cue=next((c['text'] for c in shot['cues'] if c['start']<=local<c['end']),'')
    if cue:
        sub=STYLE['subtitles']
        d.text((w/2,sub['y']*sc),cue,font=font(sub['size'],sc),fill='white',anchor='mm',
               stroke_width=max(1,round(sub['stroke']*sc)),stroke_fill='#1d2a36')
    return im if overlay_only else im.convert('RGB')


def render(route,quality='final'):
    timeline=json.loads((OUT/'shared/timeline.json').read_text())
    folder=OUT/('2_5d' if route=='2.5d' else route)
    folder.mkdir(parents=True,exist_ok=True)
    preview=quality=='preview'
    width,height,fps=(960,540,15) if preview else (1920,1080,30)
    key=digest({'timeline':timeline,'route':route,'size':[width,height,fps],'code':filehash(__file__),
                'motion':filehash(ROOT/'assets/assemblies/nail-clipper-cad-v5/motion.json'),
                'narration':filehash(OUT/'shared/narration.wav'),'visual_style':filehash(STYLE_PATH)})
    target=folder/('animatic.mp4' if preview else 'final.mp4')
    receipt=target.with_suffix('.json')
    if receipt.exists() and target.exists():
        old=json.loads(receipt.read_text())
        if old.get('key')==key and old.get('sha256')==filehash(target):return target
    budget(); started=time.time()
    with (folder/(quality+'.encode.log')).open('w') as log:
        proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24',
            '-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-i',str(OUT/'shared/narration.wav'),
            '-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
            '-c:a','aac','-b:a','160k','-movflags','+faststart','-t',str(timeline['seconds']),str(target)],stdin=subprocess.PIPE,stderr=log)
        try:
            for shot in timeline['shots']:
                count=round(shot['seconds']*fps)
                for i in range(count):
                    if i%fps==0:budget()
                    proc.stdin.write(frame(route,shot,i/max(1,count-1),(width,height)).tobytes())
                frame(route,shot,.5,(width,height)).save(folder/(shot['id']+'-'+quality+'.jpg'))
            proc.stdin.close()
            if proc.wait():raise RuntimeError('Encoder failed: see '+str(log.name))
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
    run(['ffmpeg','-v','error','-i',target,'-f','null','-'],folder/(quality+'.decode.log'))
    writejson(receipt,{'key':key,'sha256':filehash(target),'seconds':time.time()-started,'route':route,
                      'technical_decode':'PASS','visual_review':'UNKNOWN','scientific_review':'UNKNOWN',
                      'input_hashes':{'timeline':filehash(OUT/'shared/timeline.json'),'script':filehash(__file__)},
                      'scope':'Authored geometric illustration, prescribed deformation, not physical simulation'})
    return target


def render_3d(quality='preview'):
    """Serial EAS/EEVEE shots and shared editorial layer; never claims acceptance."""
    from common import Metrics
    import produce
    timeline=json.loads((OUT/'shared/timeline.json').read_text())
    folder=OUT/'3d';folder.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((folder/'config/full.json').read_text())
    preview=quality=='preview'
    w,h,fps=(960,540,15) if preview else (1920,1080,30)
    key=digest({'config':cfg,'timeline':timeline,'quality':quality,'editor':filehash(__file__),
                'renderer':filehash(ROOT/'blender/scene.py'),'production':filehash(ROOT/'scripts/produce.py'),
                'assembly':filehash(ROOT/cfg['assembly_config']),
                'glb':filehash(ROOT/'assets/assemblies/nail-clipper-cad-v5/assembly.glb'),
                'narration':filehash(OUT/'shared/narration.wav'),
                'studio':filehash(ROOT/'blender/studio_style.py'),'visual_style':filehash(STYLE_PATH)})
    target=folder/('animatic.mp4' if preview else 'final.mp4')
    receipt=target.with_suffix('.json')
    if target.exists() and receipt.exists():
        old=json.loads(receipt.read_text())
        if old.get('key')==key and old.get('sha256')==filehash(target):return target
    metrics=Metrics('nail-clipper-3d-'+quality)
    started=time.time(); media=[]
    lock=ROOT/'work/production.lock';lock.parent.mkdir(exist_ok=True)
    with lock.open('a') as held:
        fcntl.flock(held,fcntl.LOCK_EX)
        model=produce.asset(metrics,cfg['assembly_config'])
        for shot in timeline['shots']:
            spec=cfg['shots'][shot['id']]
            source,kind,cache=produce.make_shot(spec,'preview' if preview else 'final',model,metrics,cfg['render'],cfg['assembly_config'])
            if kind!='video':raise ValueError('Three-route timeline requires dynamic shot media')
            media.append({'shot':shot['id'],'path':str(source),'sha256':filehash(source),'key':cache})
        fcntl.flock(held,fcntl.LOCK_UN)
    concat=folder/('concat-'+quality+'.txt')
    concat.write_text(''.join(f"file '{m['path']}'\n" for m in media))
    silent=folder/('silent-'+quality+'.mp4')
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',concat,'-c','copy',silent],folder/('concat-'+quality+'.log'))
    decoder=subprocess.Popen(['ffmpeg','-v','error','-i',str(silent),'-fps_mode','passthrough',
        '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=(folder/('decode-source-'+quality+'.log')).open('w'))
    with (folder/('editor-'+quality+'.log')).open('w') as log:
        encoder=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}',
            '-r',str(fps),'-i','pipe:0','-i',str(OUT/'shared/narration.wav'),'-c:v','libx264','-preset','veryfast',
            '-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',str(timeline['seconds']),
            '-movflags','+faststart',str(target)],stdin=subprocess.PIPE,stderr=log)
        try:
            for shot in timeline['shots']:
                count=round(shot['seconds']*fps)
                for index in range(count):
                    data=decoder.stdout.read(w*h*3)
                    if len(data)!=w*h*3:raise RuntimeError('3D source ended before shared timeline')
                    native=Image.frombytes('RGB',(w,h),data)
                    canvas=native.convert('RGBA')
                    canvas=Image.alpha_composite(canvas,frame('3d',shot,index/max(1,count-1),(w,h),overlay_only=True))
                    encoder.stdin.write(canvas.convert('RGB').tobytes())
                    if index==count//2:canvas.convert('RGB').save(folder/(shot['id']+'-'+quality+'.jpg'))
                budget()
            if decoder.stdout.read(1):raise RuntimeError('3D source has more frames than shared timeline')
            encoder.stdin.close()
            if encoder.wait():raise RuntimeError('3D editorial encoding failed')
            decoder.stdout.close()
            if decoder.wait():raise RuntimeError('3D source decode failed')
        finally:
            for child in [encoder,decoder]:
                if child.poll() is None:child.kill();child.wait()
    run(['ffmpeg','-v','error','-i',target,'-f','null','-'],folder/(quality+'.decode.log'))
    stats=metrics.finish(status='TECHNICAL_PASS_UNACCEPTED_CANDIDATE',media=media)
    writejson(receipt,{'key':key,'sha256':filehash(target),'seconds':time.time()-started,'media':media,
                      'metrics':stats,'technical_decode':'PASS','continuous_visual_review':'UNKNOWN','listening_review':'UNKNOWN'})
    return target


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['audio','render','render-3d','keys'])
    ap.add_argument('--route',choices=['2d','2.5d'],default='2d')
    ap.add_argument('--quality',choices=['preview','final'],default='final')
    ap.add_argument('--env-file',type=Path)
    args=ap.parse_args()
    if args.action=='audio': print(json.dumps(prepare_audio(args.env_file),ensure_ascii=False))
    elif args.action=='render': print(render(args.route,args.quality))
    elif args.action=='render-3d': print(render_3d(args.quality))
    else:
        timeline=json.loads((OUT/'shared/timeline.json').read_text())
        folder=OUT/('2_5d' if args.route=='2.5d' else '2d');folder.mkdir(parents=True,exist_ok=True)
        for shot in timeline['shots']:
            for i,t in enumerate([0,.5,1]):frame(args.route,shot,t).save(folder/f'{shot["id"]}-key-{i}.png')


if __name__=='__main__': main()
