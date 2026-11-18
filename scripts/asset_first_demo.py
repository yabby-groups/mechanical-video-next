"""Exercise the asset-first hybrid policy using existing correction tape media."""
import json
import subprocess
import sys
import shutil
from pathlib import Path

from common import ROOT, filehash, writejson
from produce import validate_video
from mechanical_video_next.media_policy import binding, validate_document, write_manifest
from mechanical_video_next.provenance import bound, write_remotion_proof
from mechanical_video_next.remotion_build import render
from mechanical_video_next.reference_library import ingest_media, match_media
from mechanical_video_next.three_d import validate_config
from mechanical_video_next.workflow import lock

OUT = ROOT / 'output/asset-first-demo'
BASE = ROOT / 'output/correction-tape-visual-narrative-demo-v2'


def v4():
    prior = json.loads(BASE.with_suffix('.3d-provenance.json').read_text())
    cfg = json.loads((OUT/'hybrid-demo-v3.config.json').read_text())
    cfg['id'] = 'asset-first-correction-tape-demo-v4'
    old_matches = json.loads((OUT/'hybrid-demo-v3.library-match.json').read_text())['shots']
    refs = {s['shot_id']: s for s in prior['shots']}
    raws = {sid: bound(s['render_output']) for sid, s in refs.items()}
    library = OUT/'reference-library'
    results = {}
    for sid in ('apply', 'reveal', 'slip'):
        query = old_matches[sid]['query']
        match = match_media(query, root=library)
        if match['reuse_decision'] != 'REUSE' or match['selected_asset']['sha256'] != filehash(raws[sid]):
            raise ValueError('Library selected a different source for ' + sid)
        results[sid] = dict(query=query, result=match, ingest=old_matches[sid]['ingest'])
    graphic = cfg['shots']['film-route']['graphic']
    graphic_file = OUT/'hybrid-demo-v4.graphic.json'
    writejson(graphic_file, graphic)
    rights = results['apply']['result']['license']
    meta = dict(source_type='GENERATED', origin='project', project_id='correction-tape',
                tags=['correction-tape'], mechanism_knowledge=['film-route-diagram'], used_shots=[],
                sources=['US8746316B2 Figs 1-3', 'Prior authored Remotion composite'],
                source_url=graphic_file.as_uri(), credit=results['apply']['result']['credit'],
                content_verified=True, quality=dict(approved=True, approval_scope='exact previously rendered graphic definition; visual acceptance unknown'),
                license=rights, original_config=binding(BASE.with_suffix('.3d-provenance.json')))
    ingest = ingest_media(meta, graphic_file, root=library)
    query = dict(project_id='correction-tape', tags=['correction-tape'], mechanism_knowledge=['film-route-diagram'],
                 usage_scope='teaching_demo', duration_sec=3, accepted_types=['graphic'])
    result = match_media(query, root=library)
    if result['reuse_decision'] != 'REUSE' or result['selected_asset']['sha256'] != filehash(graphic_file):
        raise ValueError('Library did not select the authored graphic definition')
    results['film-route'] = dict(ingest=ingest, query=query, result=result)
    receipt = OUT/'hybrid-demo-v4.library-match.json'
    writejson(receipt, dict(shots=results, scope='Video quality reviewed on one sampled frame; graphic is the exact previously rendered definition. Continuous motion and listening remain UNKNOWN.'))
    media = {}
    for sid in ('apply', 'reveal', 'film-route', 'slip'):
        match = results[sid]['result']
        row = cfg['shots'][sid]['visual']
        row.update(selected_asset=match['selected_asset'], source_url=match['source_url'],
                   source_type=match['source_type'], license=match['license'],
                   license_status=match['license_status'], credit=match['credit'],
                   source_time_range=match['source_time_range'], reuse_decision='REUSE',
                   generation_required=False,
                   matching=dict(attempts=[dict(priority=1, result='Exact project asset selected by reference_library.match_media')],
                                 receipt=binding(receipt), receipt_shot=sid))
        if sid != 'film-route':
            media[sid] = (bound(match['selected_asset']) if sid == 'apply' else raws[sid], 'video', refs[sid]['cache_key'])
    row = cfg['shots']['apply']['visual']
    cfg['shots']['apply']['footage'].update(row['selected_asset'], source_url=row['source_url'],
                                           license=row['license'], credit=row['credit'])
    validate_document(cfg)
    validate_config(cfg)
    config, props = OUT/'hybrid-demo-v4.config.json', OUT/'hybrid-demo-v4.props.json'
    target, build = OUT/'hybrid-demo-v4.mp4', OUT/'hybrid-demo-v4.hybrid-build.json'
    writejson(config, cfg)
    shutil.copyfile(OUT/'hybrid-demo-v3.props.json', props)
    shutil.copyfile(OUT/'hybrid-demo-v3.mp4', target)
    if filehash(props) != filehash(OUT/'hybrid-demo-v3.props.json') or filehash(target) != filehash(OUT/'hybrid-demo-v3.mp4'):
        raise ValueError('Cached output or props changed')
    assets = prior['shots'][0]['model_assets']
    write_remotion_proof(build, target, props, cfg, media, bound(assets[0]), bound(assets[1]))
    write_manifest(OUT/'hybrid-demo-v4.media-provenance.json', target, cfg, build)
    subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True)
    writejson(OUT/'hybrid-demo-v4.reuse-report.json', dict(media=binding(target), prior_media=binding(OUT/'hybrid-demo-v3.mp4'),
        props=binding(props), prior_props=binding(OUT/'hybrid-demo-v3.props.json'), cache_hit=True,
        reused_video_seconds=15, reused_remotion_definition_seconds=3, duration_seconds=18,
        scope='Project-authored 3D video and previously rendered native Remotion definition; no third-party footage.',
        acceptance='UNKNOWN', sampled_quality='PASS for source video samples only; motion and audio UNKNOWN'))
    print(json.dumps(dict(media=str(target), sha256=filehash(target), cache_hit=True)))


