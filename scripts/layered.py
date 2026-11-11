"""Deterministic illustrated shots; normalized positions, image layers and parallax."""
import math
import subprocess
from pathlib import Path
from PIL import Image
from common import ROOT, budget, filehash, run, writejson


def sources(shot):
    if shot.get('render_route') not in {'2d', '2.5d'} or not shot.get('layers'):
        raise ValueError('Layered shot requires render_route and image layers')
    result = {}
    for layer in shot['layers']:
        path = ROOT / layer['path']
        if not path.is_file() or filehash(path) != layer.get('sha256'):
            raise ValueError('Layer source missing or changed: ' + str(path))
        with Image.open(path) as image:
            image.verify()
        result[str(path)] = layer['sha256']
    return result


def interpolate(item, t, defaults):
    start, end = item.get('from', {}), item.get('to', {})
    values = {k: start.get(k, v) * (1-t) + end.get(k, start.get(k, v)) * t
              for k, v in defaults.items()}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError('Nonfinite image transform')
    return values


def frame(shot, size, t):
    width, height = size
    canvas = Image.new('RGBA', size, shot.get('background', '#e5e7eb'))
    camera = interpolate(shot.get('camera_motion', {}), t, {'x': 0, 'y': 0, 'zoom': 1})
    for layer in shot['layers']:
        p = interpolate(layer, t, {'x': .5, 'y': .5, 'width': .8, 'scale': 1,
                                  'rotation': 0, 'opacity': 1})
        depth = float(layer.get('depth', 0)) if shot['render_route'] == '2.5d' else 0
        zoom = camera['zoom'] if shot['render_route'] == '2.5d' else 1
        if p['width'] <= 0 or p['scale'] <= 0 or zoom <= 0 or not math.isfinite(depth):
            raise ValueError('Invalid layer scale/depth')
        with Image.open(ROOT / layer['path']) as source:
            image = source.convert('RGBA')
        w = max(1, round(width * p['width'] * p['scale'] * zoom))
        h = max(1, round(w * image.height / image.width))
        if w*h > width*height*64:
            raise ValueError('Layer transform exceeds image memory allowance')
        image = image.resize((w, h), Image.Resampling.LANCZOS)
        image = image.rotate(p['rotation'], resample=Image.Resampling.BICUBIC, expand=True)
        image.putalpha(image.getchannel('A').point(lambda a: round(a*max(0, min(1, p['opacity'])))))
        x = (.5 + (p['x']-.5)*zoom - camera['x']*depth) * width
        y = (.5 + (p['y']-.5)*zoom - camera['y']*depth) * height
        canvas.alpha_composite(image, (round(x-image.width/2), round(y-image.height/2)))
    return canvas.convert('RGB')


def render(shot, folder, width, height, fps, quality):
    sources(shot)
    budget()
    count = round(shot['seconds'] * fps)
    if count < 2 or width % 2 or height % 2:
        raise ValueError('Layered video needs >=2 frames and even dimensions')
    folder.mkdir(parents=True, exist_ok=True)
    if quality in {'keys', 'checks'}:
        for index, t in enumerate((0, .5, 1)):
            frame(shot, (width, height), t).save(folder/f'key-{index}.png')
    else:
        # Stream RGB to the encoder, avoiding a full temporary PNG sequence.
        with (folder/'encode.log').open('w') as log:
            proc = subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo',
                '-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0',
                '-an','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',
                str(folder/'media.mp4')], stdin=subprocess.PIPE, stderr=log)
            try:
                for index in range(count):
                    if index % fps == 0:
                        budget()
                    proc.stdin.write(frame(shot, (width, height), index/(count-1)).tobytes())
                proc.stdin.close()
                if proc.wait():
                    raise RuntimeError('Layered encoding failed; see encode.log')
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        run(['ffmpeg','-v','error','-i',folder/'media.mp4','-f','null','-'], folder/'decode.log')
    writejson(folder/'checks.json', {'render_route': shot['render_route'],
        'source_hashes': sources(shot), 'frames': count, 'mechanics': 'UNKNOWN',
        'description': 'Illustrated prescribed motion; not contact simulation'})
