"""Compare decoded pictures in claimed revision intervals; never judge quality.

This is a deterministic verification tool for existing timeline/QA handoffs, not
a new production ledger. Every frame in each claimed interval is compared after
normalizing to 160x90 RGB. Re-encoding noise is distinguished from material change.
"""
import argparse
from contextlib import contextmanager, ExitStack
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

from scripts.common import filehash, probe, writejson

CLAIM_FIELDS = ('shot_id', 'defect_key', 'knowledge_target', 'previous_range', 'current_range', 'comparison_region')


def revision_claims(changes):
    """The declared claim includes its region, independently of pixel statistics."""
    return [{key: row[key] for key in CLAIM_FIELDS if key in row} for row in changes]


def bind(path):
    return {'path': str(Path(path).resolve()), 'sha256': filehash(path)}


def spec(path):
    result = probe(path)
    video = next(s for s in result['streams'] if s['codec_type'] == 'video')
    a, b = map(int, video['avg_frame_rate'].split('/'))
    return {'width': video['width'], 'height': video['height'], 'fps': a/b,
            'duration': float(video.get('duration', result['format']['duration'])),
            'codec': video['codec_name']}


def comparison_region(change):
    """An explicitly chosen content region excludes captions/credits when needed.

    This selection is part of the recorded claim, not automatic object detection.
    Independent QA must still check that the region contains the intended action.
    """
    region = change.get('comparison_region')
    if region is None:
        return None
    if (not isinstance(region, list) or len(region) != 4
            or any(type(v) not in {int, float} or not math.isfinite(v) for v in region)):
        raise ValueError('Comparison region requires normalized finite x, y, width, height')
    x, y, width, height = region
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < width <= 1-x and 0 < height <= 1-y):
        raise ValueError('Comparison region must lie inside both complete pictures')
    return region


def frame_span(start, seconds):
    """Half-open interval on the normalized 30 fps media clock."""
    return math.ceil(start*30-1e-6), math.ceil((start+seconds)*30-1e-6)


def crop_filter(region):
    if region is None:
        return ''
    x, y, width, height = region
    return f'crop=iw*{width}:ih*{height}:iw*{x}:ih*{y},'


@contextmanager
def frames(path, start, seconds, region=None):
    # Seek only to a whole second (also a 30 fps boundary), then trim the
    # normalized frame grid. Fractional input seeking changes fps filter phase.
    seek = math.floor(start)
    first, last = frame_span(start, seconds)
    trim = f'fps=30,trim=start_frame={first-seek*30}:end_frame={last-seek*30},setpts=PTS-STARTPTS,'
    # A file lets both decoders emit diagnostics while stdout is read in lockstep.
    with tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-ss', str(seek), '-i', str(path),
            '-frames:v', str(last-first), '-an', '-vf', trim+crop_filter(region)+'scale=160:90:flags=area,format=rgb24',
            '-fps_mode', 'passthrough', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE, stderr=stderr)
        try:
            yield process, stderr
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()


def decode_errors(*decoders):
    messages = []
    for process, stderr in decoders:
        stderr.seek(0)
        detail = stderr.read(8192).decode(errors='replace').strip()
        if detail or process.poll():
            messages.append(f'{process.args[process.args.index("-i")+1]} (exit {process.poll()}): {detail}')
    return ' | '.join(messages)