def v3():
    prior = json.loads(BASE.with_suffix('.3d-provenance.json').read_text())
    cfg = json.loads((OUT/'hybrid-demo-v2.config.json').read_text())
    cfg['id'] = 'asset-first-correction-tape-demo-v3'
    proof = OUT/'qa-v2/source-sample-review.md'
    if not proof.is_file():
        raise ValueError('Independent sampled source quality review is required')
    refs = {s['shot_id']: s for s in prior['shots']}
    raws = {sid: bound(s['render_output']) for sid, s in refs.items()}
    library = OUT/'reference-library'
    rights = cfg['shots']['apply']['visual']['license']
    credit = cfg['shots']['apply']['visual']['credit']
    all_results = {}
    for sid in ('apply', 'reveal', 'slip'):
        raw = raws[sid]
        seconds = cfg['shots'][sid]['seconds']
        meta = dict(source_type='OWNED', origin='project', project_id='correction-tape',
                    tags=['correction-tape'], mechanism_knowledge=[sid], used_shots=[],
                    sources=['US8746316B2 Figs 1-4C'], source_url=raw.as_uri(), credit=credit,
                    content_verified=True, quality=dict(approved=True, approval_scope='single sampled frame',
                    review=binding(proof)), license=dict(rights, usage_scopes=['teaching_demo'],
                    usage_restrictions=[]), segment=dict(start_sec=0, end_sec=seconds))
        ingest = ingest_media(meta, raw, root=library)
        query = dict(project_id='correction-tape', tags=['correction-tape'], mechanism_knowledge=[sid],
                     usage_scope='teaching_demo', duration_sec=seconds, accepted_types=['video'])
        result = match_media(query, root=library)
        if result['reuse_decision'] != 'REUSE' or result['selected_asset']['sha256'] != filehash(raw):
            raise ValueError('Library did not select the exact validated source for ' + sid)
        all_results[sid] = dict(ingest=ingest, query=query, result=result)
    diagram_query = dict(project_id='correction-tape', tags=['correction-tape'],
                         mechanism_knowledge=['film-route-diagram'], usage_scope='teaching_demo',
                         duration_sec=3, accepted_types=['video'])
    diagram = match_media(diagram_query, root=library)
    all_results['film-route'] = dict(query=diagram_query, result=diagram)
    receipt = OUT/'hybrid-demo-v3.library-match.json'
    writejson(receipt, dict(shots=all_results, scope='Source quality eligibility covers a single sampled frame; motion and listening UNKNOWN.'))
    media = {}
    for sid in ('apply', 'reveal', 'slip'):
        result = all_results[sid]['result']
        visual = cfg['shots'][sid]['visual']
        visual['selected_asset'] = result['selected_asset']
        visual['source_url'] = result['source_url']
        visual['matching'] = dict(attempts=[dict(priority=1, result='Selected exact project asset by reference_library.match_media')],
                                  receipt=binding(receipt), receipt_shot=sid)
        # Native provenance must continue to use the original cache directory with its checks.json.
        media[sid] = (bound(result['selected_asset']) if sid == 'apply' else raws[sid], 'video', refs[sid]['cache_key'])
    apply = cfg['shots']['apply']
    apply['footage'].update(cfg['shots']['apply']['visual']['selected_asset'])
    apply['footage']['source_url'] = apply['visual']['source_url']
    visual = cfg['shots']['film-route']['visual']
    visual['matching'] = dict(receipt=binding(receipt), receipt_shot='film-route', attempts=[
        dict(priority=1, result='Exact diagram absent from project video matches'),
        dict(priority=2, result='No exact local matching video in indexed library'),
        dict(priority=3, result='External sources not searched for this existing original diagram'),
        dict(priority=4, result='Stock providers not searched for this existing original diagram'),
        dict(priority=5, result='Indexed source renders do not provide a labeled process diagram')],
        generation_reason='Reuse the previously authored Remotion diagram for the exact coating and backing sequence; no stock diagram was established.')
    validate_document(cfg)
    validate_config(cfg)
    config = OUT/'hybrid-demo-v3.config.json'
    props = OUT/'hybrid-demo-v3.props.json'
    target = OUT/'hybrid-demo-v3.mp4'
    writejson(config, cfg)
    shutil.copyfile(OUT/'hybrid-demo-v2.props.json', props)
    shutil.copyfile(OUT/'hybrid-demo-v2.mp4', target)
    if filehash(props) != filehash(OUT/'hybrid-demo-v2.props.json') or filehash(target) != filehash(OUT/'hybrid-demo-v2.mp4'):
        raise ValueError('Cached Remotion output or props changed')
    assets = prior['shots'][0]['model_assets']
    build = OUT/'hybrid-demo-v3.hybrid-build.json'
    write_remotion_proof(build, target, props, cfg, media, bound(assets[0]), bound(assets[1]))
    write_manifest(OUT/'hybrid-demo-v3.media-provenance.json', target, cfg, build)
    subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True)
    writejson(OUT/'hybrid-demo-v3.reuse-report.json', dict(media=binding(target),
        prior_media=binding(OUT/'hybrid-demo-v2.mp4'), props=binding(props),
        prior_props=binding(OUT/'hybrid-demo-v2.props.json'), cache_hit=True,
        reuse_seconds=15, remotion_diagram_seconds=3, duration_seconds=18,
        scope='Project-generated 3D videos reused; no third-party or live-action footage.',
        acceptance='UNKNOWN', sample_quality='PASS within sampled-frame scope; motion and audio UNKNOWN'))
    print(json.dumps(dict(media=str(target), sha256=filehash(target), cache_hit=True)))


