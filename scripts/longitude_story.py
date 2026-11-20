"""Render the original illustrated longitude workprint with the measured Neil edit."""
import argparse
import json
import math
from functools import lru_cache
from pathlib import Path
import random
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mechanical_video_next import joint_timeline as joint
from scripts.common import ROOT, probe, writejson
from mechanical_video_next.workflow import lock

BLUE = '#113941'
OCEAN = '#1d555a'
INK = '#183539'
PAPER = '#ede3cb'
CREAM = '#fff1cf'
GOLD = '#f3b654'
RED = '#cf5142'
W, H = 960, 540


@lru_cache
def font(size, serif=False):
    name = 'Supplemental/Songti.ttc' if serif else 'Hiragino Sans GB.ttc'
    return ImageFont.truetype('/System/Library/Fonts/' + name, size)


def words(draw, x, y, text, size=24, color=CREAM, anchor='mm', serif=False):
    draw.text((x, y), text, font=font(size, serif), fill=color, anchor=anchor)


def circle(draw, x, y, r, fill=None, outline=None, width=1):
    draw.ellipse((x-r, y-r, x+r, y+r), fill=fill, outline=outline, width=width)


def ease(value):
    u = max(0, min(1, value))
    return u*u*(3-2*u)


@lru_cache
def background(dark):
    image = Image.new('RGB', (W, H), BLUE if dark else PAPER)
    draw = ImageDraw.Draw(image)
    rng = random.Random(41)
    palette = ('#17414a', '#153d46', '#23494d') if dark else ('#e9ddc4', '#e5d9be', '#e9ddca')
    for _ in range(9000):
        x, y = rng.randrange(W), rng.randrange(H)
        draw.line((x,y,x+rng.randrange(1,8),y), fill=rng.choice(palette))
    return image


def clock(draw, x, y, r, hour, minute, label=None, accent=GOLD):
    circle(draw,x,y,r+8, '#88633a', '#3b2c24', 4)
    circle(draw,x,y,r+3,'#c59b53', GOLD, 2)
    circle(draw,x,y,r,CREAM, '#6d4b36', 2)
    for i in range(60):
        a = i*math.tau/60
        inner = r * (.86 if i%5==0 else .93)
        draw.line((x+inner*math.sin(a),y-inner*math.cos(a),x+r*.96*math.sin(a),y-r*.96*math.cos(a)),
                  fill=INK, width=2 if i%5==0 else 1)
    for i in range(1,13):
        a = i*math.tau/12
        words(draw,x+r*.69*math.sin(a),y-r*.69*math.cos(a),str(i),int(r*.21),INK,serif=True)
    for value, length, width, color in ((hour+minute/60,r*.47,5,INK),(minute/5,r*.75,3,RED)):
        a = value*math.tau/12
        draw.line((x,y,x+length*math.sin(a),y-length*math.cos(a)),fill=color,width=width)
    circle(draw,x,y,4,RED)
    if label:
        words(draw,x,y+r+39,label,25,accent)


def ship(draw,x,y,s):
    def polygon(points, fill, outline):
        draw.polygon([(x+a*s,y+b*s) for a,b in points],fill=fill,outline=outline,width=max(1,int(2*s)))
    polygon([(-63,3),(-42,25),(32,25),(65,1),(22,13),(-43,12)],'#8b5038',INK)
    draw.line((x-4*s,y+12*s,x-4*s,y-96*s),fill=INK,width=max(2,int(4*s)))
    draw.line((x+30*s,y+12*s,x+30*s,y-59*s),fill=INK,width=max(2,int(3*s)))
    polygon([(-8,-86),(-45,-23),(-8,-28),(-22,-47)],'#d8c09b',INK)
    polygon([(0,-84),(35,-24),(0,-26),(12,-48)],CREAM,INK)
    polygon([(34,-58),(61,-10),(33,-14),(43,-31)],'#e6cda6',INK)
    polygon([(-5,-97),(22,-91),(-5,-85)],RED,INK)


