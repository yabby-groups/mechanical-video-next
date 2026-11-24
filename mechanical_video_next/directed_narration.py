"""Compile, audition and compare director-led mechanical video narration."""
import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic
import wave

from scripts import narration
from scripts.common import ROOT, check_output, digest, read_input_json, writejson
from . import joint_timeline as joint
from .voice_direction import ENGINES, plan_direction, require_engine, validate
from .voice_engines import EngineError, Synthesizer, load_profile
from .voice_quality import measure_quality, sensevoice
from .workflow import lock


def synthesis_fields(row):
    timing = {'pause_before_ms', 'pause_after_ms', 'target_duration_ms', 'action_anchors', 'scene_id'}
    return {key: value for key, value in row.items() if key not in timing}


def same_voice_runtime(current, previous):
    # File hashes are still recorded and used for new cache keys. A local adapter
    # update can coexist with prior takes from the same model and reference.
    code = {'worker_sha256', 'engine_source_sha256', 'weights_bytes'}
    return ({k: v for k, v in current.items() if k not in code}
            == {k: v for k, v in previous.items() if k not in code})


def measure(plan, direction, profile, service, output, *, fallback=False, prior=None, segment_id=None):
    validate(direction, plan, profile)
    rows = {row['segment_id']: row for row in direction['segments']}
    selected = next(iter(rows.values()))['selected_tts']
    profile_hash = digest(profile)
    if segment_id is not None and (prior is None or segment_id not in rows):
        raise ValueError('Single replacement requires a prior timeline and an existing segment')
    recordings = {}
    if prior is not None:
        require_engine(prior['actual_engine'])
        if (prior['actual_engine'] != selected
                or any(prior['plan'][key] != plan[key] for key in ('shots', 'actions', 'frame_count'))
                or [row['id'] for row in prior['speech']] != list(rows)):
            raise ValueError('Prior takes require the same picture, actions, sentence order and engine')
        previous = {row['segment_id']: row for row in prior['voice_direction']['segments']}
        if (previous.keys() != rows.keys() or any(
                synthesis_fields(row) != synthesis_fields(previous[key])
                for key, row in rows.items() if key != segment_id)):
            raise ValueError('Only timing or the selected segment can change when reusing prior takes')
        if selected == 'neil' and segment_id and prior.get('voice_profile_sha256') != profile_hash:
            raise ValueError('A Neil replacement requires the prior voice profile')
        recordings = {row['id']: row for row in prior['speech']}

    def measure_engine(engine):
        def sentence(spec):
            row = rows[spec['id']]
            if prior is not None and spec['id'] != segment_id:
                previous = recordings[spec['id']]
                wav, cache = joint.bound(previous['audio']), dict(previous['cache'], reused_from_prior=True)
            else:
                wav, cache = service.synthesize(row, profile, engine)
                if segment_id and not same_voice_runtime(cache.get('runtime', {}),
                                                          recordings[spec['id']]['cache'].get('runtime', {})):
                    raise ValueError('Single replacement requires the prior model, reference, runtime and processing')
            return wav, cache, row['pause_before_ms'] * 48, row['pause_after_ms'] * 48

        voice = 'Neil' if engine == 'neil' else profile['id']
        return joint.measure(plan, None, output, directed_sentence=sentence, voice=voice)

    started = monotonic()
    failure = None
    actual = selected
    try:
        measured = measure_engine(selected)
    except EngineError as error:
        if not fallback or selected == 'neil' or prior is not None:
            raise
        failure = str(error)
        actual = 'neil'
        service.close()
        try:
            measured = measure_engine(actual)
        except EngineError as neil_error:
            raise EngineError(f'CosyVoice 3 failed: {failure}. Neil fallback failed: {neil_error}') from neil_error
    return dict(measured, voice_direction=direction, actual_engine=actual,
                selected_engine=selected, fallback_reason=failure,
                voice_profile_sha256=profile_hash,
                placement_wall_seconds=monotonic() - started)


