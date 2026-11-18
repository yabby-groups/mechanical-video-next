import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next.media_revision import compare, validate_report


class MediaRevisionTests(unittest.TestCase):
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