def compare(previous, current, changes, *, mean_threshold=2.0, changed_fraction=.01):
    """A PASS means material decoded changes exist, never that they are better."""
    if (not 0 < mean_threshold <= 255 or not 0 < changed_fraction <= 1):
        raise ValueError('Finite positive visual thresholds required')
    before, after = spec(previous), spec(current)
    if not isinstance(changes, list) or not changes:
        raise ValueError('Declared shot/defect intervals required')
    rows = []
    for change in changes:
        if not all(isinstance(change.get(k), str) and change[k].strip()
                   for k in ('shot_id', 'defect_key', 'knowledge_target')):
            raise ValueError('Revision needs shot, persistent defect and intended knowledge/quality target')
        ranges = []
        for key, info in (('previous_range', before), ('current_range', after)):
            value = change.get(key)
            if (not isinstance(value, list) or len(value) != 2
                    or any(type(v) not in {int,float} or not math.isfinite(v) for v in value)
                    or not 0 <= value[0] < value[1] <= info['duration']+1e-5):
                raise ValueError('Claimed revision intervals must lie in actual media')
            ranges.append(value)
        lengths = [r[1]-r[0] for r in ranges]
        if abs(lengths[0]-lengths[1]) > 1/30+1e-5:
            raise ValueError('Compare corresponding equal-duration intervals; split timing edits into matching actions')
        counts = [last-first for first, last in (frame_span(r[0], lengths[0]) for r in ranges)]
        if not counts[0] or counts[0] != counts[1]:
            raise ValueError('Corresponding intervals must contain the same nonzero number of 30 fps frames')
        region = comparison_region(change)
        count, meaningful, total, maximum = 0, 0, 0., 0.
        hashes = [hashlib.sha256(),hashlib.sha256()]
        with ExitStack() as cleanup:
            decoders = [cleanup.enter_context(frames(p,r[0],lengths[0],region))
                        for p,r in zip((previous,current),ranges)]
            workers = [process for process, _ in decoders]
            while True:
                pixels = [worker.stdout.read(160*90*3) for worker in workers]
                if not any(pixels):
                    break
                if any(len(p) != 160*90*3 for p in pixels):
                    raise ValueError('Decoded frame count mismatch in corresponding interval: ' + decode_errors(*decoders))
                for digest, data in zip(hashes,pixels):
                    digest.update(data)
                mae = sum(abs(a-b) for a,b in zip(*pixels))/len(pixels[0])
                count += 1
                meaningful += mae >= mean_threshold
                total += mae
                maximum = max(maximum,mae)
            # Equal early EOF in both decoders is not complete-interval evidence.
            expected_frames = counts[0]
            if any([w.wait() for w in workers]) or count != expected_frames:
                raise ValueError(f'Complete interval decoding failed ({count}/{expected_frames} frames): '
                                 + decode_errors(*decoders))
        passed = meaningful/count >= changed_fraction
        rows.append({**change, 'decoded_frames':count, 'mean_rgb_difference':total/count,
            'maximum_frame_mean_difference':maximum, 'materially_changed_frames':meaningful,
            'changed_frame_fraction':meaningful/count, 'decoded_sha256':[h.hexdigest() for h in hashes],
            'observable_change':'PASS' if passed else 'FAIL', 'quality_improved':'UNKNOWN'})
    return {'schema_version':1, 'previous_media':bind(previous), 'current_media':bind(current),
        'previous_spec':before,'current_spec':after, 'changes':rows,
        'method':{'kind':'every_frame_decoded_rgb','width':160,'height':90,'fps':30,
                  'mean_threshold':mean_threshold,'required_changed_fraction':changed_fraction},
        'status':'OBSERVABLE_CHANGE_VERIFIED' if all(r['observable_change']=='PASS' for r in rows) else 'EXPECTED_CHANGE_NOT_DEMONSTRATED',
        'quality_improved':'UNKNOWN', 'limitation':'Pixel differences do not establish semantic improvement; independent exact-media QA required.'}


def validate_report(report, current):
    if report.get('current_media') != bind(current):
        raise ValueError('Revision report must bind the actual current MP4')
    previous = report['previous_media']
    if previous != bind(previous['path']):
        raise ValueError('Previous revision media is missing or changed')
    settings = report.get('method', {})
    rerun = compare(previous['path'], current,
                    revision_claims(report.get('changes', [])),
                    mean_threshold=settings.get('mean_threshold',2.),
                    changed_fraction=settings.get('required_changed_fraction',.01))
    if rerun != report or report['status'] != 'OBSERVABLE_CHANGE_VERIFIED':
        raise ValueError('Expected visual revision was not independently reproducible')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous',type=Path)
    parser.add_argument('current',type=Path)
    parser.add_argument('--changes',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.resolve() in {args.previous.resolve(),args.current.resolve(),args.changes.resolve()}:
        raise ValueError('Revision report cannot overwrite its inputs')
    report=compare(args.previous,args.current,json.loads(args.changes.read_text()))
    writejson(args.output,report)
    print(json.dumps({'status':report['status'],'report':str(args.output),'quality_improved':'UNKNOWN'}))
    if report['status'] != 'OBSERVABLE_CHANGE_VERIFIED':
        raise SystemExit(1)


if __name__=='__main__':
    main()
