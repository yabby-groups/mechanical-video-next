import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import production_contract as c
from mechanical_video_next.workflow import continuation, create_task, load, producer_prompt, put_handoff


class ProductionContractTests(unittest.TestCase):
    def test_pinned_director_registers_one_evidenced_story_and_resumes(self):
        import json
        from array import array
        import math
        import subprocess
        import sys
        import wave
        from types import SimpleNamespace
        from mechanical_video_next import blueprint, director, director_audio, joint_timeline as joint, reference_policy as references
        from mechanical_video_next import workflow as w

        with tempfile.TemporaryDirectory() as folder:
            task = create_task('行星齿轮', root=folder, visual_policy_version=2, media_policy_version=1,
                               story_development_version=0)
            data = load(task)
            self.assertTrue(c.producer_directed(data))
            first = continuation(task, persist=False)['next_action']
            self.assertEqual((first['owner'], first['handoff']), ('Producer', 'viral-analysis'))
            search = json.loads(Path(first['search_plan']).read_text())
            self.assertEqual([query['platform'] for query in search['queries']],
                             ['douyin', 'xiaohongshu', 'bilibili', 'youtube'])
            prompt = (task / 'producer-prompt.md').read_text()
            self.assertNotIn('EDITORIAL', prompt)
            self.assertIn('.agents/skills/director/SKILL.md', prompt)
            self.assertEqual(load(task)['timeline_policy_version'], 1)
            w.advance(task, 'RESEARCHING')
            source = task / 'manual.txt'
            source.write_text('With a fixed ring, the carrier rotates more slowly than the sun gear.')
            evidence = dict(path=str(source), sha256=w.filehash(source), position='Operating instructions')
            viewing_note = task / 'reference-observation.txt'
            viewing_note.write_text('Integration fixture: 2–4s, move from the whole tool to the output.')
            observed = '2026-11-20T08:00:00+08:00'
            candidate = dict(id='ref', url='https://youtu.be/fixture', observed_at=observed,
                             observations=['2–4s: Go from whole tool to the output'],
                             transfer_rationale='Reframe around the slow carrier',
                             techniques=[dict(id='reveal', source_range=[2, 4], visual_method='Hold the input in view',
                                              use_condition='Input and output share the frame',
                                              viewer_effect='See both speeds', implementation='Existing overview camera')],
                             viewing=dict(status='PARTIAL_VIDEO_VIEWED', time_ranges=[[2, 4]],
                                          limitation='Only the transition was observed',
                                          evidence=[joint.binding(viewing_note)]))
            put_handoff(task, 'ViralResearch', 'viral-analysis',
                        dict(task_id=data['id'], topic=data['topic'], observed_at=observed,
                             candidates=[candidate], selected_ids=['ref']))
            self.assertEqual(continuation(task, persist=False)['next_action']['handoff'], 'research')
            research = {key: data[key] for key in (c.FIELD, c.PRODUCER_DIRECTION, 'production_contract', 'production_method',
                                                  'visual_policy_version', 'media_policy_version')}
            fact = dict(id='reduction', status='VERIFIED', kind='observed', claim=source.read_text(),
                        scope='One mechanism', assumptions=[], sources=[evidence])
            research.update(mechanism_id='fixture', science=dict(subject_kind='mechanical_implementation',
                            question='Why does the carrier turn more slowly?', answer=fact['claim'],
                            scope=fact['scope'], facts=[fact]), references=[
                dict(id='manual', location=str(source), source_name='Manual', author='Fixture',
                     type='manual', acquired_at='2026-11-20', structure_evidence='Fixed ring',
                     motion_evidence='Reduction', license='REFERENCE_ONLY', usable_content='Description',
                     mechanism_id='fixture', unresolved_core_conflict=False, unknowns=[], conflicts=[],
                     viewed_scope=dict(status='DOCUMENT_READ', evidence=evidence))])
            research['audience_decision'] = dict(
                question=research['science']['question'], daily_context='Turn a geared handle',
                design_tension='Fit a speed reduction around one axis',
                visible_test='Compare marked travel', viewer_takeaway='The fixed ring changes the output speed',
                selection_rationale='One input and output make the reduction visible')
            research['director'] = dict(
                selected='direct_experiment', selection_reason='Marked rotation is directly observable',
                treatments={
                    name: dict({field: f'{field} for {name}' for field in director.TREATMENT},
                               question=research['science']['question'])
                    for name in director.APPROACHES})
            with self.assertRaisesRegex(ValueError, 'production method'):
                put_handoff(task, 'Producer', 'research', research | {'production_method': 'science-story'})
            with self.assertRaisesRegex(ValueError, 'Located visual evidence'):
                put_handoff(task, 'Producer', 'research',
                            research | {'science': research['science'] | {'facts': [fact | {'sources': []}]}})
            put_handoff(task, 'Producer', 'research', research)
            resumed = continuation(task, persist=False)
            self.assertEqual(resumed['next_action']['handoff'], 'asset-plan')
            remaining = {row['handoff'] for row in resumed['remaining_work']}
            self.assertTrue({'reference-model-qa', 'content-qa', 'preview-qa', 'final-qa'} <= remaining)
            self.assertFalse({'diagnostic-animatic', 'diagnostic-qa', 'animatic-qa'} & remaining)
            with self.assertRaisesRegex(ValueError, 'Missing handoff: creative-blueprint'):
                w.require_animatic(task)
            with self.assertRaisesRegex(ValueError, 'Missing handoff: animation-manifest'):
                w.check_qa(task, 'preview-qa')
            with self.assertRaisesRegex(ValueError, 'Missing handoff: timeline'):
                w.check_qa(task, 'final-qa')

            base = Path('tests/fixtures/production/science-demo.json')
            cfg = json.loads(base.read_text())
            native = cfg['shots']['trace']
            action = dict(id='rotate', start_frame=0, end_frame=180, source_start_frame=0, source_end_frame=180,
                          start_state='At rest', end_state='Slow carrier', input='Sun gear turns',
                          direction='Carrier follows the input', transmission='Planet gears on the fixed ring',
                          intermediate_state='Both marked datums rotate', contact='Planet and ring mesh',
                          knowledge_id='reduction', curve='Native gear track', constraints=['Fixed ring'],
                          source=joint.binding(base), evidence=evidence,
                          shot_programs={'trace': director.action_program_digest(native)})
            timeline = dict(film_integrity_version=1, frame_count=210,
                            shots=[dict(id='trace', start_frame=0, end_frame=210, action_views={'rotate': 0})],
                            actions=[action], narration=[dict(id='line', text='看行星架', knowledge_ids=['reduction'],
                                                        start_frame=0, deadline_frame=30)])
            sample = task / 'speech.wav'
            with wave.open(str(sample), 'wb') as wav:
                wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                wav.writeframes(array('h', (int(7000 * math.sin(2 * math.pi * 440 * sample / 48000))
                                           for sample in range(24000))).tobytes())
            measured = joint.measure(timeline, lambda line: (sample, {}), task / 'narration.wav')
            w.write(task / 'timing.json', measured)
            shot = dict(shot_id='trace', time_range=[0, 7], duration=7, asset=cfg['asset'],
                        existing_shot='trace', template=cfg['shots']['trace']['template'],
                        overlays=[], knowledge_goal='See the output', mechanical_action='Carrier rotates',
                        visual_type='state_change', render_engine='blender', mechanical_role='core',
                        camera=dict(scale='wide', angle='oblique', preset='establish'),
                        visual_focus='Carrier', visual_action='Rotation', assets=[cfg['asset']],
                        direction=dict(why_visual='See the two speeds', composition='Both centers in frame',
                                       lighting='Keep the carrier legible', continuity='Hold through one turn',
                                       sound_intent='Leave time to inspect the comparison',
                                       studio_lighting=dict(world_color=[.08, .10, .15], preserve_materials=True)),
                        evidence=cfg['shots']['trace']['science']['basis'], knowledge_ids=['reduction'],
                        transition=dict(kind='cut', link='Carrier'), progression=dict(kind='new', reason='Output'),
                        feasibility_evidence=[evidence], source_type='GENERATED', source_url=None,
                        source_time_range=None, license_status='VERIFIED', usage_restrictions=[],
                        selected_asset=None, reuse_decision='GENERATE', generation_required=True,
                        license=dict(status='VERIFIED', name='Owned fixture', holder='Fixture',
                                     editing_and_distribution=True, commercial_use=True, proof=evidence),
                        credit='Fixture', content_verified=True,
                        matching=dict(attempts=[dict(priority=i, status='NONE') for i in range(1, 6)],
                                      generation_reason='Use matching native model'))
            question = research['science']['question']
            shot['director'] = dict(
                {field: f'Observe {field}' for field in director.SHOT},
                visual_focus='Carrier', strategy='source_observation',
                edits=[dict(kind='cut', frame=0, purpose='Introduce both rotating parts')],
                candidates=[dict(route='native_3d', basis='Verified output geometry',
                                 accuracy=4, expression=4, intent=4, availability=4,
                                 style=4, estimated_seconds=30, estimated_cost=0)])
            policy = {key: research[key] for key in (c.FIELD, c.PRODUCER_DIRECTION, 'production_contract', 'production_method',
                                                      'visual_policy_version', 'media_policy_version')}
            plan = dict(policy, timeline_policy_version=1, reference_policy_version=1, status='FROZEN',
                        timeline=timeline, measured_timeline=joint.binding(task / 'timing.json'),
                        narrative=dict(question=question, answer=fact['claim'], moments={
                            key: dict(shot_id='trace', start_frame=i * 30, end_frame=(i + 1) * 30,
                                      observable='Watch the carrier against the rings', knowledge_id='reduction',
                                      mechanical_event_id='rotate')
                            for i, key in enumerate(('opening', 'first_discovery', 'causal_reveal',
                                                     'scientific_explanation', 'action_result', 'payoff'))}), core_question=question,
                        original_topic=data['topic'], duration_seconds=7, sources=[evidence], shots=[shot],
                        evidence_map=[dict(knowledge_id='reduction', conclusion=fact['claim'], source_ids=['manual'],
                                           reference_locations=[dict(source_id='manual', position='Instructions')],
                                           parts=['Carrier'], actions=['Rotation'], usable_material='Native model',
                                           shot_ids=['trace'], verification_method='Inspect', verified=True)],
                        content_timing=dict(basis='Measured timeline', status='PASS', measured_narration_seconds=.5,
                                            chapters=[dict(id='trace', knowledge_ids=['reduction'],
                                                           new_information='Output', duration_reason='Action')]))
            plan[director.FIELD] = director.VERSION
            plan.update({key: data[key] for key in director_audio.POLICY_FIELDS})
            plan['music_direction'] = {'mode': 'silence', 'reason': 'Keep the speed comparison quiet.'}
            plan['director'] = research['director']
            model = task / 'model.blend'
            model.write_bytes(b'fixture model')
            model_ref = joint.binding(model)
            candidate = dict(strategy='verified-existing', id='model', reason='Exact embodiment', qualified=True,
                             source_ids=['manual'], mechanism_id='fixture', validation_evidence=[evidence],
                             legal_use=True, content_match=True, source_files=[model_ref])
            asset = dict(policy, mechanism_id='fixture', strategy=candidate['strategy'], selected_candidate_id='model',
                         candidates=[dict(strategy='existing-media', reason='No match'), candidate],
                         model=model_ref, model_source=evidence, substantive_repairs=[],
                         qualified=True, independent_meshes=True, missing_required_parts=[])
            put_handoff(task, 'Asset', 'asset-plan', asset, ['research'])
            dependencies = ['research', 'asset-plan', 'viral-analysis']
            with self.assertRaisesRegex(ValueError, 'adapt the selected observations'):
                put_handoff(task, 'Producer', 'creative-blueprint', plan, dependencies)
            plan['reference_principles'] = [dict(reference_id='ref', principle='Reveal output after establishing scale',
                                                 technique_id='reveal', expected_observable_effect='See the speed contrast',
                                                 production_requirement='Hold the full view with the carrier visible',
                                                 shot_ids=['trace'])]
            plan_path, config_path = task / 'plan.json', task / 'compiled.json'
            w.write(plan_path, plan)
            blueprint.compile_config(plan_path, base, config_path)
            lighting = json.loads(config_path.read_text())['shots']['trace']['studio_lighting']
            self.assertFalse(lighting['camera_push'])
            self.assertTrue(lighting['preserve_materials'])
            self.assertEqual(lighting['world_color'], [.08, .10, .15])
            self.assertEqual(lighting['floor_color'], [.34, .38, .42])
            pilot = create_task('Same science, different edit', root=folder, visual_policy_version=2,
                                media_policy_version=1, skill_driven_pilot=True,
                                story_development_version=0)
            pilot_research = dict(research, production_method=c.SKILL_DRIVEN)
            del pilot_research['audience_decision'], pilot_research['director']
            put_handoff(pilot, 'Producer', 'research', pilot_research)
            pilot_asset = dict(asset, production_method=c.SKILL_DRIVEN, candidates=[candidate])
            put_handoff(pilot, 'Asset', 'asset-plan', pilot_asset, ['research'])
            flexible = copy.deepcopy(plan)
            flexible.update(production_method=c.SKILL_DRIVEN, chapters=[
                dict(title='Cold open', shot_ids=['trace']),
                dict(title='Return to the same image', shot_ids=['trace']),
            ])
            del flexible[director.FIELD], flexible['director'], flexible['reference_principles']
            del flexible['content_timing']['chapters']
            moment = flexible['narrative']['moments']['causal_reveal']
            flexible['narrative']['moments'] = {'watch-the-output': moment}
            new_shot = flexible['shots'][0]
            for key in ('director', 'progression', 'transition'):
                del new_shot[key]
            new_shot['visual_type'] = 'single-take observer experiment'
            pilot_plan, pilot_config = pilot / 'plan.json', pilot / 'compiled.json'
            w.write(pilot_plan, flexible)
            blueprint.compile_config(pilot_plan, base, pilot_config)
            compiled = json.loads(pilot_config.read_text())
            self.assertEqual(compiled[director_audio.MIX_MODE_FIELD], data[director_audio.MIX_MODE_FIELD])
            self.assertEqual(compiled['chapters'], flexible['chapters'])
            self.assertEqual(director.action_program_digest(compiled['shots']['trace']),
                             director.action_program_digest(native))
            flexible['production_config'] = joint.binding(pilot_config)
            put_handoff(pilot, 'Producer', 'creative-blueprint', flexible, ['research', 'asset-plan'])
            self.assertEqual(load(pilot)['config'], str(pilot_config.resolve()))
            plan['production_config'] = joint.binding(config_path)
            handoff = put_handoff(task, 'Producer', 'creative-blueprint', plan, dependencies)
            self.assertEqual(handoff['dependencies']['viral-analysis'], load(task)['handoffs']['viral-analysis']['sha256'])
            self.assertEqual(load(task)['config'], str(config_path.resolve()))
            self.assertEqual(load(task)['shared_production']['timeline'], plan['measured_timeline'])
            put_handoff(task, 'Producer', 'script', {'narration': timeline['narration']},
                        ['research', 'creative-blueprint'])
            with self.assertRaisesRegex(ValueError, 'Missing handoff: reference-model-qa'):
                w.require_animatic(task)
            part = dict(part_id='carrier', source_locations=[dict(source_id='manual', position='Instructions')],
                        cad_parts=['Carrier'], function='Output', connections='Planet pins', motion_constraints='Axis',
                        verification=dict(status='PASS', evidence='Fixture'))
            mechanical_qa = dict(mechanism_id='fixture', depicted_type='native', scope='Fixed ring',
                                 bindings=[model_ref], parts=[part], independent=True, reviewer_thread_id='qa',
                                 motion_basis=evidence, dimensions_basis=evidence, no_model_mixing=True,
                                 unresolved_core_issues=[], consistency_checks={
                                     key: dict(status='PASS', evidence='Fixture')
                                     for key in ('appearance', 'key_parts', 'connections', 'input_action',
                                                 'transmission', 'output_action', 'work_and_reset',
                                                 'exploded_relationships')})
            put_handoff(task, 'QA', 'reference-model-qa', mechanical_qa, ['research', 'asset-plan'])
            content_qa = dict(reviewer_role='QA', independent=True,
                              reviewer_thread_id='qa',
                              plan_sha256=references.plan_digest(plan, research, asset),
                              content_checks={key: dict(status='PASS', evidence='Fixture')
                                              for key in references.CONTENT_CHECKS})
            put_handoff(task, 'QA', 'content-qa', content_qa,
                        ['research', 'asset-plan', 'creative-blueprint', 'reference-model-qa'])
            put_handoff(task, 'Producer', 'feasibility', {'checks': dict.fromkeys(w.FEASIBILITY_CHECKS, 'PASS')},
                        ['research', 'asset-plan', 'creative-blueprint'])
            w.advance(task, 'ASSET_READY')
            w.advance(task, 'ANIMATING')
            self.assertIsNone(w.require_animatic(task))
            self.assertEqual(continuation(task, persist=False)['next_action']['handoff'], 'animation-manifest')
            preview = task / 'preview.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'testsrc2=size=320x180:rate=30:duration=7',
                '-i', str(task / 'narration.wav'),
                '-c:v', 'libx264', '-c:a', 'aac', str(preview),
            ], check=True)
            preview_media = dict(joint.binding(preview), chapter_ids=['trace'])
            media_dependencies = ['research', 'asset-plan', 'creative-blueprint', 'feasibility']
            put_handoff(task, 'Animation', 'animation-manifest',
                        dict(media=[preview_media], keyframes_verified=True),
                        media_dependencies)
            with self.assertRaisesRegex(ValueError, 'Video Review UNKNOWN'):
                w.check_qa(task, 'preview-qa', acceptance=False)
            self.assertEqual(continuation(task, persist=False)['next_action']['owner'], 'Producer')

            public = task.parents[2] / 'remotion/public'
            public.mkdir(parents=True)
            plate = public / 'source.mp4'
            plate.write_bytes(preview.read_bytes())
            measured = joint.receipt(timeline, plan['measured_timeline'])

            def bind_review_sources(movie):
                props_path = movie.with_suffix('.props.json')
                w.write(props_path, dict(cues=joint.cues(measured),
                                         shots=[dict(id='trace', seconds=7, media=plate.name)]))
                w.write(movie.with_suffix('.review-sources.json'),
                        dict(media=joint.binding(movie), props=joint.binding(props_path),
                             shots={'trace': {'video': joint.binding(plate)}}))

            bind_review_sources(preview)
            with patch.object(w, 'ROOT', task.parents[2]):
                approved = put_handoff(task, 'Animation', 'animation-manifest',
                                       dict(media=[preview_media], keyframes_verified=True), media_dependencies)
                self.assertEqual(approved['payload']['video_review']['technical_status'], 'PASS')
            probe = dict(streams=[
                dict(codec_type='video', avg_frame_rate='30/1', duration='7', width=1920, height=1080),
                dict(codec_type='audio', duration='7')])
            with patch('mechanical_video_next.multiroute.probe', return_value=probe):
                for state in ('PREVIEW_READY', 'PREVIEW_CHECKING'):
                    w.advance(task, state)
                with self.assertRaisesRegex(ValueError, 'Missing handoff: preview-qa'):
                    w.advance(task, 'EDITING')
                observation = dict(media_sha256=preview_media['sha256'], time_range=[0, 7],
                                   status='UNKNOWN', observation='Fixture cannot establish perception',
                                   capability_boundary='Technical fixture')
                preview_report = dict(
                    media=[preview_media], independent_reviewer=True, reviewer_thread_id='qa',
                    checks=dict.fromkeys(w.QA_CHECKS, 'PASS') | {'listening': 'UNKNOWN'},
                    creative_review={key: observation for key in c.CREATIVE_CHECKS},
                    reference_effects=[observation | dict(reference_id='ref', technique_id='reveal',
                                                          shot_id='trace', limitation='Fixture')])
                put_handoff(task, 'QA', 'preview-qa', preview_report, ['animation-manifest'])
                with self.assertRaisesRegex(ValueError, 'time-covered review observations'):
                    w.advance(task, 'EDITING')
                detail = observation | dict(status='PASS', method='continuous_video', shot_id='trace',
                                            reviewer_thread_id='qa', knowledge_ids=shot['knowledge_ids'])
                preview_report['review_observations'] = [
                    detail | dict(id='motion', dimension='mechanical_motion', source_comparison='Test fixture',
                                  mechanical_event_ids=[event['id'] for event in timeline['actions']]),
                    detail | dict(id='story', dimension='narrative_comprehension',
                                  story_moment_ids=list(plan['narrative']['moments'])),
                ]
                put_handoff(task, 'QA', 'preview-qa', preview_report, ['animation-manifest'])
                w.advance(task, 'EDITING')
            self.assertEqual(load(task)['state'], 'EDITING')
            # Exercise the stage and ledger with actual fixture media in place of a fresh render.
            compiled = json.loads(config_path.read_text())
            final = task.parents[1] / (compiled['id'] + '-final.mp4')
            with (patch.object(w, 'ROOT', task.parents[2]),
                  patch.object(w, 'subprocess', SimpleNamespace(
                      run=lambda *a, **kw: final.write_bytes(preview.read_bytes()),
                      STDOUT=subprocess.STDOUT, CalledProcessError=subprocess.CalledProcessError)),
                  patch.dict(sys.modules, {'clean': SimpleNamespace(cleanup=lambda **kw: None)}),
                  patch('mechanical_video_next.multiroute.probe', return_value=probe)):
                w.run_stage(task, 'final', config_path)
                media = load(task)['route_runs']['3d']['outputs']
                self.assertEqual(media, dict(joint.binding(final), chapter_ids=['trace']))
                bind_review_sources(final)
                put_handoff(task, 'Editor', 'timeline', dict(media=[media], technical_pass=True),
                            ['script', 'animation-manifest'])
                w.advance(task, 'FINAL_CHECKING')
                self.assertEqual(continuation(task, persist=False)['production_status'], 'FINAL_QA_PENDING')
                with self.assertRaisesRegex(ValueError, 'Missing handoff: final-qa'):
                    w.advance(task, 'COMPLETED')
            shot['source_type'] = 'REFERENCE_ONLY'
            with self.assertRaisesRegex(ValueError, 'editing/distribution rights'):
                blueprint.validate(plan)

    def test_reference_access_limit_continues_and_existing_policies_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            task = create_task('棘轮扳手', root=folder, visual_policy_version=2, media_policy_version=1,
                               story_development_version=0)
            observed = '2026-11-20T08:00:00+08:00'
            put_handoff(task, 'Producer', 'viral-analysis', dict(
                task_id=task.name, topic='棘轮扳手', observed_at=observed, candidates=[], selected_ids=[],
                limitation='Playback unavailable across the accessible results, and cache only has page evidence'))
            for _ in range(2):
                result = continuation(task)
                self.assertEqual(result['lifecycle'], 'WORKING')
                self.assertEqual(result['next_action']['handoff'], 'research')
                self.assertNotIn('viral-analysis', {row['handoff'] for row in result['remaining_work']})
            history = create_task('棘轮扳手', root=folder, visual_policy_version=2, media_policy_version=1,
                                  contract_version=6)
            self.assertEqual(continuation(history)['next_action']['handoff'], 'research')
            self.assertNotIn('reference_search_plan', load(history))
            self.assertIn('EDITORIAL', (history / 'producer-prompt.md').read_text())

    def test_pinned_mechanical_story_rejects_unanchored_research_and_preserves_v4(self):
        from scripts.common import filehash

        with tempfile.TemporaryDirectory() as folder:
            task = create_task('雨伞', root=folder, visual_policy_version=2, media_policy_version=1,
                               contract_version=c.MECHANICAL_STORY_VERSION)
            data = load(task)
            self.assertEqual(data['production_contract'], c.MECHANICAL_STORY_NAME)
            self.assertEqual(data['visual_direction_version'], 1)
            self.assertEqual(data['timeline_policy_version'], 1)
            self.assertIn('君哥拆机器', producer_prompt(data, task))
            self.assertIn('mechanical design', continuation(task, persist=False)['next_action']['action'])
            policy = dict(production_contract_version=data[c.FIELD], production_contract=data['production_contract'],
                          visual_policy_version=2, media_policy_version=1)
            question = 'How does the geometry bend light?'
            decision = dict.fromkeys(c.CREATIVE_DECISION + ('visual_approach',), 'Specific choice')
            decision['question'] = question
            source = Path(folder) / 'fixture.txt'
            source.write_text('Evidence binding fixture')
            fact = dict(id='geometry', claim='Geometry changes the light path', kind='scientific_fact',
                        status='VERIFIED', scope='One model', assumptions=[],
                        sources=[dict(path=str(source), sha256=filehash(source), position='line 1')])
            candidate = dict(id='geometry', question=question, angle='comparison', visual_test='Change one input',
                             decision_reason='Separates the inputs', fact_ids=['geometry'])
            research = dict(policy, science=dict(subject_kind='physical_phenomenon', question=question,
                            answer='A bounded optical model', scope='One model', facts=[fact],
                            subject=dict(id='model', name='Light path', scope='One model', model_kind='mathematical')),
                            audience_decision=decision, story_exploration=dict(angles={'geometry': 'One approach'},
                            candidates=[candidate], selected_id='geometry', shortlist_limit='One supported approach'))
            with self.assertRaisesRegex(ValueError, 'Mechanical stories need'):
                put_handoff(task, 'Research', 'research', research)
            self.assertEqual(load(task)['handoffs'], {})
            historic = dict(research, production_contract_version=c.DISCOVERY_VERSION,
                            production_contract=c.DISCOVERY_NAME)
            self.assertIn('geometry', c.validate_research(historic))

            science = research['science']
            science['subject_kind'] = 'documented_technology'
            science['subject'].update(name='Adjustable lens mount', model_kind='documented')
            with self.assertRaisesRegex(ValueError, 'mechanical_focus'):
                put_handoff(task, 'Research', 'research', research)
            candidate['mechanical_focus'] = 'A lens carriage moves along a threaded mount to change lens spacing.'
            self.assertIn('geometry', c.validate_research(research))

    def test_science_story_checks_the_whole_edit_and_preserves_v2_review(self):
        report = {'creative_review': {key: dict(status='PASS', media_sha256='cut', time_range=[0, 4],
                           method='continuous_audiovisual', observation='Observed visual and audio progression',
                           capability_boundary='Exact animatic') for key in c.CREATIVE_CHECKS}}
        c.validate_creative_review(report, {'cut': 24}, acceptance=True)
        with self.assertRaisesRegex(ValueError, 'whole edit'):
            c.validate_creative_review(report, {'cut': 24}, acceptance=True, whole_edit=True)
        for key in ('pace', 'visual_tasks', 'voice_and_sound'):
            report['creative_review'][key]['time_range'] = [0, 24]
        c.validate_creative_review(report, {'cut': 24}, acceptance=True, whole_edit=True)
        report['creative_review']['payoff']['status'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'remains UNKNOWN'):
            c.validate_creative_review(report, {'cut': 24}, acceptance=True, whole_edit=True)

    def test_compose_filters_only_natural_fullframe_labels_and_preserves_credits(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import produce

        class PropsReady(Exception):
            pass

        for style, caption, expected in (
                ('natural_science', '原理示意 · 摩擦力大小未模拟', '摩擦力大小未模拟'),
                ('natural_science', '原理示意', None),
                (None, '模型示意｜仅比较运动方向', '仅比较运动方向'),
                ('legacy', '原理示意', '原理示意')):
            cfg = dict(title='A concrete question', subtitle='A causal answer', voice='Ting-Ting',
                       presentation='mechanism-fullframe',
                       fullframe_caption=caption, fullframe_credit='Source: original evidence',
                       render=dict(width=1920, height=1080), storyboard=[], shots={})
            if style:
                cfg['presentation_style'] = style
            with self.subTest(style=style, caption=caption), \
                    patch('narration.effective_profile', return_value=None), \
                    patch('mechanical_video_next.style_lock.verify_lock', return_value={'status': 'PASS'}), \
                    patch('mechanical_video_next.text_layout.prepare_text_props', side_effect=PropsReady) as prepare:
                with self.assertRaises(PropsReady):
                    produce.compose(cfg, 'preview', {}, None)
                props = prepare.call_args.args[0]
                self.assertEqual(props.get('fullframe_caption'), expected)
                self.assertEqual(props['fullframe_credit'], cfg['fullframe_credit'])

    def test_audience_decision_binds_the_opening_and_payoff(self):
        plan = dict(production_contract_version=1, production_contract=c.NAME,
                    media_policy_version=1, visual_policy_version=2,
                    narrative=dict(question='Why?', tension='A contradiction', answer='Because', arc_reason='Comparison'),
                    shots=[dict(shot_id=sid, direction={k:'Concrete decision' for k in c.DIRECTION})
                           for sid in ('opening', 'answer')])
        c.validate_direction(plan)
        decision = dict(daily_context='Everyday use', opening_visual='Visible action',
                        viewer_takeaway='A causal answer', selection_rationale='A familiar question',
                        opening_shot_id='opening', payoff_shot_id='answer')
        plan['narrative']['audience_decision'] = decision
        c.validate_direction(plan)
        for changes in ({'opening_shot_id': 'answer'}, {'payoff_shot_id': 'missing'},
                        {'selection_rationale': ''}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'Audience decision'):
                plan['narrative']['audience_decision'] = decision | changes
                c.validate_direction(plan)

    def test_natural_copy_distinguishes_production_labels_from_scientific_limits(self):
        from mechanical_video_next.science_information import information_props
        c.validate_audience_copy({
            'narration': ['只看运动方向，摩擦力大小还要另测。'],
            'overlays': ['模型按等速带入计算', '压头'],
        })
        with self.assertRaisesRegex(ValueError, 'classroom'):
            c.validate_audience_copy({'narration': ['下面我们来学习修正带。']})
        with self.assertRaisesRegex(ValueError, 'production label'):
            c.validate_audience_copy({'science': {'print_marks': [{'text': '教学模型'}]}})
        shot = {'science': {'mode': 'conceptual'}}
        self.assertEqual(information_props(shot, {}, None, 'video', natural=False)['scienceLabel'], '原理示意')
        self.assertIsNone(information_props(shot, {}, None, 'video')['scienceLabel'])
        self.assertEqual(shot['science']['mode'], 'conceptual')

    def test_mechanical_review_reuse_tracks_only_its_real_dependencies(self):
        from mechanical_video_next.reference_policy import model_program_digest
        with tempfile.TemporaryDirectory() as folder:
            assembly=Path(folder)/'assembly.json';assembly.write_text('{"parts":["A"]}')
            cfg=dict(assembly_config=str(assembly),shots={'core':dict(template='state_transition',seconds=4,tracks=[{'object':'A','poses':[]}],visual={'knowledge_goal':'A'}),
                'chart':dict(template='editorial',graphic={'value':1})},storyboard=[{'narration':['Original']}])
            before=model_program_digest(cfg)
            cfg['storyboard'][0]['narration']=['Caption correction']
            cfg['shots']['chart']['graphic']['value']=2
            self.assertEqual(model_program_digest(cfg),before)
            cfg['shots']['core']['camera_direction']=[1,1,1]
            self.assertNotEqual(model_program_digest(cfg),before)
            changed=model_program_digest(cfg);assembly.write_text('{"parts":["A","B"]}')
            self.assertNotEqual(model_program_digest(cfg),changed)

    def test_new_hybrid_pins_contract_and_legacy_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            task = create_task('Why?', root=folder, task_id='mixed', visual_policy_version=2,
                               media_policy_version=1, contract_version=1)
            data = load(task)
            self.assertTrue(c.enabled(data))
            self.assertIn('mixed-original-v1', producer_prompt(data,task))
            legacy = load(create_task('Old',root=folder,task_id='old'))
            self.assertFalse(c.enabled(legacy))
            data['media_policy_version']=0
            with self.assertRaises(ValueError): c.enabled(data)

    def test_creative_first_duration_and_blueprint_cannot_migrate_v1(self):
        from mechanical_video_next.growth import duration_bounds
        from mechanical_video_next.visual_narrative import match_policy
        with tempfile.TemporaryDirectory() as folder:
            options = dict(root=folder, visual_policy_version=2, media_policy_version=1)
            path = create_task('Why?', 150, task_id='creative', **options)
            current = load(path)
            historic = load(create_task('Why?', 120, task_id='historic', contract_version=1, **options))
            self.assertTrue(c.creative_first(current))
            self.assertEqual(duration_bounds(current), (60, float('inf')))
            self.assertIsNone(current['duration_policy']['maximum'])
            self.assertEqual(duration_bounds(historic), (120, 300))
            self.assertIn('native Blender 3D', producer_prompt(current, path))
            with self.assertRaisesRegex(ValueError, 'creation policy'):
                match_policy(historic, current)
            with self.assertRaises(ValueError):
                create_task('Why?', 64, task_id='short-v1', contract_version=1, **options)

    def test_creative_direction_requires_daily_question_and_long_mechanism_run_reason(self):
        question = 'Why does the liquid rise?'
        decision = {key: 'Specific choice' for key in c.CREATIVE_DECISION}
        decision.update(question=question, opening_shot_id='sink', payoff_shot_id='return')
        shots = [dict(shot_id=key, visual_type=kind, direction={field: 'Concrete' for field in c.DIRECTION})
                 for key, kind in [('sink', 'product_exterior'), ('reveal', 'mechanical_cutaway'),
                                   ('valve', 'annotated_detail'), ('exit', 'mechanical_cutaway'),
                                   ('return', 'everyday_return')]]
        plan = dict(production_contract_version=2, production_contract=c.CREATIVE_FIRST_NAME,
                    media_policy_version=1, visual_policy_version=2, shots=shots,
                    narrative=dict(question=question, tension='Opposite directions', answer='Two phases',
                                   arc_reason='Same bottle', audience_decision=decision))
        with self.assertRaisesRegex(ValueError, 'uninterrupted'):
            c.validate_direction(plan)
        shots[1]['direction']['continuous_mechanism_reason'] = 'Follow one liquid path through both valves'
        c.validate_direction(plan)
        decision['opening_visual'] = ''
        with self.assertRaisesRegex(ValueError, 'Audience decision'):
            c.validate_direction(plan)

    def test_sampled_creative_review_can_record_unknown_only(self):
        sample = dict(status='UNKNOWN', method='sampled_frames', media_sha256='film',
                      time_range=[0, 2], observation='Opening action appears in one sample',
                      capability_boundary='No continuous video or audio')
        report = {'creative_review': {key: dict(sample) for key in c.CREATIVE_CHECKS}}
        c.validate_creative_review(report, {'film': 3}, acceptance=False)
        with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
            c.validate_creative_review(report, {'film': 3}, acceptance=True)
        report['creative_review']['opening']['status'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'continuous'):
            c.validate_creative_review(report, {'film': 3}, acceptance=False)

    def test_unknown_fact_is_local_and_cannot_enter_dependent_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.txt'; source.write_text('Located evidence')
            from scripts.common import filehash
            fact = dict(id='known',claim='A visible relationship',status='VERIFIED',kind='observed',
                        scope='This example',assumptions=[],sources=[dict(path=str(source),sha256=filehash(source),position='paragraph 1')])
            unknown = dict(fact,id='unknown',status='UNKNOWN',limitation='Hidden contact unobserved')
            research = {'science':dict(subject_kind='mechanical_implementation',question='Why?',answer='Because',scope='Example',facts=[fact,unknown])}
            c.validate_research(research)
            plan = dict(production_contract_version=1,production_contract=c.NAME,media_policy_version=1,visual_policy_version=2,
                        narrative=dict(question='Why?',tension='A contradiction',answer='Because',arc_reason='Comparison'),
                        shots=[dict(knowledge_ids=['known'],direction={k:'Concrete decision' for k in c.DIRECTION})])
            c.validate_direction(plan,research)
            plan['shots'][0]['knowledge_ids']=['unknown']
            with self.assertRaisesRegex(ValueError,'dependent shot'): c.validate_direction(plan,research)
            fact['sources'][0]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'changed'): c.validate_research(research)

    def test_six_dimensions_never_grant_missing_senses(self):
        media=[dict(path='actual.mp4',sha256='a'*64)]
        report=dict(quality_dimensions={k:dict(status='PASS',media_sha256='a'*64,observation='Observation') for k in c.DIMENSIONS})
        c.validate_qa(report,media,acceptance=False)
        with self.assertRaisesRegex(ValueError,'viewing and listening'): c.validate_qa(report,media,acceptance=True)
        report.update(full_video_reviewed=True,full_audio_listened=True)
        with self.assertRaisesRegex(ValueError,'review observations'):
            c.validate_qa(report,media,acceptance=True)
        report['quality_dimensions']['mechanical_motion']['status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'prevents acceptance'): c.validate_qa(report,media,acceptance=True)

    def test_physical_phenomenon_uses_bounded_subject_without_fake_product(self):
        from mechanical_video_next.comprehension import validate_product_plan
        from scripts.common import filehash
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.txt';source.write_text('Contract fixture for an ideal constant-speed mathematical model; not production evidence.')
            subject=dict(id='constant-speed',name='等速位移',scope='Ideal constant speed only',model_kind='mathematical')
            claims=['Distance equals speed times elapsed time','Equal time intervals give equal distances']
            refs=[dict(reference_id='physics',supported_claims=claims,evidence=[dict(path=str(source),sha256=filehash(source),position='Complete fixture')])]
            plan=dict(production_contract_version=1,production_contract=c.NAME,media_policy_version=1,visual_policy_version=2,
                subject_kind='physical_phenomenon',subject_identity=subject,subject_references=refs,
                subject_opening=dict(shot_id='a',time_range=[0,3],subject_reveal='等速位移',real_action='Equal distances',why_question='Why?',answer_promise='Constant speed'),shots=[])
            for i,sid in enumerate(('a','b')):
                row=dict(reference_ids=['physics'],product_parts=['model marker'],input_action=claims[i],transmission=claims[i],output_action=claims[i],
                    visual_evidence='Position changes',narration=claims[i],new_knowledge=claims[i],necessity='Isolate time',causal_link='s=vt',
                    recognition_relations=['phenomenon','conditions'] if i==0 else ['model','causal_test','return_to_question'],verification_method='Observe model and check assumptions',
                    causal_evidence={k:dict(reference_id='physics',claim=claims[i],position='Complete fixture') for k in ('input_action','transmission','output_action')})
                plan['shots'].append(dict(shot_id=sid,time_range=[i*3,(i+1)*3],narration=[claims[i]],comprehension=row))
            research=dict(science=dict(subject=subject))
            self.assertEqual(validate_product_plan(plan,research)['product_id'],'constant-speed')
            self.assertNotIn('product_identity',plan)
            plan['subject_identity']=dict(subject,scope='Unbounded real-world prediction')
            with self.assertRaisesRegex(ValueError,'scope differs'):validate_product_plan(plan,research)
