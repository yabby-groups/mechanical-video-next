"""Blender-side first-frame checks and isolated diagnostic entry point."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

import bpy


def event(phase, **fields):
    print('MVN_RENDER ' + json.dumps(dict(phase=phase, **fields)), flush=True)


def render_settings(scene):
    engine = scene.render.engine
    return dict(version=bpy.app.version_string, engine=engine,
                device=scene.cycles.device if engine == 'CYCLES' else None,
                frame=scene.frame_current,
                resolution=[scene.render.resolution_x, scene.render.resolution_y,
                            scene.render.resolution_percentage],
                camera=scene.camera.name if scene.camera else None,
                lights=sorted(obj.name for obj in scene.objects if obj.type == 'LIGHT' and not obj.hide_render),
                materials=sorted({slot.material.name for obj in scene.objects if not obj.hide_render
                                  for slot in obj.material_slots if slot.material}),
                view_transform=scene.view_settings.view_transform,
                samples=scene.cycles.samples if engine == 'CYCLES' else
                getattr(scene.eevee, 'taa_render_samples', None) if engine == 'BLENDER_EEVEE' else None)


def render_preflight(scene, *, check_metal=True):
    event('preflight_start', **render_settings(scene))
    if not scene.camera:
        raise ValueError('MVN_SCENE_ERROR: No render camera')
    if check_metal and sys.platform == 'darwin' and scene.render.engine in {'BLENDER_EEVEE', 'BLENDER_WORKBENCH'}:
        import ctypes
        metal = ctypes.CDLL('/System/Library/Frameworks/Metal.framework/Metal')
        default_device = metal.MTLCreateSystemDefaultDevice
        default_device.restype = ctypes.c_void_p
        accessible = bool(default_device())
        event('metal_access', default_device_available=accessible)
        if not accessible:
            raise RuntimeError('MVN_GRAPHICS_INIT_ERROR: MTLCreateSystemDefaultDevice returned NULL in this Blender process')


def render_frame(scene, frame, path, *, preflight=False, recover=False, check_metal=True):
    scene.frame_set(frame)
    path = Path(path)
    if recover and path.is_file() and not path.is_symlink():
        import subprocess
        probe = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                                '-frames:v', '1', '-f', 'null', '-'], capture_output=True)
        if probe.returncode == 0:
            event('frame_reused', frame=frame, path=str(path))
            return False
        failed = path.parent / '.render-evidence'
        failed.mkdir(exist_ok=True)
        path.rename(failed / f'invalid-{time.time_ns()}-{path.name}')
    if preflight:
        render_preflight(scene, check_metal=check_metal)
    # A SIGABRT during an image write cannot expose a partial canonical frame.
    temporary = path.parent / '.render-evidence'
    temporary.mkdir(exist_ok=True)
    pending = temporary / f'{time.time_ns()}-{path.name}'
    scene.render.filepath = str(pending)
    if bpy.ops.render.render(write_still=True) != {'FINISHED'} or not pending.is_file():
        raise RuntimeError('MVN_RENDER_ERROR: Blender did not save the requested frame')
    with pending.open('rb') as saved:
        os.fsync(saved.fileno())
    pending.replace(path)
    if preflight:
        event('preflight_pass', frame=frame, reused=False)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('api', 'render'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--engine')
    parser.add_argument('--device', choices=('CPU', 'METAL'))
    parser.add_argument('--frame', type=int)
    parser.add_argument('--factory-scene', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.mode == 'api':
        event('api_ready', version=bpy.app.version_string, background=bpy.app.background)
        if not bpy.app.background:
            raise RuntimeError('Blender did not enter background mode')
        return

    scene = bpy.context.scene
    frame = args.frame if args.frame is not None else scene.frame_current
    scene.frame_set(frame)
    event('original_settings', **render_settings(scene))
    if args.engine:
        try:
            scene.render.engine = args.engine
        except TypeError as exc:
            raise RuntimeError(f'MVN_ENGINE_UNSUPPORTED: {args.engine}: {exc}') from exc
    if args.device == 'CPU':
        scene.cycles.device = 'CPU'
    elif args.device == 'METAL':
        prefs = bpy.context.preferences.addons['cycles'].preferences
        try:
            devices = [device for device in prefs.get_devices_for_type('METAL') if device.type == 'METAL']
        except TypeError:
            devices = []
        event('metal_devices', devices=[device.name for device in devices])
        if not devices:
            event('skipped', reason='Blender reported no compatible Cycles Metal device')
            return
        prefs.compute_device_type = 'METAL'
        for device in devices:
            device.use = True
        scene.cycles.device = 'GPU'
    if args.factory_scene:
        scene.render.resolution_x, scene.render.resolution_y = 160, 120
        scene.render.resolution_percentage = 100
        scene.cycles.samples = 4
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 4
    if args.output:
        scene.render.image_settings.file_format = 'PNG'
        # The diagnostic matrix deliberately exercises the actual render call
        # even when the production guard would decline to enter GPU setup.
        render_frame(scene, frame, args.output, preflight=True, check_metal=False)


if __name__ == '__main__':
    main()