def main():
    if '--v4' in sys.argv or len(sys.argv) == 1:
        v4()
        return
    if '--v3' in sys.argv:
        v3()
        return
    OUT.mkdir(parents=True, exist_ok=True)
    prior = json.loads(BASE.with_suffix('.3d-provenance.json').read_text())
    props = json.loads(BASE.with_suffix('.props.json').read_text())
    cfg = prior['build']['visual_config']
    cfg.update(id='asset-first-correction-tape-demo-v2', media_policy_version=1)
    props.update(media_policy_version=1)
    proof_path = OUT / 'authored-media-evidence.json'
    evidence = dict(scope='Project-authored audiovisual materials, user-authorized reuse and editing',
                    authorship='Project generated Blender geometry, scenes, renders and Remotion composition; no third-party mesh or audiovisual footage was imported.',
                    sources=[binding(BASE.with_suffix('.3d-provenance.json')),
                             binding(ROOT/'output/tasks/production-1794969915231117000/asset/source-observations-v1.json')],
                    limitations='Patent is research evidence; rights in the patent and correspondence to retail products are not established.')
    writejson(proof_path, evidence)
    rights = dict(status='VERIFIED', name='Project-generated audiovisual material', holder='Project author',
                  editing_and_distribution=True, commercial_use=True,
                  proof=dict(binding(proof_path), position='scope and authorship'))
    credit = '原理示意 · 原创素材'
    references = {s['shot_id']: s for s in prior['shots']}
    clips = {sid: bound(s['render_output']) for sid,s in references.items()}
    existing = clips['apply']
    library = OUT/'reference-library'
    library_rights = dict(rights, usage_scopes=['teaching_demo'], usage_restrictions=[])
    quality_review = OUT/'qa-v2/source-sample-review.md'
    reviewed = quality_review.is_file()
    metadata = dict(source_type='OWNED', origin='project', project_id='correction-tape',
                    tags=['correction-tape'], mechanism_knowledge=['application'], used_shots=[],
                    sources=['US8746316B2 Figs 1-3'], source_url=existing.as_uri(),
                    credit=credit, content_verified=True,
                    quality=dict(approved=reviewed, approval_scope='Single compressed frame only',
                                 review=binding(quality_review) if reviewed else None),
                    license=library_rights, segment=dict(start_sec=0, end_sec=4))
    receipt = ingest_media(metadata, existing, root=library)
    matched = match_media(dict(project_id='correction-tape', tags=['correction-tape'],
                               mechanism_knowledge=['application'], usage_scope='teaching_demo',
                               duration_sec=4, accepted_types=['video']), root=library)
    writejson(OUT/'hybrid-demo-v2.library-match.json', dict(ingest=receipt, result=matched,
              limitation='Sampled image quality only; continuous motion and audio remain UNKNOWN.'))
    if '--match-only' in sys.argv:
        return
    row = cfg['shots']['apply']['visual']
    row.update(render_engine='footage', mechanical_role='support', visual_type='product_exterior',
               camera=dict(scale='medium', angle='斜前方'))
    cfg['shots']['apply'] = dict(template='editorial', seconds=4, visual=row,
        footage=dict(binding(existing), source_url=existing.as_uri(), start_frame=0, license=rights, credit=credit))
    props['shots'][0]['footage'] = dict(credit=credit, startFrame=0)
    props['shots'][0].pop('scienceLabel', None)
    attempts = [dict(priority=1, result='Existing project source reviewed')]
    for chapter in cfg['storyboard']:
        sid = chapter['shot']
        visual = cfg['shots'][sid]['visual']
        generated = sid == 'film-route'
        asset = None if generated else clips[sid]
        matching = dict(attempts=attempts if not generated else [
            dict(priority=1, result='Prior project library has this exact authored recap, reused in concept'),
            dict(priority=2, result='Existing local footage is a 3D animation, not the requested process diagram'),
            dict(priority=3, result='No matching local licensed process diagram recorded'),
            dict(priority=4, result='No matching local stock diagram recorded'),
            dict(priority=5, result='No suitable external exact diagram established')],
            generation_reason='Original Remotion diagram already authored for this teaching recap; no external diagram reused.')
        visual.update(source_type='GENERATED' if generated else 'OWNED', source_url=None if generated else asset.as_uri(),
                      source_time_range=None if generated else [0, chapter['seconds']], license_status='VERIFIED',
                      usage_restrictions=['Patent and retail product correspondence are not established'],
                      selected_asset=None if generated else binding(asset), reuse_decision='GENERATE' if generated else 'REUSE',
                      generation_required=generated, license=rights, credit=credit, content_verified=True, matching=matching)
    validate_document(cfg)
    validate_config(cfg)
    props_path = OUT/'hybrid-demo-v2.props.json'
    target = OUT/'hybrid-demo-v2.mp4'
    writejson(props_path, props)
    writejson(OUT/'hybrid-demo-v2.config.json', cfg)
    media = {sid:(path, 'video', references[sid]['cache_key']) for sid,path in clips.items()}
    assets = prior['shots'][0]['model_assets']
    with lock(ROOT/'work/production.lock'):
        render(props_path, target, OUT/'hybrid-demo-v2.render.log', visual=True, encode_profile='witness-v1')
        validate_video(target, cfg, props['cues'])
        write_remotion_proof(OUT/'hybrid-demo-v2.hybrid-build.json', target, props_path,
                             cfg, media, bound(assets[0]), bound(assets[1]))
        write_manifest(OUT/'hybrid-demo-v2.media-provenance.json', target, cfg, OUT/'hybrid-demo-v2.hybrid-build.json')
    subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True)
    print(json.dumps({'path':str(target), 'sha256':filehash(target), 'status':'TECHNICAL_PASS_UNACCEPTED'}))


if __name__ == '__main__':
    main()
