"""Build and measure the sample-clock music gain used by the existing mixer."""
from bisect import bisect_right
import math

from .audio_acceptance import MIN_MIX_MARGIN_DB, WINDOW, process_mix
from .joint_timeline import SAMPLE_RATE

VERSION = 2
DEFAULT = {
    'version': VERSION,
    'target_margin_db': 15,
    'minimum_duck_db': 4,
    'soft_limit_db': 8,
    'attack_seconds': .20,
    'hold_seconds': .32,
    'release_seconds': .60,
    'guard_margin_db': MIN_MIX_MARGIN_DB + .5,
    'guard_attack_seconds': .16,
    'guard_release_seconds': .30,
    'analysis_samples': WINDOW,
}


def amplitude(db):
    return 10 ** (db / 20)


def measurements(stems, narration, expected):
    rows = []
    process_mix(stems, narration, expected, check_masking=False,
                observe=lambda *values: rows.append(values))
    return rows


def ramp(point, left, right, attack, release):
    if left <= point <= right:
        return 1.
    return max(0., 1 - (left - point) / attack if point < left else 1 - (point - right) / release)


def interpolate(points, sample):
    index = min(len(points) - 2, bisect_right(points, sample, key=lambda row: row[0]) - 1)
    left, a = points[index]
    right, b = points[index + 1]
    return a + (b - a) * (sample - left) / (right - left)


def apply(stems, effects, narration, expected, speech, settings=DEFAULT, *, light_db=None):
    """Share one continuous voice envelope across score cuts and loop crossfades."""
    if not speech or not stems:
        return stems
    rows = measurements(stems + effects, narration, expected) if light_db is None else []
    voice_ranges = sorted((row['start_sample'], row['end_sample']) for row in speech)
    attack, hold, release = (round(settings[key] * SAMPLE_RATE) for key in
                             ('attack_seconds', 'hold_seconds', 'release_seconds'))
    guard_attack, guard_release = (round(settings[key] * SAMPLE_RATE) for key in
                                   ('guard_attack_seconds', 'guard_release_seconds'))
    soft, guard = [], []
    for left, right in voice_ranges:
        # Bridge short gaps, including pauses between adjacent narration segments.
        if soft and left <= soft[-1][1]:
            soft[-1] = (soft[-1][0], right + hold)
        else:
            soft.append((left, right + hold))
    demands = []
    for index, (left, right, voice, music, _, _, _) in enumerate(rows):
        if not music or not any(left < stop and right > start for start, stop in voice_ranges):
            continue
        nearby = rows[max(0, index - 2):index + 3]
        voice_level = max(row[2] / (row[1] - row[0]) for row in nearby)
        if voice_level > (32768 * .01) ** 2:
            ratio = 10 * math.log10(music / (right - left) / voice_level)
            extra = min(settings['soft_limit_db'], ratio + settings['target_margin_db'])
            if extra > settings['minimum_duck_db']:
                demands.append((left, right + hold, extra))
    for left, right, voice, _, music_norm, effects_norm, _ in rows:
        if voice <= (right - left) * (32768 * .01) ** 2 or not music_norm:
            continue
        budget = math.sqrt(voice) / amplitude(settings['guard_margin_db']) - effects_norm
        cap = min(1., max(amplitude(-65), budget / music_norm))
        if cap < 1:
            guard.append((left, right, -20 * math.log10(cap)))

    # Store the effective amplitude, including music fades, with its sample index.
    # Knots include guard boundaries and a 20 ms grid to retain smooth transitions.
    base_db = settings['minimum_duck_db'] if light_db is None else light_db
    windows = [(left, right, base_db, attack, release) for left, right in soft]
    windows += [(left, right, value, attack, release) for left, right, value in demands]
    windows += [(left, right, value, guard_attack, guard_release) for left, right, value in guard]
    windows.sort(key=lambda item: item[0] - item[3])
    knots = set(range(0, expected, SAMPLE_RATE // 50))
    knots.update(point for left, right, _, advance, decay in windows
                 for point in (left - advance, left, right, right + decay) if 0 <= point < expected)
    for row in stems:
        knots.update(point for point, _ in row['envelope'])
    gains, active, cursor = {}, [], 0
    for point in sorted(knots):
        active = [item for item in active if item[1] + item[4] >= point]
        while cursor < len(windows) and windows[cursor][0] - windows[cursor][3] <= point:
            active.append(windows[cursor])
            cursor += 1
        reduction = max((value * ramp(point, left, right, advance, decay)
                         for left, right, value, advance, decay in active), default=0.)
        gains[point] = amplitude(-reduction)
    result = []
    ordered = sorted(gains)
    for row in stems:
        left, last = row['start_sample'], row['end_sample'] - 1
        dry = row['envelope']
        first_index = bisect_right(ordered, left - 1)
        end_index = bisect_right(ordered, last)
        envelope = [[point, round(interpolate(dry, point) * gains[point], 10)]
                    for point in ordered[first_index:end_index]]
        result.append(dict(row, envelope=envelope))
    return result


def describe(dry, wet, speech):
    """Report active speech margin and source-aware music continuity, in 100 ms windows."""
    def db(power, length):
        return round(10 * math.log10(power / length / 32768**2), 3) if power else None
    results = []
    for before, after in zip(dry, wet, strict=True):
        left, right, voice, music, *rest = after
        source_music = before[3]
        within = any(left < row['end_sample'] and right > row['start_sample'] for row in speech)
        length = right - left
        results.append(dict(start_sample=left, end_sample=right, speech=within,
                            active_speech=voice > length * (32768 * .01) ** 2,
                            neil_rms_dbfs=db(voice, length), bgm_dry_rms_dbfs=db(source_music, length),
                            bgm_rms_dbfs=db(music, length),
                            neil_to_bgm_db=round(10 * math.log10(voice / music), 2) if voice and music else None,
                            neil_to_background_db=round(10 * math.log10(voice / after[6]), 2)
                            if voice and after[6] else None,
                            applied_reduction_db=round(10 * math.log10(source_music / music), 2)
                            if source_music and music else None))
    return results


def review_metrics(windows):
    from statistics import median

    active = [row for row in windows if row['active_speech']]
    margins = [row['neil_to_background_db'] for row in active if row['neil_to_background_db'] is not None]
    music_margins = [row['neil_to_bgm_db'] for row in active if row['neil_to_bgm_db'] is not None]
    covered = [row for row in windows if row['speech'] and row['bgm_dry_rms_dbfs'] is not None
               and row['bgm_dry_rms_dbfs'] >= -55]
    dropped = [row for row in covered if row['bgm_rms_dbfs'] is None or row['bgm_rms_dbfs'] < -62]
    ranges = []
    for row in dropped:
        left, right = row['start_sample'], row['end_sample']
        if ranges and left == ranges[-1][1]:
            ranges[-1][1] = right
        else:
            ranges.append([left, right])
    if any(right - left >= .35 * SAMPLE_RATE for left, right in ranges):
        raise ValueError('BGM continuity failure: sustained drop below -62 dBFS over audible source music')
    return {
        'speech_intelligibility': {
            'active_windows': len(active), 'minimum_speech_to_background_db': min(margins, default=None),
            'median_speech_to_music_db': median(music_margins) if music_margins else None,
        },
        'bgm_continuity': {
            'analysis_samples': WINDOW,
            'speech_windows_with_material': len(covered),
            'speech_windows_with_quiet_source': sum(row['speech'] for row in windows) - len(covered),
            'low_music_ranges_samples': ranges,
        },
    }
