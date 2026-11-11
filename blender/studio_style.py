"""A lighting/material preset for the existing EAS shot templates.

Visual reference: printer-series EP03. No new mechanism geometry or solver.
"""
import bpy
from mathutils import Vector

PROFILE = 'printer-ep03-studio-v1'


def apply(profile, objects, frames, camera):
    if profile != PROFILE:
        raise ValueError('Unknown studio visual profile: ' + profile)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.view_settings.view_transform = 'AgX'
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (0.32, 0.37, 0.43, 1)
    background.inputs['Strength'].default_value = 0.55
    materials = {m for obj in objects for m in obj.data.materials if m}
    for mat in materials:
        shader = mat.node_tree.nodes.get('Principled BSDF') if mat.use_nodes else None
        if shader:
            base = shader.inputs['Base Color'].default_value[:3]
            muted = tuple(0.65*c + 0.35*g for c,g in zip(base,(0.25,0.30,0.35)))
            shader.inputs['Base Color'].default_value = (*muted,1)
            shader.inputs['Metallic'].default_value = 0.62
            shader.inputs['Roughness'].default_value = 0.34
    lowest = float('inf')
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        lowest = min(lowest, *( (obj.matrix_world @ Vector(v)).z
                                 for obj in objects for v in obj.bound_box))
    # Studio backdrop only; never included in mechanical inventory or checks.
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,lowest-0.35))
    floor = bpy.context.object
    floor.name = 'Studio_Backdrop'
    mat = bpy.data.materials.new('Studio | neutral grey')
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (0.20,0.24,0.29,1)
    shader.inputs['Roughness'].default_value = 0.78
    floor.data.materials.append(mat)
    for name, location, energy, size in [
        ('Key',(-3,-4,10),1400,7), ('Fill',(6,1,7),850,8), ('Rim',(-4,6,8),1100,6),
    ]:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.name = 'Studio_' + name
        light.data.energy = energy
        light.data.shape = 'DISK'
        light.data.size = size
        light.rotation_euler = (-light.location).to_track_quat('-Z','Y').to_euler()
    if len(frames)>1:
        scale = camera.data.ortho_scale
        camera.data.ortho_scale = scale*1.02
        camera.data.keyframe_insert('ortho_scale',frame=frames[0])
        camera.data.ortho_scale = scale*0.98
        camera.data.keyframe_insert('ortho_scale',frame=frames[-1])
    return {'profile':profile,'engine':scene.render.engine,
            'scope':'Studio staging and PBR materials; original teaching mechanism unchanged'}
