"""Compile story-level voice direction against an existing joint picture clock."""
import math
import re

from . import joint_timeline as joint

EMOTIONS = (
    'neutral', 'curious', 'suspense', 'excited', 'surprised',
    'confident', 'explanatory', 'satisfying', 'reflective',
)
ENGINES = ('neil', 'cosyvoice3')
DELIVERY = {
    'neutral': '像面对面讲解一样自然陈述',
    'curious': '像刚注意到一个日常现象，带着自然的好奇问下去，句尾留一点疑问',
    'suspense': '顺着画面引观众看向结构，语气稍收，在展示处留一点观察空间',
    'excited': '遇到发现时稍提精神，随后回到平常的讲解语气',
    'surprised': '发现反常处时带一点意外，接着平稳讲下去',
    'confident': '平稳交代过程，在关键动作上稍微咬清字音',
    'explanatory': '清楚平稳地讲因果，短语之间自然衔接',
    'satisfying': '说到答案时语气稍舒展，像顺着动作一下子明白了',
    'reflective': '简短回扣开头，语气自然落下',
}


def require_engine(engine):
    if engine in ENGINES:
        return engine
    if isinstance(engine, str) and re.fullmatch(r'index[-_ ]?tts(?:[-_ ]?2\.?5)?', engine, re.I):
        raise ValueError('IndexTTS 2.5 is no longer supported. Select cosyvoice3 or neil.')
    raise ValueError(f'Unsupported voice engine: {engine}. Select cosyvoice3 or neil.')


def finite(value, low, high):
    return type(value) in (float, int) and math.isfinite(value) and low <= value <= high


def milliseconds(frames):
    return frames * 1000 // joint.FPS


def plan_direction(plan, beats, profile, engine, *, script_feedback=()):
    """Use authored story beats and knowledge terms. Constrain them to approved slots."""
    require_engine(engine)
    joint.validate(plan)
    speech = {row['id']: row for row in plan['narration']}
    order = []
    segments = []
    for beat in beats:
        for entry in beat['segments']:
            emotion = entry.get('emotion', beat.get('emotion', profile['default_emotion']))
            if emotion not in EMOTIONS:
                raise ValueError('Unknown director emotion: ' + str(emotion))
            spec = speech[entry['segment_id']]
            order.append(spec['id'])
            text = spec['text']
            start, deadline = spec['start_frame'], spec['deadline_frame']
            scene = next(shot['id'] for shot in plan['shots'] if shot['start_frame'] <= start < shot['end_frame'])
            emphasis = dict.fromkeys([*entry.get('emphasis_words', []), *(
                term for knowledge_id in spec['knowledge_ids']
                for term in profile.get('knowledge_terms', {}).get(knowledge_id, []) if term in text
            )])
            emphasis = list(emphasis)[:profile['max_emphasis_words']]
            before = entry.get('pause_before_ms', beat.get('pause_before_ms', profile['pause_before_ms']))
            after = entry.get('pause_after_ms', beat.get('pause_after_ms', profile['pause_after_ms']))
            result = dict(
                segment_id=spec['id'], text=text, story_purpose=beat['story_purpose'], emotion=emotion,
                emotion_intensity=entry.get('emotion_intensity', beat.get('emotion_intensity',
                                            profile['emotion_intensity_range'][0])),
                delivery_style=entry.get('delivery_style', beat.get('delivery_style', DELIVERY[emotion])),
                speaking_rate=entry.get('speaking_rate', beat.get('speaking_rate', profile['base_speaking_rate'])),
                emphasis_words=emphasis, pause_before_ms=before, pause_after_ms=after,
                target_duration_ms=entry.get('target_duration_ms', milliseconds(deadline - start) - before - after),
                scene_id=scene, voice_id=profile['id'], selected_tts=engine,
                review_required=entry.get('review_required', engine != 'neil'),
            )
            for field in ('action_anchors', 'pronunciations', 'take'):
                if field in entry:
                    result[field] = entry[field]
            segments.append(result)
    if order != list(speech):
        raise ValueError('Story beats must cover every narration slot exactly once and in order')
    direction = dict(schema_version=1, script_feedback=list(script_feedback), segments=segments)
    validate(direction, plan, profile)
    return direction


