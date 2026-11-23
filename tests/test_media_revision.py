import json
import io
from contextlib import nullcontext
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next.media_revision import compare, frames, validate_report


class MediaRevisionTests(unittest.TestCase):
    def test_native_and_variable_rates_use_the_same_half_open_output_grid(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, rate, options in (
                ('native', 30, []),
                ('cfr24', 24, []),
                ('vfr', 30, ['-vf', 'select=not(eq(mod(n\\,3)\\,1))', '-fps_mode', 'passthrough']),
            ):
                with self.subTest(name=name):
                    source = Path(folder) / (name + '.mp4')
                    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                    f'testsrc2=s=160x90:r={rate}:d=1',
                                    *options, '-c:v', 'libx264', str(source)], check=True)
                    with frames(source, 0, 1) as (decoder, stderr):
                        full = decoder.stdout.read()
                        self.assertEqual(decoder.wait(), 0, stderr.read())
                    self.assertEqual(len(full), 30 * 160 * 90 * 3)
                    with frames(source, .023, .61) as (decoder, stderr):
                        part = decoder.stdout.read()
                        self.assertEqual(decoder.wait(), 0, stderr.read())
                    self.assertEqual(part, full[160*90*3:19*160*90*3])

    def test_actual_truncated_mp4_rejects_even_when_both_inputs_end_early(self):
        from mechanical_video_next.video_review import pixel_findings
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'full.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=s=160x90:r=30:d=1', '-c:v', 'libx264',
                            '-movflags', '+faststart', str(path)], check=True)
            truncated = Path(folder) / 'truncated.mp4'
            data = path.read_bytes()
            truncated.write_bytes(data[:len(data)*2//3])
            change = dict(shot_id='core', defect_key='truncated', knowledge_target='Full cycle',
                          previous_range=[0, 1], current_range=[0, 1])
            with self.assertRaisesRegex(ValueError, r'interval.*truncated\.mp4.*exit'):
                compare(truncated, truncated, [change])
            findings = pixel_findings(path, truncated, 0, 30, 0, 'core')
            self.assertEqual(findings[0]['code'], 'picture_source_short')
            self.assertIn('truncated.mp4', findings[0]['evidence'])

    def test_workflow_binds_region_to_request_and_passes_current_blueprint(self):
        from mechanical_video_next import workflow
        from mechanical_video_next import production_contract
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root/'candidate.mp4'
            media.write_bytes(b'Workflow identity fixture, not rendered AV')
            binding = dict(path=str(media), sha256=workflow.filehash(media))
            change = dict(shot_id='core', defect_key='action', knowledge_target='Show contact',
                          previous_range=[0, 1], current_range=[0, 1], comparison_region=[0, 0, 1, .6])
            revision = root/'revision.json'
            revision.write_text(json.dumps({'changes': [dict(change, decoded_frames=30)]}))
            data = dict(schema_version=2, protocol_version=2, production_contract_version=1,
                        production_contract=production_contract.NAME, visual_policy_version=2,
                        media_policy_version=1, revision_request={'changes': [change]},
                        stages=[dict(media=binding, revision=dict(path=str(revision), sha256=workflow.filehash(revision)))])
            blueprint = {'shots': [{'shot_id': 'core'}]}
            artifacts = {'final-qa': {'media': [binding]}, 'timeline': {'media': [binding]},
                         'creative-blueprint': blueprint}
            with patch.object(workflow, 'load', return_value=data), \
                    patch.object(workflow, 'artifact', side_effect=lambda task, name: artifacts[name]), \
                    patch.object(production_contract, 'validate_qa') as science_qa, \
                    patch('mechanical_video_next.media_revision.validate_report', side_effect=RuntimeError('revision-verifier-reached')):
                with self.assertRaisesRegex(RuntimeError, 'revision-verifier-reached'):
                    workflow.check_qa(root, 'final-qa')
                self.assertEqual(science_qa.call_args.kwargs['blueprint'], blueprint)
                data['revision_request']['changes'] = [{k: v for k, v in change.items() if k != 'comparison_region'}]
                with self.assertRaisesRegex(ValueError, 'declared defect intervals'):
                    workflow.check_qa(root, 'final-qa')

    def test_caption_only_change_cannot_satisfy_a_subject_region_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, graph in (
                ('before', 'color=gray:s=160x90:r=30:d=1'),
                ('caption', 'color=gray:s=160x90:r=30:d=1,drawbox=x=0:y=72:w=160:h=18:color=red:t=fill'),
                ('action', 'color=gray:s=160x90:r=30:d=1,drawbox=x=20:y=10:w=60:h=40:color=red:t=fill'),
            ):
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', graph,
                                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(root/(name+'.mp4'))], check=True)
            change = dict(shot_id='core', defect_key='missing-action', knowledge_target='Expose subject motion',
                          previous_range=[0, 1], current_range=[0, 1], comparison_region=[0, 0, 1, .6])
            self.assertEqual(compare(root/'before.mp4', root/'caption.mp4', [change])['status'],
                             'EXPECTED_CHANGE_NOT_DEMONSTRATED')
            report = compare(root/'before.mp4', root/'action.mp4', [change])
            self.assertEqual(report['status'], 'OBSERVABLE_CHANGE_VERIFIED')
            validate_report(report, root/'action.mp4')
            report['changes'][0]['comparison_region'] = [0, .8, 1, .2]
            with self.assertRaises(ValueError):
                validate_report(report, root/'action.mp4')
            for region in ([0, 0, 0, 1], [0, 0, 2, 1], [True, 0, 1, 1], [0, 0, float('nan'), 1]):
                with self.subTest(region=region), self.assertRaisesRegex(ValueError, 'region'):
                    compare(root/'before.mp4', root/'action.mp4', [dict(change, comparison_region=region)])

    def test_both_decoders_ending_early_cannot_prove_a_complete_action(self):
        class Decoder:
            def __init__(self, value):
                self.stdout = io.BytesIO(bytes([value])*(160*90*3*2))
            def wait(self): return 0
            def poll(self): return 0
        change = dict(shot_id='core', defect_key='truncated-action', knowledge_target='Observe full cycle',
                      previous_range=[0, 1], current_range=[0, 1])
        with patch('mechanical_video_next.media_revision.spec', return_value={'duration': 1}), \
                patch('mechanical_video_next.media_revision.frames', side_effect=[
                    nullcontext((Decoder(value), io.BytesIO())) for value in (0, 255)]):
            with self.assertRaisesRegex(ValueError, 'Complete interval'):
                compare('before.mp4', 'after.mp4', [change])

    def test_actual_change_and_reencode_and_wrong_interval(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,graph in [('before','color=gray:s=160x90:r=30:d=1'),
                               ('after','color=gray:s=160x90:r=30:d=1,drawbox=x=0:y=0:w=80:h=90:color=red:t=fill:enable=gte(t\\,0.5)')]:
                subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',graph,'-c:v','libx264','-pix_fmt','yuv420p',str(root/(name+'.mp4'))],check=True)
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(root/'before.mp4'),'-metadata','comment=V2','-c:v','libx264','-crf','20',str(root/'renamed.mp4')],check=True)
            change=dict(shot_id='s1',defect_key='unseen-action',knowledge_target='Show the change',previous_range=[.5,1],current_range=[.5,1])
            report=compare(root/'before.mp4',root/'after.mp4',[change])
            self.assertEqual(report['status'],'OBSERVABLE_CHANGE_VERIFIED')
            self.assertEqual(report['changes'][0]['decoded_frames'],15)
            self.assertEqual(report['quality_improved'],'UNKNOWN')
            validate_report(report,root/'after.mp4')
            renamed=compare(root/'before.mp4',root/'renamed.mp4',[change])
            self.assertEqual(renamed['status'],'EXPECTED_CHANGE_NOT_DEMONSTRATED')
            wrong=dict(change,previous_range=[0,.4],current_range=[0,.4])
            self.assertEqual(compare(root/'before.mp4',root/'after.mp4',[wrong])['status'],'EXPECTED_CHANGE_NOT_DEMONSTRATED')
            report['changes'][0]['mean_rgb_difference']=255
            with self.assertRaises(ValueError): validate_report(report,root/'after.mp4')
            for window, expected in (([.01, .11], 3), ([.01, .51], 15), ([.001, .999], 29)):
                with self.subTest(window=window):
                    fractional = dict(change, previous_range=window, current_range=window)
                    result = compare(root/'before.mp4', root/'after.mp4', [fractional])
                    self.assertEqual(result['changes'][0]['decoded_frames'], expected)
