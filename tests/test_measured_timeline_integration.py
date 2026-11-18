"""Measured Neil's frame timeline must reach registration and reader reports."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import workflow as w
from mechanical_video_next.growth_report import planned_timeline


class MeasuredTimelineIntegrationTests(unittest.TestCase):
    def timeline(self):
        return dict(fps=30, seconds=4, frame_count=120, shots=[
            dict(id='a', start_frame=0, frame_count=45, seconds=1.5),
            dict(id='b', start_frame=45, frame_count=75, seconds=2.5)])

    def test_registration_reads_measured_seconds_and_rejects_wrong_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root/'fixture.mp4'
            video.write_bytes(b'Temporary binding only; probe is isolated below.')
            timeline = root/'timeline.json'
            content = self.timeline()
            media = dict(path=str(video), sha256=w.filehash(video), chapter_ids=['a', 'b'])
            data = dict(duration_policy=dict(minimum=1, maximum=300),
                        shared_production=dict(timeline={}))
            info = dict(streams=[dict(codec_type='video', duration='4', width=1920,
                                     height=1080, avg_frame_rate='30/1'),
                                 dict(codec_type='audio', duration='4')])
            with patch('mechanical_video_next.multiroute.probe', return_value=info):
                for duration, valid in [(4, True), (7, False), (float('nan'), False)]:
                    content['seconds'] = duration
                    timeline.write_text(json.dumps(content))
                    data['shared_production']['timeline'] = dict(
                        path=str(timeline), sha256=w.filehash(timeline))
                    if valid:
                        self.assertEqual(w.complete_media(data, media)['duration'], 4)
                    else:
                        with self.assertRaisesRegex(ValueError, 'measured shared timeline'):
                            w.complete_media(data, media)

    def test_growth_report_uses_actual_frame_boundaries(self):
        blueprint = dict(shots=[dict(shot_id='a', knowledge_goal='First cause'),
                                dict(shot_id='b', knowledge_goal='Second cause')])
        rows = planned_timeline(self.timeline(), blueprint)
        self.assertEqual([r['time_range'] for r in rows], [[0, 1.5], [1.5, 4]])
        self.assertEqual([r['knowledge'] for r in rows], ['First cause', 'Second cause'])
        self.assertTrue(all('非成片感官结论' in r['scope'] for r in rows))
