"""Revise the existing SR-FC106 panel from the photographed cover and controls."""

import json
from math import cos, pi, sin
from pathlib import Path
import sys

import bpy


def add_button(vertices, faces, materials, x, y, finish):
    start = len(vertices)
    sides = 32
    for height in (.001, .009):
        for index in range(sides):
            angle = 2 * pi * index / sides
            c, s = cos(angle), sin(angle)
            px = x + .093 * (1 if c >= 0 else -1) * abs(c)**.5
            py = y + .056 * (1 if s >= 0 else -1) * abs(s)**.5
            vertices.append((px, py, .096 + .10 * py + height))
    faces.append(tuple(start + index for index in reversed(range(sides))))
    faces.append(tuple(start + sides + index for index in range(sides)))
    for index in range(sides):
        adjacent = (index + 1) % sides
        faces.append((start + index, start + adjacent, start + sides + adjacent, start + sides + index))
    materials.extend([finish] * (sides + 2))


def revise(baseline, out):
    bpy.ops.wm.open_mainfile(filepath=str(baseline / 'sr-fc106-bezel.blend'))
    panel = bpy.data.objects['Front face']
    old = panel.data
    vertices = [tuple(vertex.co) for vertex in old.vertices]
    faces = [tuple(face.vertices) for face in old.polygons]
    materials = [face.material_index for face in old.polygons]
    if len(vertices) != 256 or len(faces) != 256:
        raise ValueError('Expected the existing two-surface, 64-point SR-FC106 bezel')

    # Repair photo 7 shows a recess between the shoulders of the rear edge.
    # Preserve the opening and the curved front lip seen in photos 6 and 7.
    for index in (*range(64), *range(128, 192)):
        x, y, z = vertices[index]
        if y > .25 and abs(x) < .45:
            offset = .13 * min(1, (.45 - abs(x)) / .09)
            vertices[index] = (x, y - offset, z - .10 * offset)

    for x, y, finish in [(-.625, .036, 1), (-.625, -.099, 1),
                         (.625, .036, 2), (.625, -.099, 1)]:
        add_button(vertices, faces, materials, x, y, finish)

    mesh = bpy.data.meshes.new('SR-FC106 inset bezel and control keys')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(old.materials[0])
    for name, color in [('Slate keys', (.20, .23, .27, 1)), ('Cook key', (.78, .53, .13, 1))]:
        material = bpy.data.materials.new(name)
        material.diffuse_color = color
        mesh.materials.append(material)
    for polygon, finish in zip(mesh.polygons, materials, strict=True):
        polygon.material_index = finish
    panel.data = mesh
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'rice-panel.blend'), compress=True)


revise(*map(Path, sys.argv[sys.argv.index('--') + 1:]))
