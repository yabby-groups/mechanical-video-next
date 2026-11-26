"""Inspect decoded episode frames and replay selected poses in Blender."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image

from scripts.common import ROOT, probe, run, writejson
from .workflow import lock
from . import joint_timeline as joint, pacing, qa_images
from .blender_runtime import run_blender


BLENDER_SCRIPT = ROOT / 'blender/visual_diagnosis.py'


def scene_source(shot, motion, episode, *, direct):
    """Resolve the picture's evaluated scene from its render binding."""
    if motion is None:
        return None
    binding = motion['binding']
    inputs = binding.get('mechanics', {}).get('inputs', {})
    authored = (episode / shot.get('scene', 'scene.py')).resolve()
    matches = [path for path, sha in inputs.items() if sha == binding['scene']]
    path = str(authored) if direct and str(authored) in matches else None
    if path is None and not direct and len(matches) == 1:
        path = matches[0]
    if path is None:
        return None
    return {'source': {'path': path, 'sha256': binding['scene']},
            'shot': binding['shot'], 'frame_count': binding['frames'],
            'inputs': [{'path': p, 'sha256': digest} for p, digest in inputs.items()]}


def shot_binding(shot, motion, episode, *, direct, preview_step):
    if type(preview_step) is not int or preview_step < 1:
        return {}
    scene = scene_source(shot, motion, episode, direct=direct)
    if scene is None:
        return {}
    evidence = shot.get('mechanics', {}).get('evidence')
    research = next((ref for ref in scene['inputs']
                     if evidence and ref['path'] == str((episode / evidence).resolve())), None)
    return {'diagnostic_scene': scene, 'source_preview_step': preview_step,
            'diagnostic_research': research}


def _intervals(path, media, limit):
    receipt = path.with_suffix('.mechanics.json')
    if not receipt.is_file():
        return []
    data = json.loads(receipt.read_text())
    if data['media']['sha256'] != media['sha256']:
        raise ValueError('Episode receipt belongs to different MP4 bytes')
    cursor = 0
    for row in data['intervals']:
        first, last = joint.interval(row, limit)
        if cursor != first:
            raise ValueError('Episode receipt has a gap or overlap')
        cursor = last
    if cursor != limit:
        raise ValueError('Episode receipt does not cover the decoded edit')
    return data['intervals']


def _shot_at(intervals, frame):
    return next((row for row in intervals if row['start_frame'] <= frame < row['end_frame']), None)


def source_location(row, frame):
    offset = row.get('source_start_frame', 0) + frame - row['start_frame']
    step = row.get('source_preview_step')
    return {
        'shot_id': row['id'], 'source_frame': (offset // step) * step if step else None,
        'source_preview_step': step,
        'scene': row.get('diagnostic_scene'), 'research': row.get('diagnostic_research'),
    }


def _view_frames(media, stream, indices, size, crop, zoom, intervals, cache):
    result = []
    with qa_images.decoded_frames(media['path'], stream, indices, cache_dir=cache) as paths:
        for index, path in zip(indices, paths, strict=True):
            with Image.open(path) as raw:
                if raw.size != size:
                    raise ValueError('Decoded size differs from the selected video track')
            row = _shot_at(intervals, index)
            location = source_location(row, index) if row else None
            short = qa_images.prepare_image(
                path, max_size=max(size) * zoom, crop_region=crop, zoom=zoom, quality=94,
                target_bytes=2_000_000, source_time=index / joint.FPS,
                shot_id=location['shot_id'] if location else None, cache_dir=cache,
            )
            # The decoded PNG exists only during this batch. The evidence remains bound to the MP4.
            result.append(short | {'source_path': media['path'], 'video_sha256': media['sha256'],
                                   'decoded_frame': index, 'decoded_size': size, 'location': location})
    return result


def _event_clip(media, stream, target, first, last, crop):
    filters = [f'trim=start_frame={first}:end_frame={last}', 'setpts=PTS-STARTPTS', 'format=yuv444p']
    if crop is not None:
        x, y, right, bottom = crop
        filters.append(f'crop={right-x}:{bottom-y}:{x}:{y}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as directory:
        output = Path(directory) / target.name
        run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-noautorotate', '-i', media['path'],
             '-map', f'0:{stream}', '-vf', ','.join(filters), '-frames:v', last-first,
             '-fps_mode', 'passthrough', '-an', '-c:v', 'libx264', '-crf', '15', output])
        video = next(row for row in probe(output)['streams'] if row['codec_type'] == 'video')
        if int(video['nb_frames']) != last-first:
            raise ValueError('Diagnostic clip did not preserve the requested decoded interval')
        joint.bound(media)
        output.replace(target)
    return joint.binding(target) | {'frame_range': [first, last]}


