import bpy
import json
import math
from pathlib import Path
import sys
from mathutils.bvhtree import BVHTree

scene = bpy.context.scene
out = Path(sys.argv[sys.argv.index('--') + 1])
names = dict(
    spring='30 continuous wire arc spring', wall='Annular spring channel, outer wall',
    inner='Annular spring channel, inner wall', shaft='66 continuous square spindle',
    base='48 hub with actual square opening', moving='Moving driver with swept square aperture',
    stationary='Opposite driver with swept square aperture', wood='Door panel with a through bore',
    upper='Stationary spring seat', lower='Moving spring seat',
    top_stop='Stationary driver stop', lower_stop='Moving driver home stop',
    ring='Housing face', cover='Cover plate with spindle opening', moving_arm='Driven radial arm',
    opposite_arm='Stationary radial arm and stop face',
)
pairs = [
    ('spring','wall'), ('spring','inner'), ('spring','top_stop'), ('spring','lower_stop'),
    ('shaft','base'), ('shaft','moving'), ('shaft','stationary'), ('shaft','wood'),
    ('shaft','cover'), ('moving','stationary'), ('moving_arm','inner'),('opposite_arm','inner'),
]
rows = []
for frame in [1,46,85,157,421,501,541,581,631,701,731,776,821,865,900,985,998,1100,1200]:
    scene.frame_set(frame)
    graph = bpy.context.evaluated_depsgraph_get()
    shapes = {}
    positions = {}
    for key, name in names.items():
        obj = bpy.data.objects[name].evaluated_get(graph)
        mesh = obj.to_mesh()
        pos = [obj.matrix_world @ vert.co for vert in mesh.vertices]
        faces = [list(face.vertices) for face in mesh.polygons]
        shapes[key] = BVHTree.FromPolygons(pos, faces, epsilon=0)
        positions[key] = pos
        obj.to_mesh_clear()
    found = {f'{a}/{b}': len(shapes[a].overlap(shapes[b])) for a,b in pairs}
    native = shapes['spring'].overlap(shapes['spring'])
    nonlocal_collision = [(a,b) for a,b in native
                          if abs(a//10-b//10) > 2 and max(a,b) < len(positions["spring"]) - 10]
    def sampled_min_gap(wire, seat):
        return min(shapes[seat].find_nearest(pt)[3] for pt in wire)
    rows.append(dict(frame=frame, seconds=(frame-1)/30, intersections=found,
                     nonlocal_spring_surface_overlap=len(nonlocal_collision),
                     upper_seat_gap=sampled_min_gap(positions['spring'][:10],'upper'),
                     lower_seat_gap=sampled_min_gap(positions['spring'][-10:],'lower')))
out.write_text(json.dumps(dict(samples=rows, methods='Evaluated native mesh BVH triangle overlap, wire ring edge to seat sampling; surface tests do not establish solid volume or force'),indent=2)+'\n')
