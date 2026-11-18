import copy
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next import production_contract as c
from mechanical_video_next.workflow import create_task, load, producer_prompt


class ProductionContractTests(unittest.TestCase):
    def test_unknown_fact_is_local_and_cannot_enter_dependent_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.txt'; source.write_text('Located evidence')
            from scripts.common import filehash
            fact = dict(id='known',claim='A visible relationship',status='VERIFIED',kind='observed',
                        scope='This example',assumptions=[],sources=[dict(path=str(source),sha256=filehash(source),position='paragraph 1')])
            unknown = dict(fact,id='unknown',status='UNKNOWN',limitation='Hidden contact unobserved')
            research = {'science':dict(subject_kind='physical_phenomenon',question='Why?',answer='Because',scope='Example',facts=[fact,unknown])}
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
        c.validate_qa(report,media,acceptance=True)
        report['quality_dimensions']['mechanical_motion']['status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'prevents acceptance'): c.validate_qa(report,media,acceptance=True)