def excerpt(source, first, last):
    if type(first) is not int or type(last) is not int or not 0 <= first < last <= source['frame_count']:
        raise ValueError('Excerpt requires valid picture frames')
    plan = {'frame_count': last - first, 'shots': [], 'actions': [], 'narration': []}
    for track, end in (('shots', 'end_frame'), ('actions', 'end_frame'), ('narration', 'deadline_frame')):
        for row in source[track]:
            if row[end] <= first or row['start_frame'] >= last:
                continue
            if row['start_frame'] < first or row[end] > last:
                if track != 'shots':
                    raise ValueError('Excerpt boundary cuts a spoken slot or mechanical event: ' + row['id'])
                row = dict(row, source_start_frame=row.get('source_start_frame', 0) +
                           max(first - row['start_frame'], 0))
            plan[track].append(dict(row, start_frame=max(first, row['start_frame']) - first,
                                    **{end: min(last, row[end]) - first}))
    for shot in plan['shots']:
        shot['action_views'] = {
            row['id']: row['source_start_frame'] + max(0, shot['start_frame'] - row['start_frame'])
            for row in plan['actions']
            if shot['start_frame'] < row['end_frame'] and shot['end_frame'] > row['start_frame']
        }
    return joint.validate(plan)


def original_neil(timeline, plan, direction, offset, output):
    source = joint.bound(timeline['narration_audio'])
    speech = {row['id']: row for row in timeline['speech']}
    sample_offset = offset * joint.SAMPLES_PER_FRAME
    frames = plan['frame_count'] * joint.SAMPLES_PER_FRAME
    rows = []
    with wave.open(str(source), 'rb') as original:
        for spec in plan['narration']:
            row = speech[spec['id']]
            start, end = row['start_sample'] - sample_offset, row['end_sample'] - sample_offset
            if row['text'] != spec['text'] or not 0 <= start < end <= frames:
                raise ValueError('Original Neil clip crosses the excerpt or differs from the script')
            with wave.open(str(joint.bound(row['audio'])), 'rb') as clip:
                original.setpos(row['start_sample'])
                if end - start != clip.getnframes() or original.readframes(end - start) != clip.readframes(end - start):
                    raise ValueError('Original Neil PCM differs from its timeline receipt')
            rows.append(dict(row, start_sample=start, end_sample=end))
        original.setpos(sample_offset)
        with wave.open(str(output), 'wb') as result:
            result.setparams(original.getparams())
            result.writeframes(original.readframes(frames))
    return dict(schema_version=2, timeline_policy_version=joint.VERSION, voice='Neil', fps=joint.FPS,
                frame_count=plan['frame_count'], seconds=plan['frame_count'] / joint.FPS, shots=plan['shots'],
                plan=plan, speech=rows, narration_audio=joint.binding(output), voice_direction=direction,
                actual_engine='neil', selected_engine='neil', listening='UNKNOWN',
                source_start_frame=offset, synthesis_basis='archived original Neil PCM')


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *map(str, args)], check=True)


def decoded_video_hash(path):
    return check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:v:0',
                         '-an', '-f', 'hash', '-hash', 'sha256', '-']).decode().strip().removeprefix('SHA256=')


def mux(picture, wav, output, plan, timeline):
    ffmpeg('-i', picture, '-i', wav, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
           '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', output)
    joint.validate_rendered_film(output, plan)
    return joint.validate_rendered_audio(output, plan, timeline)


def subtitles(timeline, path):
    cues = joint.cues(timeline)
    path.write_text(''.join(
        f'{index}\n{narration.srt_time(cue["start"])} --> {narration.srt_time(cue["end"])}\n{cue["text"]}\n\n'
        for index, cue in enumerate(cues, 1)
    ))


