"""Synthetic negative gates; these tests do not assert real viewer understanding."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from mechanical_video_next import growth as g
from tests import test_growth as legacy


class GrowthObjectivesV2Tests(unittest.TestCase):
    def setUp(self):
        legacy.GrowthTests.setUp(self)
        self.data['growth_policy_version'] = 2
        self.data['reference_principles'] = [{'reference_id': 'real-product-source'}]
        self.data['growth_goals'] = {}
        for shot in self.data['shots']:
            shot['related_growth_goal'] = list(g.GOALS_V2)
        for category, keys in g.GOALS_V2.items():
            group = self.data['growth_goals'][category] = {}
            for key in keys:
                row = dict(goal_id=category+'-'+key, knowledge_point='input transmission output',
                    reference_id='real-product-source', shot_id='s0', time_range=[0, 3],
                    planned_action='gear turns', visual_proof='marker displacement',
                    narration='input drives output', verification_method='independent actual video and audio',
                    actual_media_evidence=[], qa_status='PLANNED')
                if key == 'grounded_discussion':
                    row.update(discussion_relation='same-product-observable-question', misleading=False)
                if key == 'complete_answer':
                    row.update(answer_withheld=False, answer_complete=True)
                group[key] = row
        self.data['growth_goals']['retention']['first_answer_time'] = 1
        base = self.data['growth_goals']['retention']['information_progression']
        self.data['growth_goals']['retention']['information_progression'] = [
            dict(base, goal_id=f'progress-{i}', shot_id=f's{i}',time_range=[i*60,i*60+3]) for i in range(3)]

    # Parent tests exercise the historical schema; this subclass only runs v2 tests.
    def test_v2_complete_plan_and_negative_contracts(self):
        self.assertEqual(g.validate_contract(self.data),180)
        mutations = [
            ('unmapped reference',lambda d: d['growth_goals']['like']['mechanical_answer'].update(reference_id='unobserved')),
            ('unrelated comment',lambda d: d['growth_goals']['comment']['grounded_discussion'].update(discussion_relation='unrelated')),
            ('withheld answer',lambda d: d['growth_goals']['follow']['complete_answer'].update(answer_withheld=True)),
            ('late opening',lambda d: d['growth_goals']['retention']['product_opening'].update(time_range=[4,7])),
            ('wrong narration',lambda d: d['growth_goals']['save']['replay_value'].update(narration='a different action')),
            ('no new knowledge',lambda d: d['shots'][1].update(new_information='relation 0')),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                data=copy.deepcopy(self.data); mutate(data)
                with self.assertRaises(ValueError): g.validate_contract(data)

    def test_v2_actual_mp4_hash_and_missing_proof_rejection(self):
        # A real generated clip tests file/hash binding only. It is deliberately
        # not a product video and must not be described as perceptually passed.
        path = self.root/'synthetic.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                        'color=c=gray:s=160x90:r=1','-f','lavfi','-i','anullsrc=r=8000:cl=mono',
                        '-t','180','-c:v','libx264','-c:a','aac',str(path)],check=True)
        from mechanical_video_next.workflow import filehash
        media = {'path':str(path),'sha256':filehash(path)}
        report = dict(media=[media],independent_reviewer=True,reviewer_thread_id='synthetic-test-only')
        for cat,keys in g.GOALS_V2.items():
            checks=report[cat+'_checks']=[]
            for key in keys:
                plans=self.data['growth_goals'][cat][key]
                for plan in plans if isinstance(plans,list) else [plans]:
                    checks.append(dict(goal=key,goal_id=plan['goal_id'],shot_id=plan['shot_id'],
                        time_range=plan['time_range'],status='PASS',media_sha256=media['sha256'],
                        continuous_viewing=True,listening=True,actual_media_evidence=[self.ref],
                        observed=dict(visible_action='synthetic observation',heard_narration='synthetic observation',
                            knowledge_demonstrated='synthetic observation', action_matches_plan=True,
                            narration_matches_action=True,goal_realized=True)))
        def bind_receipt(row, suffix=''):
            receipt = {k: copy.deepcopy(row[k]) for k in ('goal_id','shot_id','time_range','media_sha256',
                       'status','continuous_viewing','listening','observed')}
            receipt.update(independent_reviewer=True,reviewer_thread_id=report['reviewer_thread_id'])
            target = self.root/(row['goal_id']+suffix+'.json')
            target.write_text(json.dumps(receipt))
            row['actual_media_evidence'] = [{'path':str(target),'sha256':filehash(target)}]
        for category in g.GOALS_V2:
            for row in report[category+'_checks']:
                bind_receipt(row)
        # The gate accepts a structurally valid test receipt, never infers truth.
        self.assertTrue(g.validate_actual_goals(self.data,report))
        failures=[
            ('like target with no proof',lambda r: r['like_checks'][0].update(actual_media_evidence=[])),
            ('save target not realized',lambda r: r['save_checks'][0]['observed'].update(goal_realized=False)),
            ('voice differs from motion',lambda r: r['retention_checks'][0]['observed'].update(narration_matches_action=False)),
            ('plan only PASS',lambda r: r['follow_checks'][0].pop('observed')),
            ('no independent review',lambda r: r.update(independent_reviewer=False)),
            ('wrong media hash',lambda r: r['like_checks'][0].update(media_sha256='stale')),
            ('still frames only',lambda r: r['save_checks'][0].update(continuous_viewing=False)),
            ('unrelated hash-bound note',lambda r: r['like_checks'][0].update(actual_media_evidence=[self.ref])),
            ('incomplete action coverage',lambda r: r['like_checks'][0].update(time_range=[0,1])),
            ('receipts for another goal',lambda r: r['like_checks'][0].update(actual_media_evidence=r['save_checks'][0]['actual_media_evidence'])),
        ]
        for label,mutate in failures:
            with self.subTest(label=label):
                broken=copy.deepcopy(report);mutate(broken)
                with self.assertRaises(ValueError):g.validate_actual_goals(self.data,broken)
        second = self.root/'second-route.mp4'
        # Same valid stream layout but distinct bytes/content identity. Merely
        # declaring it in the aggregate must not reuse route one's review.
        second.write_bytes(path.read_bytes()+b'synthetic-second-route')
        other = {'path':str(second),'sha256':filehash(second)}
        aggregate=copy.deepcopy(report); aggregate['media'].append(other)
        with self.assertRaisesRegex(ValueError,'each media'):
            g.validate_actual_goals(self.data,aggregate)
        for category in g.GOALS_V2:
            rows=aggregate[category+'_checks']
            for original in list(rows):
                row=copy.deepcopy(original);row['media_sha256']=other['sha256']
                bind_receipt(row,'-second');rows.append(row)
        self.assertTrue(g.validate_actual_goals(self.data,aggregate))
        # Alter one review receipt's coverage while updating its file hash:
        # integrity alone cannot make a partial observation sufficient.
        broken=copy.deepcopy(report)
        ref=broken['like_checks'][0]['actual_media_evidence'][0]
        receipt=json.loads(Path(ref['path']).read_text());receipt['time_range']=[0,1]
        target=self.root/'partial-review.json';target.write_text(json.dumps(receipt))
        broken['like_checks'][0]['actual_media_evidence']=[{'path':str(target),'sha256':filehash(target)}]
        with self.assertRaisesRegex(ValueError,'complete planned action'):
            g.validate_actual_goals(self.data,broken)
        path.unlink()
        with self.assertRaisesRegex(ValueError,'actual media'):g.validate_actual_goals(self.data,report)
