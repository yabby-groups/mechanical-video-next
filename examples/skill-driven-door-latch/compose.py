"""Compose the authored door-latch story at its measured Neil and picture clocks."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from mechanical_video_next import joint_timeline as joint
from scripts.common import ROOT, filehash, writejson

HERE = Path(__file__).resolve().parent
sys.path.append(str(ROOT / 'scripts'))
import narration


def ass_time(frame):
    centiseconds = round(frame * 100 / 30)
    minutes, remainder = divmod(centiseconds, 6000)
    seconds, hundredths = divmod(remainder, 100)
    return f'0:{minutes:02}:{seconds:02}.{hundredths:02}'


def captions(story, measured):
    rows = [
        '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 768', 'PlayResY: 432', 'WrapStyle: 2',
        '[V4+ Styles]',
        'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,'
        'Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,'
        'Alignment,MarginL,MarginR,MarginV,Encoding',
        'Style: Sub,Heiti SC,28,&H00FFFFFF,&H00FFFFFF,&H001A2021,&H7C172021,'
        '1,0,0,0,100,100,0,0,3,7,0,2,28,28,22,1',
        'Style: Label,Heiti SC,20,&H00EFF6FA,&H00FFFFFF,&H00243545,&H97243545,'
        '1,0,0,0,100,100,0,0,3,5,0,7,28,28,22,1',
        'Style: Title,Heiti SC,43,&H00E8F3FF,&H00FFFFFF,&H00283D45,&H7C283D45,'
        '1,0,0,0,100,100,0,0,3,8,0,7,28,28,26,1',
        'Style: Arrow,Heiti SC,27,&H0077D9FF,&H00FFFFFF,&H00182635,&H62182635,'
        '1,0,0,0,100,100,0,0,1,2,0,7,28,28,22,1',
        '[Events]', 'Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text',
    ]

    def add(start, end, style, text):
        rows.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}')

    add(5, 105, 'Title', '门合上以后')
    add(105, 210, 'Label', '情境重建')
    add(330, 960, 'Label', r'{\an9\pos(738,24)}运动原理示意')
    for shot in story['shots']:
        if shot['label'] and shot['start'] >= 330:
            add(shot['start'] + 4, shot['end'], 'Label', shot['label'])
    add(369, 513, 'Arrow', r'{\pos(142,151)}↑')
    add(613, 724, 'Arrow', r'{\pos(142,151)}↓')
    for cue in measured['speech']:
        add(cue['start_sample'] / joint.SAMPLES_PER_FRAME,
            cue['end_sample'] / joint.SAMPLES_PER_FRAME, 'Sub', cue['subtitle'])
    return '\n'.join(rows) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.frames = args.frames.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    story = json.loads((HERE / 'story.json').read_text())
    plan = {
        'frame_count': story['shots'][-1]['end'],
        'shots': [dict(id=row['id'], start_frame=row['start'], end_frame=row['end'])
                  for row in story['shots']],
        'narration': story['narration'],
        'actions': [],
    }
    (args.output / 'edit-clock.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    if len(list(args.frames.glob('frame-*.jpg'))) != plan['frame_count']:
        raise ValueError('Blender frames differ from the picture clock')
    profile = narration.load_profile(ROOT / 'config/narration-neil.json')
    audio_path = args.output / 'neil.wav'
    measured = joint.measure(plan, lambda line: narration.sentence(line, profile), audio_path)
    measured_path = args.output / 'measured-neil.json'
    writejson(measured_path, measured)
    joint.receipt(plan, joint.binding(measured_path))
    motion_path = args.output / 'kinematics.json'
    shutil.copy2(args.frames / 'kinematics.json', motion_path)
    writejson(args.output / 'preview-blueprint.json', dict(
        title=story['title'], narrative=dict(question=story['question'], answer=story['answer'],
                                            observations=story['observations']),
        chapters=story['chapters'], timeline=plan, measured_timeline=joint.binding(measured_path),
    ))
    (args.output / 'captions.ass').write_text(captions(story, measured))
    film = args.output / 'door-latch-story-preview.mp4'
    command = [
        'ffmpeg', '-hide_banner', '-v', 'warning', '-y', '-framerate', '30', '-start_number', '1',
        '-i', str(args.frames / 'frame-%04d.jpg'), '-i', str(audio_path),
        '-vf', 'subtitles=captions.ass', '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(film),
    ]
    with (args.output / 'compose.log').open('w') as log:
        subprocess.run(command, cwd=args.output, stdout=log, stderr=subprocess.STDOUT, check=True)
    render_check = joint.validate_rendered_film(film, plan)
    audio_check = joint.validate_rendered_audio(film, plan, measured)
    writejson(args.output / 'technical-review.json', dict(
        media=joint.binding(film), picture=render_check, audio=audio_check,
        kinematics=joint.binding(motion_path),
        story=joint.binding(HERE / 'story.json'), scene=joint.binding(HERE / 'scene.py'),
        compose_sha256=filehash(__file__), ffmpeg=command, listening='UNKNOWN',
    ))
    print(film)


if __name__ == '__main__':
    main()
