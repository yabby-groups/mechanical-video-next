import copy
import hashlib

import unittest
import tempfile
from pathlib import Path

from mechanical_video_next.reference_policy import validate_reference_model


def audit(tmp_path):
    model = tmp_path / 'assembly.step'
    model.write_bytes(b'verified model version')
    return {
        'mechanism_id': 'specific-embodiment', 'depicted_type': 'hand-pressed teaching model',
        'scope': 'Patent embodiment only; not a commercial product reconstruction',
        'bindings': [{'path': str(model), 'sha256': hashlib.sha256(model.read_bytes()).hexdigest()}],
        'no_model_mixing': True, 'independent': True, 'reviewer_thread_id': 'qa-thread',
        'motion_basis': 'Prescribed kinematics; no contact simulation',
        'dimensions_basis': 'Teaching dimensions, not measured product dimensions',
        'parts': [{'part_id': 'rod', 'source_locations': [{'source_id': 'patent', 'position': 'Fig. 3, part 41'}],
                   'cad_parts': ['spiral_rod41'], 'function': 'Converts relative axial motion',
                   'connections': ['Through part 42'], 'motion_constraints': ['Specified helix pitch'],
                   'verification': {'status': 'SCOPED_PASS', 'evidence': 'Independent figure and CAD comparison'},
                   'teaching_approximations': ['Pitch is illustrative']}],
        'consistency_checks': {key: {'status': 'PASS', 'evidence': 'Scoped independent comparison'} for key in
                               ('appearance', 'key_parts', 'connections', 'input_action', 'transmission',
                                'output_action', 'work_and_reset', 'exploded_relationships')},
        'unresolved_core_issues': [],
    }


class ReferenceModelTests(unittest.TestCase):
    def test_scoped_teaching_audit_and_stale_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = audit(Path(tmp))
            validate_reference_model(report, "specific-embodiment")
            Path(report["bindings"][0]["path"]).write_bytes(b"changed CAD")
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_reference_model(report, "specific-embodiment")

    def test_solid_validity_cannot_replace_reference_consistency(self):
        for change in ("unknown_connection", "model_mixing", "missing_approximation", "core_issue"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                report = copy.deepcopy(audit(Path(tmp)))
                if change == "unknown_connection":
                    report["consistency_checks"]["connections"]["status"] = "UNKNOWN"
                elif change == "model_mixing":
                    report["no_model_mixing"] = False
                elif change == "missing_approximation":
                    report["parts"][0]["teaching_approximations"] = []
                else:
                    report["unresolved_core_issues"] = ["Unsupported torque reaction connection"]
                with self.assertRaises(ValueError):
                    validate_reference_model(report, "specific-embodiment")