def sky(draw, frame, u, ending=False):
    y = 147 + 122*(1-ease(u*2.1))
    circle(draw, 690, y, 43, GOLD, '#ffe7a0', 2)
    for row in range(12):
        y0=304+row*15
        wave=[(x,y0+4*math.sin(x/37+row*.45+frame*.061)) for x in range(-5,965,5)]
        draw.line(wave, fill=('#2d6870' if row%3 else '#3e7980'),width=2)
    for i in range(9):
        length=35+i*9
        tx=690+20*math.sin(i+frame*.083)
        draw.line((tx-length,310+i*14,tx+length,310+i*14),fill='#ab935d',width=2)
    ship(draw, 338+65*ease(u) ,362+5*math.sin(frame*.065),1.53)
    if ending:
        clock(draw,763,327,65,13,0)
        words(draw,275,83,'把港口的正午带上船',39,CREAM,serif=True)
    else:
        words(draw,74,75,'海上没有路牌',48,CREAM,anchor='lm',serif=True)


def meridians(draw, frame, u, error=False):
    if error:
        drift = 4*ease((u-.28)*2.4)
        clock(draw,244,245,102,12,drift)
        words(draw,244,399,'计时误差',25,INK)
        words(draw,713,142,'经度误差',25,INK)
        y=253
        draw.line((537,y,887,y),fill=INK,width=3)
        for i in range(6):
            x=549+i*65
            draw.line((x,y-14,x,y+14), fill=INK,width=2)
            words(draw,x,y+38,f'{i}°',20,INK)
        x=549+65*drift/4
        draw.polygon([(x,y-8),(x-12,y-34),(x+12,y-34)],fill=RED)
        if u>.65:
            words(draw,713,383,'快 4 分钟 · 偏 1°',36,RED,serif=True)
        return
    x,y,r=480,239,141
    circle(draw,x,y,r,'#235b60','#92b0a1',2)
    for fraction in (.27,.6,.9):
        draw.ellipse((x-r*fraction,y-r,x+r*fraction,y+r),outline='#5e8c8a',width=2)
    for dy in (-65,0,65):
        width=math.sqrt(r*r-dy*dy)
        draw.line((x-width,y+dy,x+width,y+dy),fill='#5e8c8a',width=2)
    theta=math.radians(15)*ease((u-.34)*3)
    x2=x+r*math.sin(theta)
    draw.arc((x-r*math.sin(theta),y-r,x2,y+r),-90,90,fill=RED,width=4)
    draw.line((x,y-r,x,y+r),fill=GOLD,width=3)
    words(draw,480,55,'按同一太阳时口径比较',23,CREAM)
    clock(draw,183,245,83,12,0,'船上当地正午')
    clock(draw,777,245,83,12+ease(u*2.3),0,'同一刻的港口时间')
    words(draw,480,420,'船在港口以西 15°' if u>.58 else '同一个时刻',31,CREAM,serif=True)


def route(draw, u):
    draw.rectangle((52,78,907,426),outline='#c7af82',width=2)
    for x in range(105,907,75):
        draw.line((x,78,x,426),fill='#d2c1a2')
    for y in range(106,426,52):
        draw.line((52,y,907,y),fill='#d2c1a2')
    draw.polygon([(52,79),(264,79),(233,111),(190,136),(199,157),(162,175),(139,206),(112,218),(149,238),
                  (156,273),(117,255),(83,282),(52,276)],fill='#b2b99a',outline='#849d88',width=2)
    draw.polygon([(181,333),(249,326),(289,356),(265,425),(173,425),(157,394)],fill='#b2b99a',
                 outline='#849d88',width=2)
    draw.polygon([(699,79),(906,79),(906,425),(761,425),(763,355),(727,303),(703,265),(746,218),
                  (762,179),(736,153),(756,127),(707,114)],fill='#b2b99a',outline='#849d88',width=2)
    start,end=(742,122),(175,309)
    path=[]
    for i in range(51):
        p=i/50
        path.append((start[0]+(end[0]-start[0])*p,start[1]+(end[1]-start[1])*p+60*math.sin(math.pi*p)))
    n=2+round(49*ease(u*1.10))
    draw.line(path[:n],fill=RED,width=4)
    for x,y,label in ((*start,'英国'),(*end,'牙买加')):
        circle(draw,x,y,6,RED,CREAM,2)
        words(draw,x,y+27,label,21,INK,serif=True)
    x,y=path[n-1]
    ship(draw,x,y-13,.62)
    words(draw,67,48,'1761 · 威廉·哈里森的试航',28,INK,'lm',True)
    words(draw,900,451,'航程方向插画',19,INK,'rm')
    if u>.37:
        circle(draw,471,266,74, PAPER, '#c3ac7d', 2)
        clock(draw,471,270,53,13,9)
        draw.arc((457,188,485,214),180,360,fill='#88633a',width=6)


