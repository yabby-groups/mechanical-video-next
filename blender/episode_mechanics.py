"""Evaluate and preview the same procedural Blender poses used by an episode render."""

import json
import math
from pathlib import Path
import runpy
import sys

import bpy
from mathutils import Vector


def position(obj, depsgraph, local=(0, 0, 0)):
    return obj.evaluated_get(depsgraph).matrix_world @ Vector(local)


def relative_matrix(obj, reference, depsgraph):
    world = obj.evaluated_get(depsgraph).matrix_world
    return reference.evaluated_get(depsgraph).matrix_world.inverted() @ world


def surface_hit(obj, depsgraph, origin, direction):
    """Intersect an evaluated surface along the relevant contact normal."""
    evaluated = obj.evaluated_get(depsgraph)
    inverse = evaluated.matrix_world.inverted()
    hit, point, _, _ = evaluated.ray_cast(inverse @ Vector(origin),
                                          inverse.to_3x3() @ Vector(direction))
    if not hit:
        raise ValueError(f'No contact surface on {obj.name}')
    return evaluated.matrix_world @ point


def require_range(label, value, lower, upper):
    if not lower <= value <= upper:
        raise ValueError(f'{label}: {value:.6g} outside [{lower:.6g}, {upper:.6g}]')
    return value


def evaluate(scene, pose, count, measure, model, substeps):
    def seek(frame):
        whole = math.floor(frame)
        scene.frame_set(whole, subframe=frame - whole)
        pose(frame / 30)
        bpy.context.view_layer.update()
        return bpy.context.evaluated_depsgraph_get()

    def checked(frame, callback, phase):
        try:
            return callback(seek(frame))
        except (ValueError, KeyError) as error:
            raise ValueError(f'{phase} at frame {frame:g} ({frame / 30:.4f}s): {error}') from error

    checked(0, model, 'Model')
    samples = {}
    for tick in range((count - 1) * substeps + 1):
        frame = tick / substeps
        values = checked(frame, measure, 'Motion')
        if (not values or (samples and values.keys() != samples.keys())
                or any(not math.isfinite(value) for value in values.values())):
            raise ValueError(f'Missing or invalid evaluated motion channels at frame {frame:g}')
        for key, value in values.items():
            samples.setdefault(key, []).append(value)
    return samples, seek


def preview(scene, seek, count, samples, substeps, folder):
    # Pick a contiguous native-rate window where the mechanism actually moves.
    # Each normalized channel gets a vote independent of its units.
    scores = [0.0] * max(1, count - 1)
    for values in samples.values():
        span = max(values) - min(values)
        if span > 1e-6:
            for i in range(count - 1):
                scores[i] += abs(values[(i + 1) * substeps] - values[i * substeps]) / span
    center = max(range(len(scores)), key=scores.__getitem__)
    first = max(0, min(count - 8, center - 3))
    last = min(first + 8, count)
    folder.mkdir(exist_ok=True)
    scene.render.resolution_percentage = 18
    # Keep the production camera, visibility, materials and procedural pose.
    if scene.render.engine == 'BLENDER_EEVEE':
        scene.eevee.taa_render_samples = 4
    for frame in range(first, last):
        seek(frame)
        path = folder / f'{frame - first:05}.jpg'
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    return [first, last]


def main():
    # The scene's original command line and render loop stay in use.
    delimiter = sys.argv.index('--')
    source, phase, receipt_path, *args = sys.argv[delimiter + 1:]
    receipt_path = Path(receipt_path)
    sys.argv[delimiter + 1:] = args
    sys.path.insert(0, str(Path(__file__).parent))
    result = None

    def check(scene, pose, count, measure, *, model, substeps=2):
        nonlocal result
        if (result is not None or type(count) is not int or count < 1
                or type(substeps) is not int or not 1 <= substeps <= 16):
            raise ValueError('Expected one check per shot, with 1–16 samples per frame')
        samples, seek = evaluate(scene, pose, count, measure, model, substeps)
        result = {
            'status': 'PASS', 'blender': bpy.app.version_string, 'frames': count,
            'substeps': substeps, 'evaluated_poses': (count - 1) * substeps + 1,
            'samples': samples,
        }
        if phase == 'preflight':
            result['preview_range'] = preview(
                scene, seek, count, samples, substeps, receipt_path.parent / 'motion-preview-frames')
            return True
        expected = json.loads(receipt_path.read_text())
        if any(result[key] != expected[key] for key in result):
            raise ValueError('Rebuilt Blender scene differs from the evaluated preflight')
        # Existing procedural render loops begin at the first pose.
        seek(0)
        return False

    try:
        runpy.run_path(source, run_name='__main__', init_globals={'check_mechanics': check})
        if result is None:
            raise ValueError('Scene did not run its declared mechanical checks')
        if phase == 'preflight':
            receipt_path.write_text(json.dumps(result, allow_nan=False) + '\n')
    except (ValueError, KeyError) as error:
        failure = receipt_path.with_suffix(f'.{phase}.failure.json')
        failure.write_text(json.dumps({'status': 'FAIL', 'error': str(error)}) + '\n')
        raise


if __name__ == '__main__':
    main()
