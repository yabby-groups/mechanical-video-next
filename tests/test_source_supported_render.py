"""Technical production evidence is distinct from final sensory acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from mechanical_video_next import workflow as w


class SourceSupportedRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = w.create_task('fixture', root=Path(self.tmp.name), protocol_version=1)
        def save(name, obj):
            path = self.task / name
            path.write_text(json.dumps(obj))
            return dict(path=str(path), sha256=w.filehash(path))
        self.save = save
        self.assembly = save('assembly.json', dict(id='new verified fixture'))
        self.cfg = save('film.json', dict(production_scope='source-supported-film', assembly_config=self.assembly['path']))
        self.preview_cfg = save('preview.json', dict(assembly_config=self.assembly['path']))
        self.preview = save('preview.mp4', {})
        self.inventory = save('inventory.json', [dict(valid=True, solids=1, volume_mm3=4)])
        self.research = dict(mechanism_id='fixture-A')
        self.asset = dict(mechanism_id='fixture-A', selected_candidate_id='new', candidates=[dict(id='new', validation_evidence=self.inventory)])
        data = w.load(self.task)
        data['config'] = self.cfg['path']
        data['stages'] = [dict(phase='local', command_success=True, config_sha256=self.preview_cfg['sha256'])]
        data['reference_remake'] = dict(mechanism_basis=dict(status='PASS', mechanism_id='fixture-A', source_bindings=[self.assembly]),
            production_binding=dict(config=self.cfg, preview=self.preview, preview_config=self.preview_cfg))
        w.write(self.task/'task.json', data)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(w, 'require_current_scheme'))
        self.stack.enter_context(patch.object(w, 'artifact', return_value=self.research))
        self.stack.enter_context(patch.object(w, 'check_asset', return_value=self.asset))
        self.stack.enter_context(patch('mechanical_video_next.reference_policy.validate_research'))
        self.stack.enter_context(patch('mechanical_video_next.comprehension.validate_product_research'))
        self.stack.enter_context(patch('mechanical_video_next.three_d.validate_config'))
        self.stack.enter_context(patch.object(w.subprocess, 'check_output', return_value=json.dumps(dict(
            format=dict(duration='15'), streams=[dict(codec_type='video')])).encode()))

    def test_verified_technical_basis_does_not_require_sensory_or_growth_qa(self):
        self.assertTrue(w.require_source_supported_render(self.task))
        w.require_animatic(self.task)
        w.require_reference_content(self.task)
        self.assertNotEqual(w.load(self.task)['state'], 'COMPLETED')
        with patch.object(w, 'artifact', return_value=dict(checks={'listening':'UNKNOWN'})):
            with self.assertRaises(ValueError):
                w.check_qa(self.task, 'final-qa')

    def test_actual_media_handoffs_use_current_technical_dependencies(self):
        data = w.load(self.task)
        dependencies = {'research', 'asset-plan', 'cad-model', 'mechanical-diagnostics', 'audio-preparation'}
        data['handoffs'] = {name: dict(sha256=name) for name in dependencies}
        w.write(self.task/'task.json', data)
        payload = dict(config=self.cfg, media=[self.preview], keyframes_verified=True)
        with patch.object(w, 'protocol_version', return_value=2):
            envelope = w.put_handoff(self.task, 'Animation', 'animation-manifest', payload,
                ['research', 'asset-plan', 'cad-model', 'mechanical-diagnostics'])
            self.assertNotIn('animatic-qa', envelope['dependencies'])
            envelope = w.put_handoff(self.task, 'Editor', 'timeline', payload,
                ['research', 'animation-manifest', 'audio-preparation'])
            self.assertEqual(set(envelope['dependencies']), {'research', 'animation-manifest', 'audio-preparation'})
            with self.assertRaisesRegex(ValueError, 'exact current film config'):
                w.put_handoff(self.task, 'Editor', 'timeline', dict(payload, config={'sha256':'stale'}),
                    ['research', 'animation-manifest', 'audio-preparation'])

    def test_unknown_mechanics_or_invalid_solids_cannot_render(self):
        self.asset['candidates'][0]['validation_evidence'] = self.save('invalid.json', [dict(valid=False, solids=1, volume_mm3=4)])
        with self.assertRaisesRegex(ValueError, 'CAD solids'):
            w.require_source_supported_render(self.task)
        self.asset['candidates'][0]['validation_evidence'] = self.inventory
        data = w.load(self.task)
        data['reference_remake']['mechanism_basis']['status'] = 'UNKNOWN'
        w.write(self.task/'task.json', data)
        with self.assertRaisesRegex(ValueError, 'continue research'):
            w.require_source_supported_render(self.task)

    def test_stale_config_or_preview_assembly_substitution_is_rejected(self):
        Path(self.cfg['path']).write_text(json.dumps(dict(production_scope='source-supported-film', assembly_config=self.assembly['path'], changed=True)))
        with self.assertRaisesRegex(ValueError, 'exact new config'):
            w.require_source_supported_render(self.task)
        data = w.load(self.task)
        data['reference_remake']['production_binding']['config']['sha256'] = w.filehash(self.cfg['path'])
        other = self.save('other-assembly.json', dict(id='different model'))
        new_preview = self.save('preview-config2.json', dict(assembly_config=other['path']))
        data['reference_remake']['production_binding']['preview_config'] = new_preview
        data['stages'] = [dict(phase='local', command_success=True, config_sha256=new_preview['sha256'])]
        w.write(self.task/'task.json', data)
        with self.assertRaisesRegex(ValueError, 'substitute'):
            w.require_source_supported_render(self.task)
