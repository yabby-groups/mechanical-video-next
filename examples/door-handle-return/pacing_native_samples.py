import bpy
import hashlib
import json
import math
import sys

scene = bpy.context.scene
names = ["Lever handle", "66 square drive spindle", "34 active flat spring driver", "32 opposite flat spring driver", "30 continuous wire arc spring"]
rows = []
for frame in range(1, 1216):
    scene.frame_set(frame)
    objects = [bpy.data.objects[name] for name in names]
    rows.append({
        "handle": math.degrees(objects[0].rotation_euler.y),
        "spindle": math.degrees(objects[1].rotation_euler.y),
        "active_driver": math.degrees(objects[2].rotation_euler.y),
        "fixed_driver": math.degrees(objects[3].rotation_euler.y),
        "spring_compression": sum(i * key.value for i, key in enumerate(objects[4].data.shape_keys.key_blocks[1:]))
    })
path = bpy.data.filepath
with open(sys.argv[-1], "w") as out:
    json.dump({"scene": {"path": path, "sha256": hashlib.file_digest(open(path, "rb"), "sha256").hexdigest()}, "samples": rows}, out)
