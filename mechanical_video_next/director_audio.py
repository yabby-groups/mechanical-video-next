"""Place owned or licensed effects at authored action and edit points."""
from array import array
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
import wave

from . import joint_timeline as joint
from .audio_acceptance import verify_mix
from .media_policy import bound, validate_rights


def sound_stems(plan, events):
    """Resolve frame-local triggers to the existing sample-based mix schema."""
    if not isinstance(events, list):
        raise ValueError('Sound events must be a list')
    action_index = {item['id']: item for item in plan['actions']}
    cuts = {item['id']: item for item in plan['shots']}
    stems = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Sound event must be an object')
        anchor = ('action_id' in event, 'shot_id' in event)
        if anchor == (True, False):
            row = action_index.get(event['action_id'])
        elif anchor == (False, True):
            row = cuts.get(event['shot_id'])
        else:
            row = None
        offset, duration, lead = (event.get('offset_frames', 0), event.get('duration_frames'),
                                  event.get('lead_frames', 0))
        gain = event.get('gain_db')
        source_offset = event.get('source_start_sample', 0)
        if (not row or not all(type(value) is int and value >= 0
                               for value in (offset, duration, lead, source_offset)) or duration == 0
                or type(gain) not in (int, float) or not math.isfinite(gain) or not -80 <= gain <= 0
                or not isinstance(event.get('purpose'), str) or not event['purpose'].strip()):
            raise ValueError('Sound event needs one valid anchor, bounded timing, attenuation and purpose')
        trigger = row['start_frame'] + offset
        start, end = trigger - lead, trigger - lead + duration
        if not 0 <= start <= trigger < row['end_frame'] or end > plan['frame_count']:
            raise ValueError('Sound event is outside its trigger or film')
        validate_rights(event)
        left, right = start * joint.SAMPLES_PER_FRAME, end * joint.SAMPLES_PER_FRAME
        if source_offset + right - left > joint.pcm_frames(bound(event['source'])):
            raise ValueError('Sound event exceeds its bound PCM source')
        stems.append(dict(event, kind='sfx', start_sample=left, end_sample=right,
                          source_start_sample=source_offset))
    return stems


def mix(plan, events, narration, output):
    stems = sound_stems(plan, events)
    if not stems:
        return None
    expected = plan['frame_count'] * joint.SAMPLES_PER_FRAME
    if joint.pcm_frames(narration) != expected:
        raise ValueError('Director mix needs the complete measured Neil track')
    with wave.open(str(narration), 'rb') as wav:
        samples = array('h', wav.readframes(expected))
    mixed = array('d', samples)
    for row in stems:
        gain = 10 ** (row['gain_db'] / 20)
        with wave.open(str(bound(row['source'])), 'rb') as effect:
            effect.setpos(row['source_start_sample'])
            left, right = row['start_sample'], row['end_sample']
            for index, sample in enumerate(array('h', effect.readframes(right - left)), left):
                mixed[index] += gain * sample
    if any(abs(sample) >= 32767 for sample in mixed):
        raise ValueError('Director effects would clip the audio')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, prefix='.director-mix-', suffix='.wav', delete=False) as file:
        temporary = Path(file.name)
    try:
        with wave.open(str(temporary), 'wb') as wav:
            wav.setparams((1, 2, joint.SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            wav.writeframes(array('h', map(round, mixed)).tobytes())
        receipt = dict(master=joint.binding(temporary), stems=stems)
        verify_mix(receipt, narration, expected)
        temporary.replace(output)
        return dict(receipt, master=joint.binding(output))
    finally:
        temporary.unlink(missing_ok=True)
