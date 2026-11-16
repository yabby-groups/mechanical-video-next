"""Producer must repair independently observed failures before old approvals."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from mechanical_video_next import workflow as w
from mechanical_video_next import comprehension as c
from tests.test_comprehension import valid_plan


class ContentRepairPriorityTests(unittest.TestCase):
    def test_research_product_cannot_bind_different_patent(self):
        with self.assertRaisesRegex(ValueError, 'researched implementation'):
            c.validate_product_plan(valid_plan(), {'mechanism_id': 'another-product'})

    def test_known_content_failure_supersedes_old_render_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            data = w.load(task)
            data['content_repairs'] = [dict(defect_key='product-unrecognizable', status='OPEN',
                suggested_fix='Show verified whole product before core', responsible_agent='Animation',
                evidence='independently observed exact-media failure')]
            w.write(task / 'task.json', data)
            report = w.continuation(task)
            self.assertEqual(report['next_action']['defect_key'], 'product-unrecognizable')
            self.assertIsNone(report['next_action']['command'])
            with self.assertRaisesRegex(ValueError, 'content defect'):
                w.require_reference_content(task)
            data['content_repairs'][0]['status'] = 'RESOLVED'
            w.write(task / 'task.json', data)
            self.assertEqual(w.continuation(task)['next_action']['handoff'], 'research')

    def test_new_final_qa_cannot_bypass_comprehension(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder))
            with patch.object(w, 'artifact', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Real product identity'):
                    w.check_qa(task, 'final-qa')
