"""Compose the story preview with the existing measured Neil and FFmpeg tools."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from mechanical_video_next import joint_timeline as joint
from scripts.common import ROOT, writejson

sys.path.insert(0, str(ROOT / 'scripts'))
import narration

HERE = Path(__file__).resolve().parent
CAPTION_FORMAT = """[Script Info]
ScriptType: v4.00+
PlayResX: 768
PlayResY: 432
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Sub,Heiti SC,25,&H00FFFFFF,&H00FFFFFF,&H00191D22,&H89191D22,1,0,0,0,100,100,0,0,3,5,0,2,22,22,19,1
Style: Label,Heiti SC,19,&H00E5F1F5,&H00FFFFFF,&H00191D22,&H90191D22,1,0,0,0,100,100,0,0,3,5,0,7,24,24,20,1
Style: Title,Heiti SC,35,&H00E5F1F5,&H00FFFFFF,&H00191D22,&H90191D22,1,0,0,0,100,100,0,0,3,5,0,7,24,24,20,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def ass_time(seconds):
    minutes, remainder = divmod(round(seconds * 100), 6000)
    return f'0:{minutes:02}:{remainder // 100:02}.{remainder % 100:02}'


def cue(start, end, style, text):
    return f'Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}\n'


def build_clock(edit):
    shots, speech = [], []
    start = 0
    for shot in edit['shots']:
        stop = start + round(shot['seconds'] * 30)
        shots.append(dict(id=shot['id'], start_frame=start, end_frame=stop))
        lines = [(start + round(seconds * 30), line) for seconds, line in shot['narration']]
        for index, (first, line) in enumerate(lines):
            deadline = lines[index + 1][0] if index + 1 < len(lines) else stop
            speech.append(dict(id=f"{shot['id']}-{index + 1}", start_frame=first,
                               deadline_frame=deadline, text=line,
                               knowledge_ids=shot['knowledge_ids']))
        start = stop
    return {'frame_count': start, 'shots': shots, 'narration': speech, 'actions': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output, frames = args.output.resolve(), args.frames.resolve()
    output.mkdir(parents=True, exist_ok=True)
    edit = json.loads((HERE / 'edit.json').read_text())
    plan = build_clock(edit)
    if len(list(frames.glob('frame-*.jpg'))) != plan['frame_count']:
        raise ValueError('Render frame count differs from the complete picture clock')
    profile = narration.load_profile(ROOT / 'config/narration-neil.json')
    audio = output / 'neil.wav'
    measured = joint.measure(plan, lambda line: narration.sentence(line, profile), audio)
    measured_path = output / 'measured-neil.json'
    writejson(measured_path, measured)
    measured_binding = joint.binding(measured_path)
    joint.receipt(plan, measured_binding)
    writejson(output / 'preview-blueprint.json',
              dict(title=edit['title'], timeline=plan, measured_timeline=measured_binding))
    captions = CAPTION_FORMAT + cue(0.25, 2.75, 'Title', edit['title'])
    for shot, span in zip(edit['shots'], plan['shots']):
        if shot.get('label'):
            captions += cue(span['start_frame'] / 30 + 0.2, span['end_frame'] / 30,
                            'Label', shot['label'])
    for row in measured['speech']:
        captions += cue(row['start_sample'] / joint.SAMPLE_RATE, row['end_sample'] / joint.SAMPLE_RATE,
                        'Sub', row['subtitle'])
    (output / 'captions.ass').write_text(captions)
    film = output / 'door-lock-story-preview.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'warning', '-y',
                    '-framerate', '30', '-start_number', '1', '-i', str(frames / 'frame-%04d.jpg'),
                    '-i', str(audio), '-vf', 'subtitles=captions.ass', '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(film)],
                   cwd=output, check=True)
    joint.validate_rendered_film(film, plan, require_audio=True)
    audio_result = joint.validate_rendered_audio(film, plan, measured)
    writejson(output / 'technical-review.json', {
        'media': joint.binding(film), 'edit': joint.binding(HERE / 'edit.json'),
        'scene_source': joint.binding(HERE / 'scene.py'), 'picture_frames': plan['frame_count'],
        'audio_check': audio_result, 'creative_acceptance': 'INDEPENDENT_REVIEW_REQUIRED',
    })


if __name__ == '__main__':
    main()
