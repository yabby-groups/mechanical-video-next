"""A lighting/material preset for the existing EAS shot templates.

Visual reference: printer-series EP03. No new mechanism geometry or solver.
"""
import bpy
from mathutils import Vector

PROFILE = 'printer-ep03-studio-v1'


def apply(profile, objects, frames, camera, options=None):
    if profile != PROFILE:
        raise ValueError('Unknown studio visual profile: ' + profile)
    scene = bpy.context.scene
    options = options or {}
    scene.render.engine = 'BLENDER_EEVEE'
    samples = options.get('render_samples', 8 if scene.render.resolution_x<=960 else 24)
    if isinstance(samples, bool) or not isinstance(samples, int) or not 1 <= samples <= 512:
        raise ValueError('Studio render_samples must be an integer from 1 to 512')
    if hasattr(scene.eevee,'taa_render_samples'):
        scene.eevee.taa_render_samples=samples
    scene.view_settings.view_transform = 'AgX'
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (0.32, 0.37, 0.43, 1)
    background.inputs['Strength'].default_value = options.get('world_strength',0.55)
    materials = {m for obj in objects for m in obj.data.materials if m}
    for mat in materials:
        shader = mat.node_tree.nodes.get('Principled BSDF') if mat.use_nodes else None
        if shader and not mat.get('studio_preserve_surface', False):
            base = shader.inputs['Base Color'].default_value[:3]
            muted = tuple(0.65*c + 0.35*g for c,g in zip(base,(0.25,0.30,0.35)))
            shader.inputs['Base Color'].default_value = (*muted,1)
            shader.inputs['Metallic'].default_value = 0.62
            shader.inputs['Roughness'].default_value = 0.34
    # Explicit episode styling can distinguish parts which share a source
    # material. Copy locally so source CAD materials and other parts stay intact.
    overrides = options.get('material_overrides', {})
    for obj in objects:
        spec = overrides.get(obj.name)
        if not spec:
            continue
        for slot in obj.material_slots:
            if slot.material is None:
                continue
            mat = slot.material.copy()
            mat.name = obj.name + ' | episode studio finish'
            slot.material = mat
            shader = mat.node_tree.nodes.get('Principled BSDF') if mat.use_nodes else None
            if shader:
                shader.inputs['Base Color'].default_value = (*spec['color'], 1)
                shader.inputs['Metallic'].default_value = spec.get('metallic', .8)
                shader.inputs['Roughness'].default_value = spec.get('roughness', .26)
    lowest = float('inf')
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        lowest = min(lowest, *( (obj.matrix_world @ Vector(v)).z
                                 for obj in objects for v in obj.bound_box))
    # Studio backdrop only; never included in mechanical inventory or checks.
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,lowest-options.get('floor_gap',0.35)))
    floor = bpy.context.object
    floor.name = 'Studio_Backdrop'
    mat = bpy.data.materials.new('Studio | neutral grey')
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*options.get('floor_color',(0.20,0.24,0.29)),1)
    shader.inputs['Roughness'].default_value = 0.78
    floor.data.materials.append(mat)
    light_scale=1.0
    light_center=Vector((0,0,0))
    if options.get('scale_to_subject'):
        points=[obj.matrix_world @ Vector(v) for obj in objects for v in obj.bound_box]
        lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
        hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
        light_scale=max(hi-lo)/4
        light_center=(lo+hi)/2
    for name, location, energy, size in [
        ('Key',(-3,-4,10),1400,7), ('Fill',(6,1,7),850,8), ('Rim',(-4,6,8),1100,6),
    ]:
        location=light_center+Vector(location)*light_scale
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.name = 'Studio_' + name
        light.data.energy = energy*light_scale**2*options.get(name.lower()+'_strength',1.0)
        light.data.shape = 'DISK'
        light.data.size = size*light_scale*options.get(name.lower()+'_size',1.0)
        light.rotation_euler = (light_center-light.location).to_track_quat('-Z','Y').to_euler()
    if len(frames)>1:
        scale = camera.data.ortho_scale
        camera.data.ortho_scale = scale*1.02
        camera.data.keyframe_insert('ortho_scale',frame=frames[0])
        camera.data.ortho_scale = scale*0.98
        camera.data.keyframe_insert('ortho_scale',frame=frames[-1])
    return {'profile':profile,'engine':scene.render.engine,
            'lighting_options':options,
            'render_samples':getattr(scene.eevee,'taa_render_samples',None),
            'scope':'Studio staging and PBR materials; original teaching mechanism unchanged'}
