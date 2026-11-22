"""Bind one completed native HD candidate and its production and publish assets."""

import argparse
import json
from pathlib import Path
import shutil

from cinematic_edit import TASK
from mechanical_video_next import joint_timeline as joint, workflow
from scripts.common import ROOT, probe, writejson

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def package(task):
    final, preview, publish = (task / name for name in ('final', 'preview', 'publish'))
    movie = final / '门把手回正.mp4'
    animatic = preview / '门把手回正-完整动态预演.mp4'
    plan = read(task / 'joint-timeline.json')
    media = dict(joint.binding(movie), chapter_ids=[cut['id'] for cut in plan['shots']])
    checks = workflow.complete_media(workflow.load(task), media)
    review = read(final / 'technical-review.json')
    if review['technical_status'] != 'PASS' or review['media'] != joint.binding(movie):
        raise ValueError('Resolve the exact-film technical findings before packaging')
    motion = read(final / 'motion-review.json')
    if motion['status'] != 'PASS' or motion['rendered_sha256'] != joint.binding(final / 'scene.blend')['sha256']:
        raise ValueError('Native HD motion review is incomplete or stale')
    covers = read(publish / 'cover-report.json')
    if covers['media'] != joint.binding(movie):
        raise ValueError('Covers must come from this exact film')
    for row in covers['covers']:
        joint.bound(row['cover'])
    source_paths = {
        'patent': TASK / 'restored-3d/sources/US7900978.pdf',
        'patent_text': TASK / 'restored-3d/sources/US7900978.txt',
        'base_geometry': TASK / 'visual-story/contact-refined/scene.blend',
        'historical_reference_edit': TASK / 'visual-story/delivery-66d47353/door-handle-return-contact-66d47353.mp4',
        'treatment': ROOT / 'docs/productions/door-handle-formal-20261122.md',
        'story_program': HERE / 'formal-story.json',
        'scene_program': final / 'scene-program.py',
        'composition_program': HERE / 'formal_edit.py',
        'render_receipt': final / 'chunk-result.json',
        'native_scene': final / 'scene.blend',
        'native_picture': final / 'picture.mp4',
        'native_clock': final / 'source-clock.json',
        'joint_timeline': task / 'joint-timeline.json',
        'blueprint': final / 'blueprint.json',
        'measured_voice': task / 'measured-neil.json',
        'neil_pcm': task / 'neil.wav',
        'foley_pcm': task / 'foley.wav',
        'foley_receipt': task / 'foley-source.json',
        'mixed_pcm': task / 'neil-and-foley.wav',
        'audio_mix': task / 'audio-mix.json',
        'subtitle_ass': task / 'captions.ass',
        'subtitle_srt': task / '门把手回正.srt',
    }
    manifest = dict(media=joint.binding(movie), source_files={key: joint.binding(path)
                    for key, path in source_paths.items()}, third_party_picture_intervals=[],
                    music_intervals=[], narration_provider='qwen3-tts-flash · Neil',
                    original_sound='Generated CC0 foley', simulation=False)
    writejson(final / '门把手回正.media-provenance.json', manifest)
    template = publish / '发布后数据复盘.md'
    shutil.copyfile(ROOT / 'docs/douyin-post-review.md', template)
    summary = publish / '增长设计证据.json'
    shots = {cut['id']: [cut['start_frame']/30, cut['end_frame']/30] for cut in plan['shots']}
    writejson(summary, dict(media=joint.binding(movie), observations={
        'retention': {key: shots[key] for key in ('hook', 'reveal', 'coils', 'release', 'answer')},
        'like': {key: shots[key] for key in ('lost', 'mid', 'lower', 'release')},
        'save': {key: shots[key] for key in ('map', 'design')},
        'comment': joint.binding(publish / '抖音发布文案.md'),
        'follow': {'answer': shots['answer'], 'series_copy': joint.binding(publish / '抖音发布文案.md')},
    }, publication=None, viewer_test=None,
        observed_metrics={key: None for key in ('retention','like','save','comment','follow','share')}))
    report = dict(media=media, preview=joint.binding(animatic), frame_count=plan['frame_count'],
                  duration_seconds=checks['duration'], ffprobe=probe(movie), technical=joint.binding(
                      final / 'technical-review.json'), motion=joint.binding(final / 'motion-review.json'),
                  story_qa=joint.binding(task / 'story-independent-recheck.md'),
                  preview_qa=joint.binding(preview / 'independent-qa.md'),
                  covers=joint.binding(publish / 'cover-report.json'), growth_design=joint.binding(summary),
                  production_inputs=manifest['source_files'],
                  preview_render=read(preview / 'render-timing.json'), hd_render=read(final / 'render-timing.json'),
                  task_file_bytes=sum(path.stat().st_size for path in task.rglob('*') if path.is_file()),
                  disk_free_bytes=shutil.disk_usage(task).free,
                  movie_bytes=movie.stat().st_size, local_render_billing=None, speech_billing=None,
                  final_sensory_acceptance='UNKNOWN', audience_acceptance='UNKNOWN',
                  publication=None)
    for key, name in (('git_start', '起始工作树.json'), ('regression', 'regression-tests.log')):
        if (task / name).is_file():
            report[key] = joint.binding(task / name)
    writejson(task / 'production-report.json', report)
    with workflow.lock(task / '.ledger.lock'):
        data = workflow.load(task)
        run = data['route_runs']['3d']
        run['outputs'].update(media)
        run['status'] = 'FINAL_RENDERED_QA_PENDING'
        workflow.write(task / 'task.json', data)
        workflow.event(task, 'native_hd_candidate_completed', media=media,
                       report=joint.binding(task / 'production-report.json'))
    workflow.continuation(task)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', type=Path)
    args = parser.parse_args()
    package(args.task.resolve())


if __name__ == '__main__':
    main()
