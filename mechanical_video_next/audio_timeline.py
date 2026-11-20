"""Measure original script with approved Neil before freezing shot durations.

Uses the existing speech cache and processing code; it never estimates speech
timings from character counts, retries uncertain paid requests or fits speech by
speed changes. The existing shared timeline is the only measured time axis.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

from scripts.common import ROOT, filehash, probe, writejson


def speech_phrases(narration):
    """Author measured-width utterances before TTS; never invent later cue cuts."""
    from .text_layout import load_style,measure_text,split_text
    style=load_style()
    capacity=style['subtitle']['safe_box'][2]-style['subtitle']['safe_box'][0]
    phrases=[];pending=''
    for text in narration:
        for part in re.split(r'(?<=[，。？！；：])',text):
            part=part.strip()
            if pending and measure_text(pending+part,style=style)['width']>capacity:
                phrases.append(pending);pending=''
            pending+=part
            if len(pending)>=8:
                phrases.extend(split_text(pending,style=style) if measure_text(pending,style=style)['width']>capacity else [pending])
                pending=''
    if pending:
        if phrases and len(pending)<8 and measure_text(phrases[-1]+pending,style=style)['width']<=capacity:
            phrases[-1]+=pending
        else:
            phrases.append(pending)
    return phrases


def prepare(task, script, env_file=None):
    sys.path.insert(0,str(ROOT/'scripts'))
    from narration import effective_profile, load_env, sentence, synthesize_shot
    from .workflow import load
    from .production_contract import NATURAL_SCIENCE, PRESENTATION_STYLE, validate_audience_copy, creative_first
    data=load(task)
    script=Path(script)
    content=json.loads(script.read_text())
    if content.get('task_id') != data['id']:
        raise ValueError('Original script must belong to this task')
    from . import joint_timeline
    if joint_timeline.enabled(data):
        if not joint_timeline.enabled(content):
            raise ValueError('The task requires a joint Blueprint timeline')
        plan = joint_timeline.validate(content['timeline'], content.get('shots'))
        for segment in plan['narration']:
            validate_audience_copy({'narration': [segment['text']]}, creative=True)
        load_env(env_file)
        profile = effective_profile({'narration_profile': 'config/narration-neil.json'})
        if profile['voice'] != 'Neil' or profile['target_speed'] != 1:
            raise ValueError('Joint timeline requires unmodified Neil speech')
        shared = Path(task) / 'shared'
        result = joint_timeline.measure(plan, lambda line: sentence(line, profile), shared / 'narration.wav')
        result['task_id'] = data['id']
        result['script'] = joint_timeline.binding(script)
        writejson(shared / 'timeline.json', result)
        return result
    chapters=content.get('chapters',[])
    if not chapters or len({c['id'] for c in chapters}) != len(chapters):
        raise ValueError('Unique original script chapters required')
    if data.get(PRESENTATION_STYLE) == NATURAL_SCIENCE:
        for chapter in chapters:
            validate_audience_copy(chapter, creative=creative_first(data))
    load_env(env_file)
    profile=effective_profile({'narration_profile':'config/narration-neil.json'})
    rows=[]; cursor=0
    for chapter in chapters:
        phrases=speech_phrases(chapter['narration'])
        durations=[]
        for text in phrases:
            clip,_=sentence(text,profile)
            durations.append(float(probe(clip)['format']['duration']))
        needed=(profile['leading_silence_seconds']+sum(durations)
                +profile['pause_between_sentences_seconds']*(len(phrases)-1)
                +profile['trailing_silence_seconds'])
        seconds=math.ceil(needed*30)/30
        audio,cues,key,hit=synthesize_shot(dict(id=chapter['id'],narration=phrases,seconds=seconds),profile)
        count=round(seconds*30)
        rows.append(dict(id=chapter['id'],start_frame=cursor,frame_count=count,seconds=seconds,
                         narration=phrases,subtitles=phrases,cues=cues,
                         audio={'path':str(audio),'sha256':filehash(audio)},
                         audio_key=key,cache_hit=hit,knowledge_ids=chapter['knowledge_ids']))
        cursor+=count
    result=dict(schema_version=1,task_id=data['id'],voice='Neil',fps=30,
                script={'path':str(script.resolve()),'sha256':filehash(script)},
                frame_count=cursor,seconds=cursor/30,shots=rows,
                timing_basis='Measured individual synthesized utterances; no character-based alignment',
                listening='UNKNOWN')
    writejson(Path(task)/'shared/timeline.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task',type=Path)
    parser.add_argument('--script',required=True,type=Path)
    parser.add_argument('--env-file',type=Path)
    args=parser.parse_args()
    report=prepare(args.task,args.script,args.env_file)
    print(json.dumps({'timeline':str(args.task/'shared/timeline.json'),'seconds':report['seconds'],'listening':'UNKNOWN'}))


if __name__=='__main__':
    main()
