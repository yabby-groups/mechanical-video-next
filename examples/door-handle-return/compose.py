"""Compose the complete low-cost preview with the existing measured Neil pipeline."""
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
HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 768
PlayResY: 432
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Title,Heiti SC,30,&H00E5F7FF,&H00FFFFFF,&H00132125,&H7A132125,1,0,0,0,100,100,0,0,3,6,0,7,24,24,20,1
Style: Sub,Heiti SC,25,&H00FFFFFF,&H00FFFFFF,&H00132125,&H9A132125,1,0,0,0,100,100,0,0,3,5,0,2,22,22,19,1
Style: Label,Heiti SC,18,&H00E5F7FF,&H00FFFFFF,&H00132125,&H9A132125,1,0,0,0,100,100,0,0,3,4,0,7,24,24,20,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def timestamp(seconds):
    mins, rest = divmod(round(seconds * 100), 6000)
    return f'0:{mins:02}:{rest // 100:02}.{rest % 100:02}'


def cue(start, end, style, text):
    return f'Dialogue: 0,{timestamp(start)},{timestamp(end)},{style},,0,0,0,,{text}\n'


def plan_for(edit):
    picture, speech = [], []
    for shot in edit['shots']:
        start, end = round(shot['start'] * joint.FPS), round(shot['end'] * joint.FPS)
        picture.append(dict(id=shot['id'], start_frame=start, end_frame=end))
        lines = shot['narration']
        for index, (offset, words, fact) in enumerate(lines):
            stop = start + round(lines[index + 1][0] * joint.FPS) if index + 1 < len(lines) else end
            speech.append(dict(id=f"{shot['id']}-{index+1}", text=words, knowledge_ids=[fact],
                               start_frame=start + round(offset * joint.FPS), deadline_frame=stop))
    return dict(frame_count=picture[-1]['end_frame'], shots=picture, narration=speech, actions=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    edit = json.loads((HERE/'edit.json').read_text())
    plan = plan_for(edit)
    profile = narration.load_profile(ROOT/'config/narration-neil.json')
    audio = folder/'neil.wav'
    measured = joint.measure(plan, lambda line: narration.sentence(line, profile), audio)
    measured_path = folder/'measured-neil.json'
    writejson(measured_path, measured)
    measured_ref = joint.binding(measured_path)
    joint.receipt(plan, measured_ref)
    captions = HEADER + cue(.15, 3.2, 'Title', edit['title'])
    for shot in edit['shots']:
        if 'label' in shot:
            captions += cue(shot['start'], shot['end'], 'Label', shot['label'])
    for row in measured['speech']:
        captions += cue(row['start_sample']/joint.SAMPLE_RATE, row['end_sample']/joint.SAMPLE_RATE,
                        'Sub', row['subtitle'])
    (folder/'captions.ass').write_text(captions)
    source = joint.binding(folder/'door-handle-return.blend')
    writejson(folder/'preview-blueprint.json', dict(
        title=edit['title'], timeline=plan, measured_timeline=measured_ref,
        core_3d=[dict(scene_id=scene, shot_id=shot, source=source)
                 for scene, shot in [('assembly','explode'), ('return-cycle','load'), ('return-cycle','release')]]))
    film = folder/'door-handle-return-preview.mp4'
    if len(list((folder/'frames').glob('frame-*.jpg'))) != plan['frame_count']:
        raise ValueError('Blender frames differ from the complete edit clock')
    subprocess.run(['ffmpeg','-v','warning','-y','-framerate','30','-start_number','1',
                    '-i','frames/frame-%04d.jpg','-i',str(audio),'-vf','subtitles=captions.ass',
                    '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
                    '-c:a','aac','-b:a','160k','-movflags','+faststart',str(film)],
                   cwd=folder, check=True)
    joint.validate_rendered_film(film, plan, require_audio=True)
    writejson(folder/'technical-review.json', dict(
        media=joint.binding(film), native_scene=source, motion=joint.binding(folder/'motion.json'),
        scene_source=joint.binding(HERE/'scene.py'), edit=joint.binding(HERE/'edit.json'),
        picture_frames=plan['frame_count'], audio=joint.validate_rendered_audio(film,plan,measured),
        audience_acceptance='UNKNOWN'))


if __name__ == '__main__':
    main()