def alternatives(draw, u):
    draw.line((480,88,480,420),fill='#6a8d84',width=1)
    words(draw,230,90,'在天上找时间',30,CREAM,serif=True)
    words(draw,723,90,'把时间带上船',30,CREAM,serif=True)
    circle(draw,169,205,39,'#e1d4a3')
    circle(draw,183,192,38,BLUE)
    for x,y in ((286,195),(346,139),(369,259),(108,142)):
        draw.line((x-5,y,x+5,y),fill=CREAM,width=2)
        draw.line((x,y-5,x,y+5),fill=CREAM,width=2)
    if u>.13:
        draw.line((222,329,169,205),fill='#7faaa0',width=2)
        draw.line((222,329,346,139),fill=GOLD,width=2)
        draw.arc((166,273,278,385),248,303,fill=RED,width=3)
    circle(draw,222,329,7,GOLD)
    clock(draw,721,241,97,12+u*.1,u*3)
    words(draw,230,395,'观测月亮 · 查表',24,CREAM)
    if u>.54:
        words(draw,721,395,'省去测月 · 早期昂贵',24,CREAM)


def frame_image(shot, frame, u, subtitle):
    dark = shot not in {'error', 'trial'}
    image = background(dark).copy()
    draw = ImageDraw.Draw(image)
    if shot in {'open','return'}:
        sky(draw,frame,u,ending=shot=='return')
    elif shot == 'time':
        meridians(draw,frame,u)
    elif shot == 'error':
        meridians(draw,frame,u,error=True)
    elif shot == 'trial':
        route(draw,u)
    elif shot == 'choice':
        alternatives(draw,u)
    if subtitle:
        tw=draw.textlength(subtitle,font(size=29))
        draw.rounded_rectangle((W/2-tw/2-18,476,W/2+tw/2+18,525),radius=6,fill='#13282b')
        words(draw,W/2,498,subtitle,29)
    return image


def measured_edit(out, document):
    sys.path.insert(0, str(ROOT / 'scripts'))
    from narration import effective_profile, sentence
    profile = effective_profile({'narration_profile':'config/narration-neil.json'})
    cursor, picture, speech, clips = 0, [], [], {}
    for chapter in document['chapters']:
        start = cursor
        cursor += 9
        for i, line in enumerate(chapter['narration']):
            wav, cache = clips[line] = sentence(line, profile)
            count = math.ceil(joint.pcm_frames(wav) / joint.SAMPLES_PER_FRAME)
            subtitle = chapter.get('captions', {}).get(str(i+1), line)
            speech.append(dict(id=f"{chapter['id']}-{i+1}", text=line, subtitle=subtitle,
                               knowledge_ids=chapter['knowledge_ids'], start_frame=cursor,
                               deadline_frame=cursor+count+1))
            cursor += count + 7
        cursor += 12
        picture.append(dict(id=chapter['id'],start_frame=start,end_frame=cursor))
    plan = dict(fps=30, frame_count=cursor, shots=picture, narration=speech, actions=[])
    receipt = joint.measure(plan, clips.__getitem__, out/'neil.wav')
    writejson(out/'joint-timeline.json',receipt)
    joint.receipt(plan,joint.binding(out/'joint-timeline.json'))
    return receipt


