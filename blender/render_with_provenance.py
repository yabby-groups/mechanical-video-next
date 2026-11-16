"""Save the actual prepared scene without changing locked geometry/style code."""
from pathlib import Path
import json
import sys
import hashlib
import time
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scene

savejson=scene.savejson


def save_with_scene(path, report):
    if Path(path).name=='checks.json':
        args=sys.argv[sys.argv.index('--')+1:]
        shot=json.loads(Path(args[args.index('--shot')+1]).read_text())
        fps=int(args[args.index('--fps')+1])
        bpy.context.scene.frame_start=1
        bpy.context.scene.frame_end=max(2,round(shot['seconds']*fps))
        bpy.context.scene.frame_set(1)
        target = Path(path).parent/'scene.blend'
        if shot.get('scene_artifact_dir'):
            root = Path(shot['scene_artifact_dir']).resolve()
            output = Path(__file__).resolve().parents[1]/'output'
            if not root.is_relative_to(output.resolve()):
                raise ValueError('Permanent scene artifacts must remain inside project output')
            root.mkdir(parents=True, exist_ok=True)
            # Scenes are permanent inspectable deliverables, not disposable frames.
            # Unique names preserve failed and successful rendering history alike.
            target = root/(Path(path).parent.parent.name+'-'+str(time.time_ns())+'.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True)
        report['scene_artifact'] = {'path': str(target.resolve()),
                                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    savejson(path,report)


scene.savejson=save_with_scene
if '--export-scene-only' in sys.argv:
    sys.argv.remove('--export-scene-only')
    sys.argv.append('--checks-only')
scene.main()
