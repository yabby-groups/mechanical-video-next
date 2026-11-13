import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from mechanical_video_next import covers as c


class CoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = Path(self.tmp.name)
        video = self.task/'source.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=1',
                        '-t','2','-c:v','libx264',str(video)],check=True)
        self.paths = {r:video for r in c.ROUTES}
        self.data = {'topic':'测试齿轮','route_runs':{r:{'outputs':{'path':str(video)}} for r in c.ROUTES}}
        c.write(self.task/'task.json', self.data)
        self.plan = dict(topic='测试齿轮', recommended_route='3d', recommendation_reason='空间关系清晰',
            route_analysis={r:dict(suitability='UNKNOWN',reason='待实际审查') for r in c.ROUTES},
            title=['齿轮如何传动？'], series='拆开机器', copy_rationale='讲解传动关系',frame_rationale='可见输入输出',
            selected_candidate='main', candidates=[dict(id='main', route='3d', seconds=0, shot_id='s1',
                mechanical_moment='齿轮啮合',subject_box=[0,0,1,1])])
        self.save()

    def save(self):
        c.write(self.task/'cover-plan.json',self.plan)

    def test_exports_names_dimensions_and_no_video_mutation(self):
        before = c.sha(self.paths['3d'])
        with patch.object(c.subprocess,'run',wraps=subprocess.run) as run:
            report=c.generate(self.task)
        for call in run.call_args_list:
            self.assertIn(Path(call.args[0][0]).name, ('ffmpeg','ffprobe'))
        for name,size in c.SIZES.items():
            with c.Image.open(self.task/'cover'/name) as im:
                self.assertEqual(im.size,size); self.assertEqual(im.format,'PNG')
        self.assertEqual(before,c.sha(self.paths['3d']))
        self.assertEqual(c.validate(self.task)['topic'],'测试齿轮')
        self.assertTrue(all(x['status']=='UNKNOWN' for x in report['cover_checks'].values()))
        with self.assertRaises(ValueError):c.validate(self.task,True)

    def test_growth_report_binds_covers_and_detects_changed_copy(self):
        from mechanical_video_next import growth_report as gr
        comparison=self.task/'compare.mp4'
        comparison.write_bytes(self.paths['3d'].read_bytes())
        report=gr.generate(self.task, self.paths, comparison)
        self.assertEqual(report['recommendation']['route'], '3d')
        gr.validate(self.task)
        self.plan['title']=['新问题'];self.save()
        with self.assertRaisesRegex(ValueError, 'STALE'):gr.validate(self.task)

    def test_new_delivery_requires_cover_qa(self):
        from mechanical_video_next import workflow
        data=dict(self.data, requested_routes=list(c.ROUTES), content_policy_version=1)
        with self.assertRaisesRegex(ValueError, 'Cover missing'):
            workflow.check_requested_routes(self.task, data)

    def test_crop_must_preserve_important_structure(self):
        self.plan['candidates'][0]['source_crop']=[.1,.1,.9,.9]
        self.save()
        with self.assertRaisesRegex(ValueError, 'crop must preserve'):c.generate(self.task)
        self.plan['candidates'][0]['subject_box']=[.2,.2,.8,.8]
        self.save()
        report=c.generate(self.task)
        self.assertIn('source_crop', report['compositions']['portrait_cover_3x4.png'])
        c.validate(self.task)

    def test_explicit_candidate_source_is_hash_bound(self):
        candidate=self.task/'candidate.v7.mp4'
        candidate.write_bytes(self.paths['3d'].read_bytes())
        self.plan['source_overrides']={'3d':c.binding(candidate)}
        self.save()
        report=c.generate(self.task)
        self.assertEqual(report['source_media']['3d']['path'], str(candidate.resolve()))
        c.validate(self.task)
        candidate.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'STALE'):c.validate(self.task)

    def test_bad_input_blocks(self):
        for change, message in (({'title':[]},'title'),({'title':[' ']},'title'),
                ({'topic':'wrong'},'topic'),({'candidates':[]},'candidate missing')):
            original=copy.deepcopy(self.plan)
            self.plan.update(change);self.save()
            with self.assertRaisesRegex(ValueError,message):c.generate(self.task)
            self.plan=original

    def test_recommendation_change_invalidates_and_updates(self):
        c.generate(self.task)
        self.plan['recommended_route']='2d'
        self.plan['candidates'][0]['route']='2d';self.save()
        with self.assertRaisesRegex(ValueError,'STALE'):c.validate(self.task)
        self.assertEqual(c.generate(self.task)['recommended_route'],'2d')
        c.validate(self.task)

    def test_small_subject_fails_composition_and_blocks_forged_pass(self):
        self.plan['candidates'][0]['subject_box']=[0,0,.05,.05];self.save()
        report=c.generate(self.task)
        self.assertEqual(report['cover_checks']['portrait_composition']['status'],'FAIL')
        refs=[c.binding(self.task/'cover'/n) for n in c.SIZES]
        qa=dict(independent_reviewer=True,reviewer_thread_id='synthetic-test',
            report_sha256=c.sha(self.task/'cover/cover-report.json'),
            cover_checks={key:dict(status='PASS',evidence='synthetic',visual_inspection=True,artifacts=refs) for key in c.CHECKS})
        c.write(self.task/'cover/cover-qa.json',qa)
        with self.assertRaisesRegex(ValueError,'composition'):c.validate(self.task,True)

    def test_independent_review_is_exact_cover_bound(self):
        c.generate(self.task)
        refs=[c.binding(self.task/'cover'/n) for n in c.SIZES]
        qa=dict(independent_reviewer=True,reviewer_thread_id='synthetic-test',
            report_sha256=c.sha(self.task/'cover/cover-report.json'),
            cover_checks={key:dict(status='PASS',evidence='synthetic review',visual_inspection=True,artifacts=refs) for key in c.CHECKS})
        c.write(self.task/'cover/cover-qa.json',qa)
        c.validate(self.task,True)
        qa['cover_checks']['copy_consistency']['status']='UNKNOWN'
        c.write(self.task/'cover/cover-qa.json',qa)
        with self.assertRaisesRegex(ValueError,'copy_consistency'):c.validate(self.task,True)
