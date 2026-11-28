"""Measure the section model on Blender's evaluated geometry."""


def section(scene, graph):
    def obj(name):
        return scene.objects[name].evaluated_get(graph)

    def extent(name, axis, select):
        part = obj(name)
        return select((part.matrix_world @ corner.co)[axis] for corner in part.data.vertices)

    def sample(graph):
        values = {
            'stem': obj('Blue stem').matrix_world.translation.z,
            'impact_gap': extent('Blue driver leg', 2, min) - extent('Blue impact seat -1', 2, max),
            'contact_gap': extent('Blue contact dot fixed', 0, min)
                           - extent('Blue contact dot moving', 0, max),
            'spring_scale': obj('Blue coil').scale.z,
        }
        if 'Red stem' in scene.objects:
            values['input_difference'] = values['stem'] - obj('Red stem').matrix_world.translation.z
            values['red_gap'] = extent('Red contact dot fixed', 0, min) - extent('Red contact dot moving', 0, max)
        return values

    return sample


RELATIONS = {'section': section}