def comparison(spec, profile, output, *, engines, models=None, cache=None, repeat_segment=None):
    for engine in engines:
        require_engine(engine)
    source_manifest = read_input_json(ROOT / spec['original_timeline'])
    first, last = spec['source_frames']
    source_picture = ROOT / spec['picture']
    original_plan = excerpt(source_manifest['plan'], first, last)
    edited = spec.get('speech_slots', {})
    if set(edited) - {row['id'] for row in original_plan['narration']}:
        raise ValueError('Comparison slot edits must name existing spoken segments')
    revised_plan = joint.validate(dict(original_plan, narration=[
        dict(row, start_frame=edited[row['id']][0], deadline_frame=edited[row['id']][1])
        if row['id'] in edited else row for row in original_plan['narration']
    ]))
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with lock(output / 'comparison.lock', wait=True), TemporaryDirectory(prefix='render-', dir=output) as scratch:
        scratch = Path(scratch)
        picture = scratch / 'picture.mp4'
        ffmpeg('-i', source_picture, '-map', '0:v:0', '-vf',
               f'trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS', '-an',
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', picture)
        picture_hash = decoded_video_hash(picture)
        for engine in engines:
            plan = original_plan if engine == 'neil' else revised_plan
            direction = plan_direction(plan, spec['beats'], profile, engine,
                                       script_feedback=spec.get('script_feedback', []))
            label = dict(zip(ENGINES, 'AB', strict=True))[engine] + '-' + engine
            staged = scratch / label
            staged.mkdir()
            wav, mp4 = staged / 'narration.wav', staged / 'audition.mp4'
            try:
                with Synthesizer(cache=cache, models=models, diagnostics=output / 'diagnostics') as service:
                    if engine == 'neil':
                        timeline = original_neil(source_manifest, plan, direction, first, wav)
                    else:
                        timeline = measure(plan, direction, profile, service, wav)
                observations = sensevoice(timeline, spec['sensevoice']) if spec.get('sensevoice') else None
                timeline['encoded_audio'] = mux(picture, wav, mp4, plan, timeline)
                qa = measure_quality(timeline, direction, observations, media=mp4)
                if decoded_video_hash(mp4) != picture_hash:
                    raise ValueError('Decoded audition picture differs from the comparison picture')
            except (EngineError, ValueError, OSError, subprocess.SubprocessError) as error:
                results[engine] = {'status': 'UNAVAILABLE', 'reason': str(error)}
                continue
            stats = collect_stats(timeline)
            if repeat_segment and engine != 'neil':
                row = next(row for row in direction['segments'] if row['segment_id'] == repeat_segment)
                with TemporaryDirectory(prefix='repeat-', dir=scratch) as repeat_cache:
                    try:
                        with Synthesizer(cache=repeat_cache, models=models,
                                         diagnostics=output / 'diagnostics') as service:
                            repeated, receipt = service.synthesize(row, profile, engine)
                        original = next(item for item in timeline['speech'] if item['id'] == repeat_segment)
                        stats['repeat'] = dict(segment_id=repeat_segment, original=original['audio']['sha256'],
                                               repeated=joint.binding(repeated)['sha256'],
                                               original_samples=original['end_sample'] - original['start_sample'],
                                               repeated_samples=receipt['samples'],
                                               inference_seconds=receipt['inference']['inference_seconds'])
                    except (EngineError, OSError, ValueError) as error:
                        stats['repeat'] = {'status': 'UNKNOWN', 'reason': str(error)}
            folder = output / label
            folder.mkdir(exist_ok=True)
            wav.replace(folder / wav.name)
            mp4.replace(folder / mp4.name)
            timeline['narration_audio'] = joint.binding(folder / wav.name)
            timeline['mp4'] = joint.binding(folder / mp4.name)
            writejson(folder / 'timeline.json', timeline)
            writejson(folder / 'quality.json', dict(qa, mp4=timeline['mp4']))
            writejson(folder / 'voice_direction.json', direction)
            subtitles(timeline, folder / 'narration.srt')
            results[engine] = dict(status='AUDITION_READY', stats=stats, mp4=timeline['mp4'],
                                   wav=timeline['narration_audio'], timeline=joint.binding(folder / 'timeline.json'),
                                   quality=joint.binding(folder / 'quality.json'), listening='UNKNOWN')
        report = dict(source_picture=joint.binding(source_picture), source_frames=[first, last],
                      picture_decoded_sha256=picture_hash, seconds=original_plan['frame_count'] / joint.FPS,
                      groups=results, perceptual_winner='UNKNOWN')
        writejson(output / 'comparison.json', report)
    return report


def collect_stats(timeline):
    receipts = [row['cache'] for row in timeline['speech']]
    runs = [row['inference'] for row in receipts if 'inference' in row]
    generated = [row['inference'] for row in receipts if 'inference' in row and not row['cache_hit']]
    speech_seconds = sum(row['end_sample'] - row['start_sample'] for row in timeline['speech']) / joint.SAMPLE_RATE
    inference = sum(row['inference_seconds'] for row in runs)
    return dict(
        speech_seconds=speech_seconds, inference_seconds=inference if runs else None,
        inference_realtime_factor=inference / speech_seconds if runs else None,
        fresh_inference_seconds=sum(row['inference_seconds'] for row in generated) if runs else None,
        initialization_seconds=sum(row['initialization_seconds'] for row in generated) if runs else None,
        process_peak_rss_bytes=max((row['process_peak_rss_bytes'] for row in runs), default=None),
        model_bytes=next((row['runtime']['weights_bytes'] for row in receipts if 'runtime' in row), None),
        cache_hits=sum(row.get('cache_hit', False) for row in receipts) if runs else None,
        synthesis_wall_seconds=timeline.get('placement_wall_seconds'),
        billed_inference_cost=None if not runs else 0,
        hardware_energy_cost=None,
    )


def write_audition(plan, direction, profile, service, output, *, fallback=False, prior=None, segment_id=None,
                   picture=None):
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / 'narration.lock', wait=True), TemporaryDirectory(prefix='render-', dir=output) as temporary:
        temporary = Path(temporary)
        wav = temporary / 'narration.wav'
        timeline = measure(plan, direction, profile, service, wav, fallback=fallback,
                           prior=prior, segment_id=segment_id)
        movie = None
        if picture is not None:
            movie = temporary / 'audition.mp4'
            timeline['encoded_audio'] = mux(picture, wav, movie, plan, timeline)
        qa = measure_quality(timeline, direction, media=movie)
        if movie is not None:
            movie.replace(output / movie.name)
            timeline['mp4'] = joint.binding(output / movie.name)
        wav.replace(output / wav.name)
        timeline['narration_audio'] = joint.binding(output / wav.name)
        timeline['quality'] = qa
        subtitles(timeline, output / 'narration.srt')
        writejson(output / 'timeline.json', timeline)
    return timeline