def _replay(scene, frames, region, args, directory, *, mapped):
    path = joint.bound(scene['source'])
    for ref in scene.get('inputs', []):
        joint.bound(ref)
    if mapped and max(frames) >= scene['frame_count']:
        raise ValueError('Requested pose exceeds the evaluated shot')
    request = {'frames': frames, 'region': region, 'view': args.view,
               'objects': args.objects, 'hide': args.hide, 'isolate': args.isolate,
               'xray': args.xray, 'resolution': args.resolution,
               'shot': scene.get('shot'), 'frame_count': scene.get('frame_count')}
    options = ['--python-exit-code', '7', '--python', BLENDER_SCRIPT]
    if path.suffix == '.blend':
        options.insert(0, path)
    else:
        request['script'] = str(path)
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory / uuid4().hex
    directory.mkdir()
    writejson(directory / 'request.json', request)
    with lock(ROOT / 'work/production.lock', wait=True):
        run_blender([*options, '--', directory], directory=directory / 'runtime', timeout=180)
    joint.bound(scene['source'])
    for ref in scene.get('inputs', []):
        joint.bound(ref)
    result = json.loads((directory / 'poses.json').read_text())
    for row in result:
        if row['image']:
            row['image'] = joint.binding(directory / row['image'])
    return {'scene': scene, 'mapping': 'episode_receipt' if mapped else 'reviewer_supplied',
            'request': request, 'poses': result, 'report': joint.binding(directory / 'poses.json')}