def validate(direction, plan, profile):
    joint.validate(plan)
    rows = direction['segments']
    if type(direction.get('schema_version')) is not int or direction['schema_version'] != 1:
        raise ValueError('Unsupported voice direction version')
    if not isinstance(rows, list) or not rows or len(rows) != len(plan['narration']):
        raise ValueError('Voice direction must cover the approved narration')
    if not isinstance(direction.get('script_feedback'), list) or any(
        not isinstance(item, str) or not item.strip() for item in direction['script_feedback']
    ):
        raise ValueError('Script feedback must be a list of notes')
    actions = {action['id']: action for action in plan['actions']}
    for row in rows:
        require_engine(row['selected_tts'])
    selected_engine = rows[0]['selected_tts']
    if selected_engine not in profile['engines']:
        raise ValueError('Select an engine in the voice profile')
    for row, spec in zip(rows, plan['narration'], strict=True):
        start, deadline = spec['start_frame'], spec['deadline_frame']
        scene = next(shot['id'] for shot in plan['shots'] if shot['start_frame'] <= start < shot['end_frame'])
        if (row['segment_id'] != spec['id'] or row['text'] != spec['text'] or row['scene_id'] != scene
                or row['voice_id'] != profile['id'] or row['selected_tts'] != selected_engine):
            raise ValueError('Voice direction differs from the joint script, scene or voice profile: ' + spec['id'])
        if (row['emotion'] not in EMOTIONS
                or not finite(row['emotion_intensity'], *profile['emotion_intensity_range'])
                or not finite(row['speaking_rate'], .8, 1.2)
                or type(row['review_required']) is not bool
                or any(not isinstance(row[k], str) or not row[k].strip() for k in ('story_purpose', 'delivery_style'))):
            raise ValueError('Invalid delivery controls: ' + spec['id'])
        times = [row[k] for k in ('pause_before_ms', 'pause_after_ms', 'target_duration_ms')]
        if (any(type(t) is not int or t < 0 for t in times) or not times[2]
                or sum(times) > milliseconds(deadline - start)):
            raise ValueError('Voice duration and pauses exceed joint slot: ' + spec['id'])
        emphasis = row['emphasis_words']
        if (not isinstance(emphasis, list) or len(emphasis) > profile['max_emphasis_words']
                or any(not isinstance(word, str) or not word or word not in row['text'] for word in emphasis)
                or len(set(emphasis)) != len(emphasis)):
            raise ValueError('Emphasis terms must appear verbatim in the narration: ' + spec['id'])
        for term, pinyin in row.get('pronunciations', {}).items():
            if len(term) != 1 or term not in row['text'] or not re.fullmatch(r'[A-ZÜV]+[1-5]', pinyin):
                raise ValueError('Use a literal Chinese character and uppercase numbered pinyin: ' + spec['id'])
        for anchor in row.get('action_anchors', []):
            action = actions.get(anchor['action_id'])
            frame, phrase = anchor['frame'], anchor['phrase']
            occurrence, tolerance = anchor.get('occurrence', 1), anchor.get('tolerance_ms', 300)
            if (not action or type(frame) is not int or not action['start_frame'] <= frame < action['end_frame']
                    or not start <= frame < deadline or not isinstance(phrase, str) or not phrase
                    or type(occurrence) is not int or not 1 <= occurrence <= row['text'].count(phrase)
                    or type(tolerance) is not int or not 0 <= tolerance <= 1500):
                raise ValueError('Action anchor needs a spoken phrase and a frame inside both clocks: ' + spec['id'])
        if 'take' in row and (not isinstance(row['take'], str) or not row['take'].strip()):
            raise ValueError('Take must be a non-empty string: ' + spec['id'])
    return direction


def review_cues(direction):
    cues = []
    high = sum(row['emotion'] in ('excited', 'surprised') and row['emotion_intensity'] >= .5
               for row in direction['segments'])
    if high > max(1, len(direction['segments']) // 5):
        cues.append('惊讶或兴奋密度偏高，复核剧情是否有足够的发现或转折。')
    for left, right in zip(direction['segments'], direction['segments'][1:]):
        if abs(left['speaking_rate'] - right['speaking_rate']) > .12:
            cues.append(f'{left["segment_id"]} → {right["segment_id"]} 的导演语速变化超过 0.12×。')
    return cues
