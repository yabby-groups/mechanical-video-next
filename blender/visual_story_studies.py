"""Two low-resolution visual direction studies, authored as native Blender scenes."""
import argparse
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector


def material(name, color, *, rough=.45, metal=0, emission=0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Emission Color'].default_value = (*color, 1)
    shader.inputs['Emission Strength'].default_value = emission
    return result


def finish(obj, name, surface):
    obj.name = name
    obj.data.materials.append(surface)
    return obj


def box(name, location, size, surface, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = finish(bpy.context.object, name, surface)
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new('Soft edges', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 2
        obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def sphere(name, location, size, surface):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=location)
    obj = finish(bpy.context.object, name, surface)
    obj.scale = size
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def rod(name, start, end, radius, surface, radius_top=None, vertices=24):
    a, b = Vector(start), Vector(end)
    axis = b-a
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius,
                                   radius2=radius if radius_top is None else radius_top,
                                   depth=axis.length, location=(a+b)/2)
    obj = finish(bpy.context.object, name, surface)
    obj.rotation_euler = axis.to_track_quat('Z', 'Y').to_euler()
    return obj


def mesh(name, vertices, faces, surface):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, surface)


def line(name, points, radius, surface):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new('POLY')
    spline.points.add(len(points)-1)
    for point, coordinate in zip(spline.points, points, strict=True):
        point.co = (*coordinate, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, surface)


def pivot(name, children, at):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = at
    for child in children:
        child.parent = obj
    return obj