def _review(args):
    analysis = pacing.opening_analysis(args.media, expected_sha=args.sha256)
    media, stream = analysis['media'], analysis['picture_stream']
    path = Path(media['path'])
    video = next(row for row in probe(path)['streams'] if row['index'] == stream)
    rotated = any(row.get('rotation') for row in video.get('side_data_list', ()))
    if (video.get('avg_frame_rate') != '30/1' or video.get('r_frame_rate') != '30/1'
            or float(video.get('start_time', 'inf')) != 0 or rotated):
        raise ValueError('Frame diagnosis uses a zero-start, unrotated 30 fps episode picture track')
    limit = int(video['nb_frames'])
    size = (video['width'], video['height'])
    intervals = _intervals(path, media, limit)
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = {'media': media, 'decoded_size': size, 'frame_count': limit, 'fps': joint.FPS,
              'continuous_viewing': 'UNKNOWN', 'observations': []}
    if args.overview:
        pacing.extract_phone_preview(analysis, directory)
        report['overview'] = analysis['phone_preview']
        report['shots'] = []
        for row in intervals:
            first, last = row['start_frame'], row['end_frame']
            item = {'id': row['id'], 'frame_range': [first, last], 'time_range': [first/30, last/30]}
            motion = row.get('evaluated_motion')
            if motion is not None:
                event_first, event_last = motion['preview_range']
                offset = row.get('source_start_frame', 0)
                start, stop = max(first, first + event_first-offset), min(last, first + event_last-offset)
                if start < stop:
                    item['evaluated_motion_window'] = [start, stop]
            report['shots'].append(item)
    indices = args.frames
    if args.at is not None:
        if not math.isfinite(args.at) or args.at < 0:
            raise ValueError('Use a nonnegative finite time')
        indices = [math.floor(args.at * joint.FPS + 1e-8)]
    crop = args.crop
    if crop is not None:
        x, y, right, bottom = crop
        if not (0 <= x < right <= size[0] and 0 <= y < bottom <= size[1]):
            raise ValueError('Crop must be within the native video frame')
    region = [crop[i] / size[i % 2] for i in range(4)] if crop else None
    if args.window:
        first, last = args.window
        if not 0 <= first < last <= limit or last-first > 300:
            raise ValueError('A diagnostic clip must cover 1–300 decoded frames')
        filename = 'event-' + qa_images.key([media['sha256'], first, last, crop])[:16] + '.mp4'
        clip_path = directory / filename
        report['event'] = _event_clip(media, stream, clip_path, first, last, crop)
        if not indices:
            indices = sorted({first, (first+last)//2, last-1})
    if indices:
        if max(indices) >= limit:
            raise ValueError('Requested frame exceeds the decoded edit')
        report['images'] = _view_frames(media, stream, indices, size, crop, args.zoom, intervals, qa_images.CACHE)
    if args.model:
        rows = [_shot_at(intervals, index) for index in indices]
        if not rows or rows[0] is None or any(row != rows[0] for row in rows):
            raise ValueError('Select frames in one mapped episode shot, or supply a saved Blender scene')
        locations = [source_location(row, index) for row, index in zip(rows, indices, strict=True)]
        scene = locations[0]['scene']
        if not scene or any(location['source_frame'] is None for location in locations):
            raise ValueError('The shot has no bound evaluable Blender source')
        frames = sorted({row['source_frame'] for row in locations})
        report['blender'] = _replay(scene, frames, region, args, directory / 'blender', mapped=True)
    elif args.blend:
        scene = {'source': joint.binding(args.blend)}
        report['blender'] = _replay(scene, args.blend_frames, region, args, directory / 'blender', mapped=False)
    if args.baseline:
        before_analysis = pacing.opening_analysis(args.baseline)
        before = before_analysis['media']
        before_path = Path(before['path'])
        before_video = next(row for row in probe(before_path)['streams'] if row['codec_type'] == 'video'
                            and row['index'] == before_analysis['picture_stream'])
        if any(video.get(k) != before_video.get(k) for k in (
                'width', 'height', 'avg_frame_rate', 'r_frame_rate', 'start_time', 'side_data_list')):
            raise ValueError('Baseline must have the same picture geometry and clock')
        before_intervals = _intervals(before_path, before, int(before_video['nb_frames']))
        report['baseline'] = {'media': before, 'images': _view_frames(
            before, before_video['index'], indices, size, crop, args.zoom, before_intervals, qa_images.CACHE)}
        if args.window:
            report['baseline']['event'] = _event_clip(
                before, before_video['index'], directory / ('baseline-' + filename), first, last, crop)
        joint.bound(before)
    joint.bound(media)
    output = directory / 'visual-diagnosis.json'
    writejson(output, report)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--sha256')
    parser.add_argument('--overview', action='store_true', help='Full playback and available shot/event intervals')
    frames = parser.add_mutually_exclusive_group()
    frames.add_argument('--frames', nargs='+', type=int, help='Exact zero-based decoded indices, up to 16')
    frames.add_argument('--at', type=float, help='Select the displayed frame at this second')
    parser.add_argument('--window', nargs=2, type=int, metavar=('FIRST', 'STOP'), help='Native-rate event, stop exclusive')
    parser.add_argument('--crop', nargs=4, type=int, metavar=('X', 'Y', 'RIGHT', 'BOTTOM'))
    parser.add_argument('--zoom', type=int, choices=range(1, 5), default=1)
    parser.add_argument('--baseline', type=Path, help='Same camera and clock comparison using identical pixels')
    model = parser.add_mutually_exclusive_group()
    model.add_argument('--model', action='store_true', help='Replay the bound source from the episode receipt')
    model.add_argument('--blend', type=Path, help='Explicit saved Blender scene for older films')
    parser.add_argument('--blend-frames', nargs='+', type=int, help='Native scene frames verified by the reviewer')
    parser.add_argument('--view', choices=('objects', 'camera', 'front', 'side', 'top'), default='objects')
    parser.add_argument('--objects', nargs='+', default=[], help='Exact Blender names to inspect and frame')
    parser.add_argument('--hide', nargs='+', default=[], help='Hide existing shells or occluders in the diagnostic render')
    parser.add_argument('--isolate', action='store_true')
    parser.add_argument('--xray', action='store_true')
    parser.add_argument('--resolution', type=int, choices=(360, 540, 720, 1080), default=540,
                        help='Diagnostic render long edge in pixels')
    args = parser.parse_args()
    if not (args.overview or args.frames or args.at is not None or args.window or args.blend):
        parser.error('Select an overview, decoded frame, event window or native scene frames')
    if args.baseline and not (args.frames or args.at is not None or args.window):
        parser.error('A baseline comparison needs decoded frames or an event window')
    if args.zoom > 1 and args.crop is None:
        parser.error('Zoom needs a native-pixel crop')
    if bool(args.blend) != bool(args.blend_frames):
        parser.error('--blend and --blend-frames are used together')
    if args.blend_frames and not 1 <= len(set(args.blend_frames)) == len(args.blend_frames) <= 16:
        parser.error('Use 1–16 Blender frames')
    if args.model and not (args.frames or args.at is not None or args.window):
        parser.error('Mapped Blender diagnostics need decoded frames')
    if not (args.model or args.blend) and (
            args.view != 'objects' or args.objects or args.hide or args.isolate or args.xray):
        parser.error('Blender view and object options require --model or --blend')
    if (args.isolate or args.view in ('front', 'side', 'top')) and not args.objects:
        parser.error('Isolation and orthographic close-ups need named objects')
    print(_review(args))


if __name__ == '__main__':
    main()