def cover(out, width, height):
    image=Image.new('RGB',(width,height),BLUE)
    draw=ImageDraw.Draw(image)
    for i in range(12):
        y=height*(.63+i*.028)
        draw.line([(x,y+7*math.sin(x/45+i*.42)) for x in range(0,width+8,8)],
                  fill='#31656a',width=3)
    circle(draw,width*.73,height*.48,width*.075,GOLD)
    ship(draw,width*.34,height*.72,width/360)
    clock(draw,width*.73,height*.72,int(width*.125),13,0)
    words(draw,width/2,height*.135,'没有地标的海上',int(width*.062),CREAM,serif=True)
    words(draw,width/2,height*.245,'一只表怎么定位？',int(width*.087),GOLD,serif=True)
    image.save(out)


def render(out, receipt, hd):
    name = 'longitude-workprint.mp4' if hd else 'longitude-animatic.mp4'
    target=out/name
    if target.exists():
        raise FileExistsError(target)
    path=target.with_suffix('.tmp.mp4')
    scale = '1920:1080' if hd else '960:540'
    command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-f','rawvideo',
             '-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate','30','-i','pipe:0',
             '-i',str(out/'neil.wav'),'-vf',f'scale={scale}:flags=lanczos:out_color_matrix=bt709,format=yuv420p',
             '-c:v','libx264','-threads','4','-preset','veryfast','-crf','19','-color_range','tv',
             '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-c:a','aac','-b:a','192k',
             '-movflags','+faststart',str(path)]
    cues=joint.cues(receipt)
    t0=time.monotonic()
    with subprocess.Popen(command,stdin=subprocess.PIPE) as encoder:
        for shot in receipt['shots']:
            a,b=shot['start_frame'],shot['end_frame']
            for frame in range(a,b):
                cue=next((row['text'] for row in cues if row['start']<=frame/30<row['end']),None)
                image=frame_image(shot['id'],frame,(frame-a)/(b-a),cue)
                encoder.stdin.write(image.tobytes())
        encoder.stdin.close()
        if encoder.wait():
            raise RuntimeError('Film encoder failed')
    path.replace(target)
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'],check=True)
    writejson(target.with_suffix('.receipt.json'),dict(media=joint.binding(target),
              timeline=joint.binding(out/'joint-timeline.json'), source=joint.binding(__file__),
              artwork_raster=[W,H], stream=probe(target), seconds=round(time.monotonic()-t0,3),
              bytes=target.stat().st_size, creative_acceptance='UNKNOWN'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out',type=Path)
    parser.add_argument('--workprint',action='store_true')
    parser.add_argument('--measured',type=Path, help='Reuse a previous verified speech edit')
    args=parser.parse_args()
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    script=Path(__file__).with_name('longitude_story_text.json')
    with lock(ROOT/'work/production.lock'):
        if args.measured:
            import shutil
            receipt=json.loads(args.measured.read_text())
            joint.receipt(receipt['plan'],joint.binding(args.measured))
            shutil.copy2(joint.bound(receipt['narration_audio']),out/'neil.wav')
            receipt['narration_audio']=joint.binding(out/'neil.wav')
            writejson(out/'joint-timeline.json',receipt)
        elif args.workprint:
            receipt=json.loads((out/'joint-timeline.json').read_text())
            joint.receipt(receipt['plan'],joint.binding(out/'joint-timeline.json'))
        else:
            receipt=measured_edit(out,json.loads(script.read_text()))
        render(out,receipt,args.workprint)
        if args.workprint:
            cover(out/'cover-3x4.jpg',780,1040)
            cover(out/'cover-4x3.jpg',1040,780)


if __name__ == '__main__':
    main()