def look(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()


def lamp(name, location, strength, color, *, kind='AREA', size=3, target=(0, 0, 0)):
    data = bpy.data.lights.new(name, kind)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look(obj, target)
    data.energy = strength
    data.color = color
    if kind == 'AREA':
        data.shape = 'DISK'
        data.size = size
    else:
        data.angle = .12
    return obj


def camera(scene, at, target, lens):
    scene.camera.location = at
    look(scene.camera, target)
    scene.camera.data.lens = lens


def smooth(u):
    x = min(1, max(0, u))
    return x*x*(3-2*x)


def wood(name, color):
    surface = material(name, color, rough=.55)
    tree = surface.node_tree
    shader = tree.nodes.get('Principled BSDF')
    coords = tree.nodes.new('ShaderNodeTexCoord')
    scale = tree.nodes.new('ShaderNodeVectorMath')
    scale.operation = 'MULTIPLY'
    scale.inputs[1].default_value = (.45, 18, 9)
    noise = tree.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 5
    color_map = tree.nodes.new('ShaderNodeValToRGB')
    color_map.color_ramp.elements[0].color = (*(v*.29 for v in color), 1)
    color_map.color_ramp.elements[1].color = (*(v*1.42 for v in color), 1)
    tree.links.new(coords.outputs['Object'], scale.inputs[0])
    tree.links.new(scale.outputs['Vector'], noise.inputs['Vector'])
    tree.links.new(noise.outputs['Fac'], color_map.inputs[0])
    tree.links.new(color_map.outputs['Color'], shader.inputs['Base Color'])
    return surface


def nautical(scene):
    rng = random.Random(21)
    deck = wood('Salt-worn oak planks', (.25, .122, .052))
    trim = wood('Oiled dark timber', (.16, .078, .035))
    parchment = material('Ivory instrument dial', (.83, .74, .52))
    silver = material('Brushed instrument silver', (.54, .55, .52), rough=.25, metal=.83)
    brass = material('Fittings', (.58, .32, .095), rough=.36, metal=.75)
    iron = material('Blued steel', (.028, .042, .055), metal=.65)
    canvas = material('Unbleached sailcloth', (.7, .62, .45), rough=.78)
    seam = material('Sail seams', (.38, .31, .2), rough=.8)
    rope = material('Hemp rigging', (.18, .109, .061), rough=.81)
    cloth = material('Indigo wool', (.035, .083, .102), rough=.79)
    linen = material('Linen', (.61, .49, .34), rough=.8)
    leather = material('Boot leather', (.064, .031, .016), rough=.65)
    skin = material('Carved figure skin', (.37, .2, .126), rough=.64)
    water = material('Deep Atlantic water', (.038, .14, .19), rough=.23, metal=.35)
    globe = material('Illustration globe', (.032, .145, .19), rough=.43, metal=.22)
    warm = material('Port meridian', (.94, .39, .09), emission=.9)
    cool = material('Ship meridian', (.23, .73, .71), emission=.7)

    for j in range(14):
        for i in range(5):
            x = 2.18*i-4+(.35 if j%2 else 0)
            box('Deck plank', (x, .246*j-1.6, -.08), (2.167,.237,.16), deck, .008)
    for side in (-1,1):
        for z in (.12,.37,.65):
            box('Planked bulwark', (0,side*1.81,z),(11,.13,.22),trim,.02)
        box('Rounded rail top',(0,side*1.81,.83),(11,.20,.12),deck,.035)
        for x in range(-5,6):
            box('Bulwark stanchion',(x,side*1.72,.44),(.13,.12,.85),trim)
    box('Deck hatch', (1.42,.42,.12),(1.35,1.22,.32),trim)
    for j in range(8):
        box('Hatch grating',(1.42,.42+(j-3.5)*.135,.30),(1.22,.049,.047),deck,.004)
    for j in range(6):
        box('Hatch grating',(1.42+(j-2.5)*.18,.42,.325),(.05,1.04,.046),deck,.004)
    box('Chart table',(-.56,-.57,.99),(.87,.78,.105),deck)
    for x in (-.89,-.23):
        for y in (-.88,-.27):
            box('Table legs',(x,y,.475),(.09,.09,.98),trim)
    box('Folded working chart',(-.52,-.58,1.047),(.56,.49,.012),parchment,.006)

    rod('Foremast', (2.9,.03,0),(2.9,.03,5.65),.13,trim,.068)
    rod('Cross yard',(2.9,-2.57,4.65),(2.9,2.57,4.65),.081,trim,.064)
    for i in (-1,1):
        line('Shroud',[(2.9,0,5.32),(1.46,i*1.71,.81)],.012,rope)
        line('Stay',[(2.9,0,5.49),(5.3,i*.36,.29)],.010,rope)
        for j in range(4):
            line('Ladder rigging',[(2.9,0,5.28),(1.95-j*.24,i*1.71,.82)],.011,rope)
    sail_vertices=[]
    for iz in range(11):
        v=iz/10
        for iy in range(21):
            u=iy/20
            sail_vertices.append((2.93+math.sin(v*math.pi)*math.sin(u*math.pi)*.83,
                                  (u-.5)*(4.82-1.02*v),4.61-v*2.86+.21*v*math.sin(u*math.pi)))
    sail_faces=[(j*21+i,j*21+i+1,(j+1)*21+i+1,(j+1)*21+i) for j in range(10) for i in range(20)]
    sail=mesh('Billowed flax mainsail',sail_vertices,sail_faces,canvas)
    sail.modifiers.new('Canvas thickness','SOLIDIFY').thickness=.012
    for i in range(0,21,4):
        line('Stitched sail panel',[sail_vertices[j*21+i] for j in range(11)],.012,seam)
    for f in sail.data.polygons:
        f.use_smooth=True
    for i in range(5):
        v=(i+1)*.11
        pts=[(-.95+v*math.cos(a*math.tau/40),1.17+v*math.sin(a*math.tau/40),.03+.008*i) for a in range(41)]
        line('Coiled rope',pts,.024,rope)

    for y in (-.17,.17):
        rod('Breeches',(.04,.53+y,.44),(.10,.53+y,.92),.127,cloth,.143)
        rod('Stockings',(.04,.53+y,.11),(.04,.53+y,.45),.081,linen,.093)
        sphere('Leather shoe',(-.056,.53+y,.082),(.159,.089,.082),leather)
    sphere('Long wool coat',(.10,.53,1.13),(.225,.29,.39),cloth)
    rod('Neck',(.07,.53,1.38),(.03,.53,1.58),.093,skin)
    head = sphere('Face',(.035,.53,1.65),(.146,.146,.187),skin)
    sphere('Face profile',(-.097,.51,1.633),(.056,.044,.047),skin)
    sphere('Linen collar',(.045,.53,1.43),(.145,.198,.063),linen)
    hat=mesh('Cockled hat brim', [(.08+.32*math.cos(i*math.tau/3),.53+.3*math.sin(i*math.tau/3),1.81)
                                 for i in range(3)],[(0,1,2)],leather)
    hat.modifiers.new('Felt thickness','SOLIDIFY').thickness=.039
    sphere('Felt crown',(.06,.53,1.824),(.16,.17,.077),leather)
    rod('Left coat sleeve',(-.015,.79,1.35),(-.17,.87,1.065),.102,cloth,.091)
    rod('Left forearm',(-.17,.87,1.065),(-.42,.74,1.07),.089,cloth,.072)
    sphere('Resting hand',(-.465,.72,1.07),(.103,.073,.058),skin)
    for k in range(4):
        sphere('Coat buttons',(-.11,.42,1.13+.06*k),(.021,.023,.021),brass)

    hand_origin = (-.28,.30,1.15)
    watch_parts = [
        rod('Silver timekeeper case',(0,0,.012),(0,0,.035),.085,silver),
        rod('Ivory dial',(0,0,.035),(0,0,.037),.075,parchment),
        rod('Pendant stem',(0,.074,.022),(0,.109,.022),.012,silver),
        sphere('Pendant bow',(0,.108,.022),(.021,.018,.012),silver),
    ]
    for i in range(12):
        a=math.tau*i/12
        start=(.064*math.sin(a),.064*math.cos(a),.038)
        end=(.071*math.sin(a),.071*math.cos(a),.038)
        watch_parts.append(rod('Dial graduation',start,end,.0019,iron,vertices=8))
    watch_parts.extend([
        rod('Hour hand',(0,0,.041),(.021,.033,.041),.0023,iron),
        rod('Minute hand',(0,0,.042),(0,.055,.042),.0018,iron),
        sphere('Dial pivot',(0,0,.045),(.005,.005,.004),brass),
        sphere('Palm',(-.035,-.042,-.012),(.091,.06,.029),skin),
    ])
    for i in range(4):
        watch_parts.append(sphere('Curled finger',(-.066+i*.023,-.069,.006),(.011,.046,.017),skin))
    hand=pivot('Timekeeper and hand',watch_parts,hand_origin)
    elbow=Vector((-.19,.20,1.06))
    sleeve=rod('Right coat forearm',elbow,hand_origin,.092,cloth,.062)
    sleeve_length=(Vector(hand_origin)-elbow).length
    rod('Right coat sleeve',(-.035,.21,1.39),(-.19,.20,1.06),.108,cloth,.089)

    vertices=[(x*1.8,y*1.8,-1.98+.105*math.sin(x*.71+y*.31)+.12*math.cos(y*.49+x*.16))
              for y in range(-45,46) for x in range(-45,46)]
    sea=mesh('Atlantic swell',vertices,
             [(y*91+x,y*91+x+1,(y+1)*91+x+1,(y+1)*91+x) for y in range(90) for x in range(90)],water)
    for f in sea.data.polygons:
        f.use_smooth=True
    land=material('Distant volcanic land',(.091,.110,.089),rough=.88)
    land_x=[-12,-9,-6,-4,-2,0,2,5,8,12]
    land_z=[0,.22,.58,1.44,1.52,1.19,1.27,.61,.33,0]
    mesh('Reconstructed island skyline',
         [(-41,x+4,z-1.96) for x,z in zip(land_x,land_z,strict=True)]
         +[(-40,16,-2.19),(-40,-8,-2.19)], [tuple(range(12))], land)
    for i in range(4):
        line('Taut side rope', [(-5.5,1.68,1+i*.02),(5.6,1.67,.81+i*.02)],.009,rope)

    center=Vector((0,0,-28))
    sphere('Time and meridian globe',center,(1.26,1.26,1.26),globe)
    for j in (-45,-20,0,20,45):
        latitude=math.radians(j)
        line('Globe latitude', [center+Vector((1.265*math.cos(latitude)*math.cos(a*math.tau/80),
              1.265*math.cos(latitude)*math.sin(a*math.tau/80),1.265*math.sin(latitude))) for a in range(81)],
              .007, silver)
    for j in range(-75,91,15):
        angle=math.radians(j)
        line('Meridian', [center+Vector((1.268*math.cos(i*math.pi/36)*math.cos(angle),
             1.268*math.cos(i*math.pi/36)*math.sin(angle),1.268*math.sin(i*math.pi/36))) for i in range(-18,19)],
             .019 if j in (0,15) else .008, warm if j==0 else cool if j==15 else silver)
    for j, color in ((0,warm),(15,cool)):
        a=math.radians(j)
        sphere('Location on meridian',center+Vector((1.134*math.cos(a),1.134*math.sin(a),.57)),(.051,)*3,color)
    world=scene.world
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.44,.56,.67,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.51
    lamp('Low sun',(-10,-4,8),3.1,(1,.78,.55),kind='SUN')
    lamp('Sky fill',(0,-4,6),680,(.65,.8,1),size=6)
    lamp('Globe light',(4,1,-24),520,(.54,.76,1),target=center)

    def animate(t):
        lift=smooth((t-2.6)/2.3)
        hand.location=(-.35-.12*lift,.31-.14*lift,1.12+.23*lift)
        hand.rotation_euler=(.26*lift,-.54*lift,-.30*lift)
        arm=hand.location-elbow
        sleeve.location=elbow+arm/2
        sleeve.scale.z=arm.length/sleeve_length
        sleeve.rotation_euler=arm.to_track_quat('Z','Y').to_euler()
        head.rotation_euler.y=.12*lift
        sea.location.x=-.4*t
        if t < 5:
            u=t/5
            camera(scene,(-3.65+.53*u,-2.74+.63*u,1.95+.05*math.sin(t*2)),
                   (.55,.17,1.34),32)
        elif t < 9:
            u=(t-5)/4
            camera(scene,(-.98+.05*u,-.28+.12*u,1.89-.08*u),hand.location,49)
        elif t < 13.5:
            u=(t-9)/4.5
            camera(scene,(4.7,1.32-.49*u,-25.9),center,42)
        else:
            u=(t-13.5)/4.5
            camera(scene,(.82-.39*u,1.18+.09*u,1.48+.07*u),(-41,4,-.96),46)

    return 18, animate


EYE=Vector((3.5,0,2.6))
COIN=Vector((0,0,.12))
RIM_X, RIM_Z = .82, .86
WATER_INDEX=1.333


def interface(height):
    lo, hi=0, EYE.x
    for _ in range(48):
        x=(lo+hi)/2
        water_sine=x/math.hypot(x,height-COIN.z)
        air_sine=(EYE.x-x)/math.hypot(EYE.x-x,EYE.z-height)
        if WATER_INDEX*water_sine < air_sine:
            lo=x
        else:
            hi=x
    return Vector(((lo+hi)/2,0,height))


def optics(scene):
    table=material('Ivory terrazzo work surface',(.57,.55,.47),rough=.56)
    glaze=material('Blue enamel bowl',(.018,.19,.24),rough=.24)
    rim=material('Ivory rim',(.69,.78,.78),rough=.27)
    gold=material('Brass coin',(.85,.48,.10),rough=.28,metal=.72)
    gold_dark=material('Stamped lines',(.38,.17,.022),rough=.37,metal=.63)
    white=material('Light through water and air',(.06,.78,.69),emission=2.8)
    warm=material('Straight-line extension',(.98,.56,.10),emission=1.7)
    water=material('Water, IOR 1.333',(.95,.995,1))
    nodes=water.node_tree.nodes
    refraction=nodes.new('ShaderNodeBsdfGlass')
    refraction.inputs['Color'].default_value=(.95,.995,1,1)
    refraction.inputs['Roughness'].default_value=0
    refraction.inputs['IOR'].default_value=WATER_INDEX
    water.node_tree.links.new(refraction.outputs[0],nodes.get('Material Output').inputs['Surface'])
    box('Work surface',(0,0,-.115),(200,200,.23),table)
    box('Enamel vessel bottom',(0,0,.05),(1.70,1.38,.13),glaze,.025)
    front=[]
    for x in (-RIM_X,RIM_X):
        obj=box('Front wall' if x>0 else 'Back wall',(x,0,.48),(.055,1.43,.705),glaze,.014)
        bead=rod('Lip', (x,-.716,.837),(x,.716,.837),.022,rim)
        if x>0:
            front.extend((obj,bead))
    for sign in (-1,1):
        obj=box('Vessel side',(0,sign*.687,.48),(1.62,.050,.71),glaze,.014)
        bead=rod('Lip',(-.81,sign*.687,.837),(.81,sign*.687,.837),.022,rim)
        if sign<0:
            front.extend((obj,bead))
    rod('Coin', (0,0,.115),(0,0,.132),.225,gold,vertices=64)
    line('Raised border',[(.185*math.cos(i*math.tau/64),.185*math.sin(i*math.tau/64),.1335)
                         for i in range(65)],.0045,gold_dark)
    for y, length in ((-.054,.105),(0,.147),(.054,.105)):
        rod('Raised coin stamp',(-length/2,y,.134),(length/2,y,.134),.009,gold_dark)
    rim_section=box('Cut edge of occluding rim',(RIM_X,-.709,.485),(.055,.059,.75),rim,.008)
    pour_x,pour_y=-.52,.44
    stream=rod('Water entering vessel',(pour_x,pour_y,0),(pour_x,pour_y,1),.021,water,.026)
    droplets=[sphere('Water drop',(pour_x,pour_y,0),(.028,.028,.047),water) for _ in range(5)]
    fluid=box('Closed water volume',(0,0,.42),(1.589,1.316,.60),water,0)
    section=box('Explanatory water cross-section',(0,0,.409),(1.589,.036,.623),
                material('Section water plane',(.03,.31,.38),rough=.32),0)
    join=interface(.74)
    rays=[
        line('Refracted ray',[COIN+Vector((0,-.709,0)),join+Vector((0,-.709,0)),EYE+Vector((0,-.709,0))],.012,white),
        sphere('Surface crossing',join+Vector((0,-.709,0)),(.031,)*3,white),
    ]
    scale=join.x/(EYE.x-join.x)
    apparent=Vector((0,-.71,join.z-scale*(EYE.z-join.z)))
    for i in range(7):
        a,b=i/7,(i+.54)/7
        start=join.lerp(apparent,a)
        end=join.lerp(apparent,b)
        start.y=end.y=-.711
        rays.append(line('Back projection',[start,end],.008,warm))
    rays.append(sphere('Back-projected point', apparent, (.028,)*3,warm))
    rays.append(sphere('Observer',EYE+Vector((0,-.709,0)),(.04,)*3,white))
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.64,.70,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.47
    lamp('Large left window',(-3,-4,6),1700,(.78,.88,1),size=5)
    lamp('Warm reflection',(0,3,4),910,(1,.87,.68),size=2.8)

    def animate(t):
        explain=7.1<=t<12.6
        height=.12+.62*smooth((t-2.15)/3.2)
        if t>=12.6:
            height=.74-.62*smooth((t-14.1)/2.45)
        fluid.scale.z=max(.004,(height-.107)/.60)
        fluid.location.z=(height+.107)/2
        fluid.hide_render=explain or height<=.144
        pouring=2.15<t<5.34
        stream.hide_render=not pouring
        stream.location.z=(height+1.44)/2
        stream.scale.z=1.44-height
        for i,drop in enumerate(droplets):
            drop.hide_render=not pouring
            phase=((t-2.15)*3.5+i/len(droplets))%1
            drop.location.z=1.44-(1.44-height)*phase**1.8
        for obj in front:
            obj.hide_render=explain
        section.hide_render=not explain
        rim_section.hide_render=not explain
        for i,obj in enumerate(rays):
            obj.hide_render=not explain or (i>=2 and t<9.4)
        if explain:
            scene.camera.data.type='ORTHO'
            scene.camera.data.ortho_scale=5.4
            camera(scene,(1.21,-7.1,2.65),(1.21,-.66,1.28),48)
        else:
            scene.camera.data.type='PERSP'
            camera(scene,EYE,(.05,0,.42),46)

    return 17, animate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('topic',choices=('nautical','optics'))
    parser.add_argument('output',type=Path)
    parser.add_argument('--sample',type=float,action='append')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.world=bpy.data.worlds.new('Environment')
    bpy.ops.object.camera_add()
    scene.camera=bpy.context.object
    scene.camera.data.clip_end=160
    scene.render.engine='CYCLES' if args.topic=='optics' else 'BLENDER_EEVEE'
    if args.topic=='optics':
        scene.cycles.samples=12
        scene.cycles.use_denoising=True
        scene.cycles.max_bounces=7
    scene.render.resolution_x=640
    scene.render.resolution_y=360
    scene.render.resolution_percentage=100
    scene.render.fps=12
    scene.render.image_settings.file_format='JPEG'
    scene.render.image_settings.quality=90
    scene.view_settings.view_transform='AgX'
    duration,animate={'nautical':nautical,'optics':optics}[args.topic](scene)
    times = args.sample if args.sample else [f/scene.render.fps for f in range(duration*scene.render.fps)]
    animate(times[0])
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'scene.blend'))
    for i,t in enumerate(times):
        scene.frame_set(i+1)
        animate(t)
        scene.render.filepath=str(args.output/f'{i:04d}.jpg')
        bpy.ops.render.render(write_still=True)
        print(f'Finished {args.topic} frame {i+1}/{len(times)} at {t:.3f}s',flush=True)


if __name__=='__main__':
    main()
