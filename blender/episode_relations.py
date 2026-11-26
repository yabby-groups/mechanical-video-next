"""Apply source-reviewed relations to the scene's existing Blender evaluator."""

import json
from pathlib import Path
import runpy
import sys


sys.path.insert(0, str(Path(__file__).parent))
import episode_mechanics


def main():
    # Keep the authored render command and the existing evaluator/preview unchanged.
    delimiter = sys.argv.index('--')
    verifier, relation_ids = sys.argv[delimiter + 1:delimiter + 3]
    del sys.argv[delimiter + 1:delimiter + 3]
    checks = runpy.run_path(verifier)['RELATIONS']
    relations = json.loads(relation_ids)
    original_evaluate = episode_mechanics.evaluate

    def evaluate(scene, pose, count, measure, model, substeps):
        observers = {}
        substeps = max(2, substeps)

        def inspect(depsgraph):
            for relation in relations:
                observers[relation] = checks[relation](scene, depsgraph)
            model(depsgraph)

        def sample(depsgraph):
            independent = {}
            for relation, observer in observers.items():
                independent.update({f'review.{relation}.{key}': value
                                    for key, value in observer(depsgraph).items()})
            if not independent:
                raise ValueError('Independent mechanical measurements are empty')
            authored = measure(depsgraph)
            if any(key.startswith('review.') for key in authored):
                raise ValueError('Scene measurements cannot use the independent review namespace')
            return authored | independent

        return original_evaluate(scene, pose, count, sample, inspect, substeps)

    episode_mechanics.evaluate = evaluate
    episode_mechanics.main()


if __name__ == '__main__':
    main()
