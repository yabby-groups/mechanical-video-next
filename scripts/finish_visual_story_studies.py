"""Compose the silent visual previews and register their exact scene direction."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.common import ROOT, filehash, probe, writejson
from mechanical_video_next import workflow as w


OUT = ROOT/'output/visual-story-20261120'
OLD = ROOT/'output/science-creation-20261120'
SOURCE = ROOT/'blender/visual_story_studies.py'
FONT = Path('/System/Library/Fonts/Hiragino Sans GB.ttc')


def binding(path, position=None):
    item = dict(path=str(path), sha256=filehash(path))
    if position:
        item['position'] = position
    return item


def scene(identity, role, start, end, event, subject, setting, change, focus, camera,
          transition, purpose, medium, basis, carry=None):
    row = dict(id=identity, role=role, time_range=[start, end], event=event,
               subject=subject, setting=setting, change=change, focus=focus,
               camera=camera, transition=transition, purpose=purpose,
               planned_medium=medium, actual_medium=medium,
               sources=[basis, binding(SOURCE, 'Native geometry, lighting and camera source')])
    if carry:
        row['carry'] = carry
    return row


def timecode(seconds):
    return f'{int(seconds//3600)}:{int(seconds//60)%60:02d}:{seconds%60:05.2f}'


def compose(topic, cues):
    folder = OUT/'render'/topic
    clip = OUT/f'{topic}-visual-preview.mp4'
    if clip.exists():
        return clip
    if not (folder/'render-receipt.json').is_file():
        raise ValueError(f'Render still incomplete: {topic}')
    temporary = clip.with_suffix('.tmp.mp4')
    ass = OUT/f'{topic}.ass'
    lines = [
        '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 640', 'PlayResY: 360',
        '[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        'Style: Default,Hiragino Sans GB,21,&H00F1FAFF,&H000000FF,&H00141616,&H00000000,0,0,0,0,100,100,0,0,1,1.6,0,2,20,20,22,1',
        '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    ]
    lines += [f'Dialogue: 0,{timecode(a)},{timecode(b)},Default,,0,0,0,,{words}' for a,b,words in cues]
    ass.write_text('\n'.join(lines)+'\n')
    command = ['ffmpeg','-hide_banner','-nostdin','-v','error','-y','-framerate','12',
               '-i',str(folder/'%04d.jpg'),'-vf',
               f"scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p,subtitles='{ass}':fontsdir='{FONT.parent}',fps=24",
               '-an','-c:v','libx264','-crf','18','-preset','fast','-color_range','tv',
               '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
               '-movflags','+faststart',str(temporary)]
    subprocess.run(command, check=True)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(temporary),'-f','null','-'], check=True)
    temporary.replace(clip)
    return clip


def register(topic, original, baseline, scenes, cues):
    clip=compose(topic, cues)
    previous = ROOT/'output/tasks'/original
    old = w.load(previous)
    research = w.artifact(previous, 'research')
    slug = original+'-picture'
    task = ROOT/'output/tasks'/slug
    if not task.is_dir():
        w.create_task(old['topic'], task_id=slug, visual_policy_version=2, media_policy_version=1)
        w.advance(task, 'RESEARCHING')
        w.put_handoff(task, 'Research','research',research)
    plan = OUT/f'{topic}-scene-direction.json'
    if 'diagnostic-animatic' not in w.load(task)['handoffs']:
        writejson(plan, dict(story_id=research['story_exploration']['selected_id'],
                             baseline=binding(baseline), scenes=scenes))
        w.put_handoff(task, 'Producer', 'diagnostic-animatic',
                      dict(status='DRAFT_UNAPPROVED', media=[binding(clip)], blueprint_evidence=binding(plan)),
                      ['research'])
    render_log = OUT/'render'/topic/'render-receipt.json'
    writejson(OUT/f'{topic}-preview-receipt.json', {
        'media': binding(clip), 'scene_direction': binding(plan), 'baseline': binding(baseline),
        'render': binding(render_log), 'timed_labels': binding(OUT/f'{topic}.ass'),
        'encoded': probe(clip), 'audio': 'Deliberate silence in the pre-voice picture edit',
        'formal_review': 'UNKNOWN',
    })
    print(clip)


def nautical():
    history = binding(OLD/'sources/h4.html', 'Harrison marine timekeeper H4 and the 1761 Jamaica trial; earlier Madeira landfall')
    time = binding(OLD/'sources/longitude.html', 'Determining longitude; simultaneous place times and Earth rotation')
    reconstruction = 'Blender period-inspired 3D reconstruction'
    scenes = [
        scene('on-deck','story',0,5,'在航行中读表','18 世纪船员和航海表','风帆、桅杆和图桌所在的甲板',
              '船员把表从桌边举起','手和表','移近图桌','由甲板推向手部','建立海上如何定位的问题',reconstruction,history),
        scene('watch','story',5,9,'保留岸上参照时间','手中的银壳计时表','同一图桌和船员衣袖',
              '手腕把读数面转向观察者','表盘','俯视近景轻移','切近手部','让观众看到要读取的实物',reconstruction,history),
        scene('meridians','explanation',9,13.5,'在同一瞬间比较两地太阳时','两条相差 15° 的经线','有界的三维地球示意',
              '观察角度移动并区别两条经线','两地标记和同一时刻的解释','短弧绕行','从圆表盘切到地球',
              '把港口时读数与空间位置联系起来','Blender 3D explanation',time,'表盘的读数进入同一时刻的两地示例'),
        scene('landfall','story',13.5,18,'接近岛岸','桅索、舷边和远方岛岸','归纳重建的开阔海面',
              '机位从舷边滑向岛屿方向','地平线上的陆地','近甲板水平移动','从经线回到航路终点',
              '呈现计时推算给航行带来的结果',reconstruction,history,'地球经度推算回到真实航程结果'),
    ]
    register('nautical','longitude-at-sea-v4',OLD/'longitude-v2/longitude-workprint.mp4',scenes,[
        (0,2.5,'{\\an7\\pos(18,18)}1761  大西洋 · 情境重建'),
        (6.05,8.7,'把港口的时间带上船'),
        (9.25,13.5,'船上正午 · 港口下午一点'),
        (9.25,13.5,'{\\an7\\pos(18,18)}同一时刻 · 按太阳时'),
        (13.5,17.9,'更早到达马德拉，威廉事先算到了'),
    ])


def optics():
    optics_source = binding(OLD/'sources/open.html','OpenStax 1.4 Refraction, water index and Snell law')
    apparent = binding(OLD/'sources/fish.html','Refraction and Sight; rays and apparent object position')
    observation = 'Cycles 3D optical reconstruction'
    scenes = [
        scene('dry','story',0,2.15,'从低视角观察容器','空容器的前缘','光学实验台',
              '固定视角建立遮挡，短暂停留对照下一状态','杯沿','锁定眼点','保留同一机位',
              '让观众确认初始遮挡',observation,optics_source),
        scene('fill','story',2.15,7.1,'水面上升后硬币出现','同一杯沿、水面和硬币','同一实验台',
              '注水提高液面，硬币从杯沿后出现','显现的金色区域','同一眼点','硬币显现后短暂停留',
              '画面直接给出反直觉结果',observation,optics_source),
        scene('ray','explanation',7.1,12.6,'顺同一杯沿查看折射路径','截面、硬币、水面和眼点','实验台侧剖',
              '实际折线路径先出现，随后补出反向延长方向','光线经过水面并越过杯沿','侧视近正交','从可见硬币切到同一实体的剖面',
              '展示同一眼点为什么在湿态能收到光','Blender 3D optical section',apparent,'保留相同水位、眼点、硬币与遮挡杯沿'),
        scene('drain','story',12.6,17,'水位下降，硬币重新被挡住','同一容器和硬币','同一实验台',
              '液面降低后硬币消失','杯沿遮住的区域','返回原眼点','切回与开头严格同机位',
              '用可见回退检验原因',observation,optics_source,'用相同杯沿在原眼点复现干态'),
    ]
    register('optics','coin-apparent-depth-v4',OLD/'optics/v2/draft.mp4',scenes,[
        (0,2.1,'{\\an7\\pos(18,18)}固定机位 · 光学重建'),
        (7.35,9.38,'光越过杯沿，进入眼睛'),
        (9.6,12.5,'沿空气里的方向回看'),
    ])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    studies={'nautical':nautical,'optics':optics}
    parser.add_argument('--topic',choices=tuple(studies),action='append')
    for topic in parser.parse_args().topic or studies:
        studies[topic]()
