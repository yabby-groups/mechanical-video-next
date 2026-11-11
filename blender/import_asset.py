"""GLB/glTF/Blend import and structural inventory, called by the asset skill CLI."""
import argparse
import json
from pathlib import Path
import sys
import bpy

ap=argparse.ArgumentParser()
ap.add_argument('source',type=Path)
ap.add_argument('output',type=Path)
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.read_factory_settings(use_empty=True)
if args.source.suffix.lower()=='.blend':
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
elif args.source.suffix.lower() in ['.glb','.gltf']:
    bpy.ops.import_scene.gltf(filepath=str(args.source))
else:
    raise ValueError('Only GLB/glTF/Blend supported; convert STEP separately with FreeCAD')
parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and len(o.data.vertices)>0]
assert len(parts)>=2, 'Single monolithic mesh is not an explodable assembly'
inventory={'independent_objects':len(parts),'parts':[{'name':o.name,'vertices':len(o.data.vertices),
    'parent':o.parent.name if o.parent else None,'mesh':o.data.name,
    'world_matrix':[v for row in o.matrix_world for v in row],
    'bounds':[list(v) for v in o.bound_box]} for o in parts],
    'status':'STRUCTURAL_ONLY_NEEDS_PART_MAPPING_AND_LICENSE_REVIEW',
    'unverified':['Part identity','Disassembly path','Scientific motion','Declared source license']}
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
args.output.with_suffix('.inventory.json').write_text(json.dumps(inventory,indent=2))
