"""Compare decoded pictures in claimed revision intervals; never judge quality.

This is a deterministic verification tool for existing timeline/QA handoffs, not
a new production ledger. Every frame in each claimed interval is compared after
normalizing to 160x90 RGB. Re-encoding noise is distinguished from material change.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from scripts.common import filehash, probe, writejson


def bind(path):
    return {'path': str(Path(path).resolve()), 'sha256': filehash(path)}


def spec(path):
    result = probe(path)
    video = next(s for s in result['streams'] if s['codec_type'] == 'video')
    a, b = map(int, video['avg_frame_rate'].split('/'))
    return {'width': video['width'], 'height': video['height'], 'fps': a/b,
            'duration': float(video.get('duration', result['format']['duration'])),
            'codec': video['codec_name']}


def frames(path, start, seconds):
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(path),
        '-t', str(seconds), '-an', '-vf', 'scale=160:90:flags=area,fps=30,format=rgb24',
        '-f', 'rawvideo', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


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
        workers = [frames(p,r[0],lengths[0]) for p,r in zip((previous,current),ranges)]
        count, meaningful, total, maximum = 0, 0, 0., 0.
        hashes = [hashlib.sha256(),hashlib.sha256()]
        try:
            while True:
                pixels = [worker.stdout.read(160*90*3) for worker in workers]
                if not any(pixels):
                    break
                if any(len(p) != 160*90*3 for p in pixels):
                    raise ValueError('Decoded frame count mismatch in corresponding interval')
                for digest, data in zip(hashes,pixels):
                    digest.update(data)
                mae = sum(abs(a-b) for a,b in zip(*pixels))/len(pixels[0])
                count += 1
                meaningful += mae >= mean_threshold
                total += mae
                maximum = max(maximum,mae)
            if any(w.wait() for w in workers) or not count:
                raise ValueError('Complete interval decoding failed')
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait()
                worker.stdout.close()
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
                    [{k:r[k] for k in ('shot_id','defect_key','knowledge_target','previous_range','current_range')}
                     for r in report.get('changes',[])],
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