def main():
    def engine_argument(value):
        try:
            return require_engine(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(str(error)) from error

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=ROOT / 'config/voice-profile.json')
    parser.add_argument('--models', type=Path)
    parser.add_argument('--cache', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('timeline', type=Path)
    plan.add_argument('beats', type=Path)
    plan.add_argument('output', type=Path)
    plan.add_argument('--engine', type=engine_argument, choices=ENGINES, default='neil')
    render = commands.add_parser('render')
    render.add_argument('timeline', type=Path)
    render.add_argument('direction', type=Path)
    render.add_argument('output', type=Path)
    render.add_argument('--segment')
    render.add_argument('--prior', type=Path)
    render.add_argument('--fallback-neil', action='store_true')
    render.add_argument('--env-file', type=Path)
    render.add_argument('--picture', type=Path)
    bench = commands.add_parser('compare')
    bench.add_argument('spec', type=Path)
    bench.add_argument('output', type=Path)
    bench.add_argument('--engine', type=engine_argument, choices=ENGINES, action='append', required=True)
    bench.add_argument('--repeat-segment')
    qa = commands.add_parser('qa')
    qa.add_argument('timeline', type=Path)
    qa.add_argument('output', type=Path)
    asr = qa.add_mutually_exclusive_group()
    asr.add_argument('--observations', type=Path)
    asr.add_argument('--sensevoice', type=Path)
    args = parser.parse_args()
    if args.command == 'qa':
        timeline = read_input_json(args.timeline)
        observations = read_input_json(args.observations) if args.observations else None
        if args.sensevoice:
            observations = sensevoice(timeline, read_input_json(args.sensevoice))
        media = joint.bound(timeline['mp4']) if 'mp4' in timeline else None
        quality = measure_quality(timeline, timeline['voice_direction'], observations, media=media)
        if media is not None:
            quality['mp4'] = timeline['mp4']
        writejson(args.output, quality)
        return 0
    try:
        profile = load_profile(args.profile)
    except ValueError as error:
        parser.error(str(error))
    if args.command == 'compare':
        report = comparison(read_input_json(args.spec), profile, args.output, models=args.models, cache=args.cache,
                            engines=dict.fromkeys(args.engine), repeat_segment=args.repeat_segment)
        print(json.dumps({name: item['status'] for name, item in report['groups'].items()}))
        return int(any(row['status'] != 'AUDITION_READY' for row in report['groups'].values()))
    timeline = read_input_json(args.timeline)
    plan = timeline.get('plan', timeline.get('timeline', timeline))
    if args.command == 'plan':
        document = read_input_json(args.beats)
        direction = plan_direction(plan, document['beats'], profile, args.engine,
                                   script_feedback=document.get('script_feedback', []))
        writejson(args.output, direction)
        return 0
    direction = read_input_json(args.direction)
    narration.load_env(args.env_file)
    try:
        prior = None
        if args.prior:
            reference = joint.binding(args.prior)
            prior_plan = read_input_json(joint.bound(reference))['plan']
            prior = joint.receipt(prior_plan, reference, directed=True)
        fallback = args.fallback_neil or profile.get('fallback_engine') == 'neil'
        if fallback and 'neil' not in profile['engines']:
            raise ValueError('Neil fallback needs a Neil route in the voice profile')
        with Synthesizer(cache=args.cache, models=args.models, diagnostics=args.output / 'diagnostics') as service:
            result = write_audition(plan, direction, profile, service, args.output, fallback=fallback, prior=prior,
                                    segment_id=args.segment, picture=args.picture)
    except (ValueError, EngineError) as error:
        parser.error(str(error))
    if result['fallback_reason']:
        print(f'Using Neil for the entire track: {result["fallback_reason"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
