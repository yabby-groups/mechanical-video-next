"""Blender-native photography and look development for source-bound assemblies."""

import bpy
from mathutils import Vector


def render_settings(scene, engine, width, height, samples):
    scene.render.engine = engine
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 94
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = 0
    scene.view_settings.look = 'AgX - Medium High Contrast'
    if engine == 'CYCLES':
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
    elif engine == 'BLENDER_EEVEE':
        scene.eevee.taa_render_samples = samples
    scene.render.film_transparent = False


def studio_world(scene, color, strength):
    world = bpy.data.worlds.new('Cinematic ambient')
    world.use_nodes = True
    background = world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (*color, 1)
    background.inputs['Strength'].default_value = strength
    scene.world = world


def surface(name, color, metallic, roughness, *, grain=None, grain_colors=None,
            bump=0, anisotropy=0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    anisotropic = shader.inputs.get('Anisotropic IOR Level') or shader.inputs.get('Anisotropic')
    if anisotropic is not None:
        anisotropic.default_value = anisotropy
    if grain is None:
        return material
    coord = nodes.new('ShaderNodeTexCoord')
    scale = nodes.new('ShaderNodeVectorMath')
    scale.operation = 'MULTIPLY'
    scale.inputs[1].default_value = grain
    links.new(coord.outputs['Object'], scale.inputs[0])
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1
    noise.inputs['Detail'].default_value = 2
    links.new(scale.outputs['Vector'], noise.inputs['Vector'])
    if grain_colors:
        ramp = nodes.new('ShaderNodeValToRGB')
        for stop, value in zip(ramp.color_ramp.elements, grain_colors):
            stop.color = (*value, 1)
        links.new(noise.outputs['Fac'], ramp.inputs[0])
        links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
    variation = nodes.new('ShaderNodeMapRange')
    variation.inputs['To Min'].default_value = max(.03, roughness - .10)
    variation.inputs['To Max'].default_value = min(1, roughness + .12)
    links.new(noise.outputs['Fac'], variation.inputs['Value'])
    links.new(variation.outputs['Result'], shader.inputs['Roughness'])
    if bump:
        relief = nodes.new('ShaderNodeBump')
        relief.inputs['Strength'].default_value = .24
        relief.inputs['Distance'].default_value = bump
        links.new(noise.outputs['Fac'], relief.inputs['Height'])
        links.new(relief.outputs[0], shader.inputs['Normal'])
    return material


def assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def area(scene, name, position, target, power, size, color=(1, 1, 1)):
    lamp = bpy.data.lights.new(name, 'AREA')
    lamp.shape = 'RECTANGLE'
    lamp.size, lamp.size_y = size
    lamp.energy, lamp.color = power, color
    obj = bpy.data.objects.new(name, lamp)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def camera(scene, name, poses, *, lens=50, ortho=None, aperture=None):
    """Fixed-lens dolly, or orthographic inspection, with a keyed tracking target."""
    data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, data)
    target = bpy.data.objects.new(name + ' focus', None)
    for obj in (camera, target):
        scene.collection.objects.link(obj)
    data.lens = lens
    if ortho is not None:
        data.type, data.ortho_scale = 'ORTHO', ortho
    track = camera.constraints.new('TRACK_TO')
    track.target, track.track_axis, track.up_axis = target, 'TRACK_NEGATIVE_Z', 'UP_Y'
    if aperture is not None:
        data.dof.use_dof = True
        data.dof.focus_object = target
        data.dof.aperture_fstop = aperture
    for frame, position, focus in poses:
        camera.location, target.location = position, focus
        camera.keyframe_insert('location', frame=frame)
        target.keyframe_insert('location', frame=frame)
    scene.timeline_markers.new(name, frame=poses[0][0]).camera = camera
    return camera


def apply_shot_lighting(scene, objects, frames, options):
    """Apply lamps to a normal Blueprint shot in assembly-relative coordinates."""
    from mathutils import Vector

    dimensions = scene.render
    engine = options.get('engine', 'BLENDER_EEVEE')
    if engine not in {'BLENDER_EEVEE', 'CYCLES'}:
        raise ValueError('Cinematic shots support EEVEE or Cycles')
    samples = options.get('render_samples', 16)
    if type(samples) is not int or not 1 <= samples <= 512:
        raise ValueError('Cinematic render_samples must be an integer from 1 to 512')
    render_settings(scene, engine, dimensions.resolution_x, dimensions.resolution_y, samples)
    dimensions.image_settings.file_format = 'PNG'
    studio_world(scene, options.get('world_color', (.20, .25, .31)), options.get('world_strength', .38))
    points = []
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        points.extend(obj.matrix_world @ Vector(vertex) for obj in objects for vertex in obj.bound_box)
    low = Vector(tuple(min(p[axis] for p in points) for axis in range(3)))
    high = Vector(tuple(max(p[axis] for p in points) for axis in range(3)))
    center, scale = (low + high) / 2, max(high - low) / 4
    default = {
        'key': {'position': [-4, -6, 6], 'power': 2350, 'size': [6, 4], 'color': [1, .88, .76]},
        'fill': {'position': [0, -6, -.8], 'power': 620, 'size': [5, 4], 'color': [.73, .85, 1]},
        'rim': {'position': [5, 1.3, 4], 'power': 1700, 'size': [2.5, 5], 'color': [.58, .77, 1]},
    }
    lights = options.get('lights', default)
    if not isinstance(lights, dict) or not lights:
        raise ValueError('Cinematic lamps must be a named mapping')
    for name, spec in lights.items():
        power = spec['power'] * scale ** 2 * options.get(name + '_strength', 1)
        position = center + Vector(spec['position']) * scale
        target = center + Vector(spec.get('target', [0, 0, 0])) * scale
        area(scene, name, position, target, power, [size * scale for size in spec['size']], spec['color'])
    if options.get('preserve_materials') is not True:
        for obj in objects:
            spec = options.get('material_overrides', {}).get(obj.name)
            if spec:
                assign(obj, surface(obj.name, tuple(spec['color']), spec.get('metallic', 0),
                                    spec.get('roughness', .35), grain=spec.get('grain'),
                                    bump=spec.get('bump', 0), anisotropy=spec.get('anisotropy', 0)))
    return {'profile': 'cinematic-native-v1', 'engine': engine, 'render_samples': samples,
            'assembly_scale': scale, 'lights': lights, 'lighting_options': options}
