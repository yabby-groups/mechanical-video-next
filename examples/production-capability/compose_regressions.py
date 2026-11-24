"""Compose localized comparisons using the existing native and measured speech clocks."""

import argparse
import json
from math import cos, hypot, radians, sin
from pathlib import Path
import subprocess

from mechanical_video_next.joint_timeline import FPS, binding, bound
from scripts.common import ROOT, probe, writejson


def ffmpeg(out, *args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *map(str, args), str(out)],
                   check=True, cwd=out.parent)


def pair(out, before, after, *, audio=False):
    sound = ['-map', '1:a', '-c:a', 'copy'] if audio else ['-an']
    ffmpeg(out, '-i', before, '-i', after, '-filter_complex',
           '[0:v]scale=640:360[l];[1:v]scale=640:360[r];[l][r]hstack=shortest=1[out]',
           '-map', '[out]', *sound, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart')


def bin_contacts(out, source, upper, lower):
    # These three render passes use the same native channel samples. The
    # side view locates the upper and lower contacts in the complete assembly.
    graph = (
        '[0:v]crop=550:720:390:0,pad=744:720:97:0:0x232e3f[side];'
        '[side][1:v][2:v]xstack=inputs=3:layout=0_0|748_4|748_364:'
        'fill=0x232e3f:shortest=1,pad=1280:720:0:0:0x232e3f[out]'
    )
    ffmpeg(out, '-i', source, '-i', upper, '-i', lower, '-filter_complex', graph, '-map', '[out]', '-an',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart')


def ass_clock(frame):
    hundredths = round(frame * 100 / FPS)
    seconds, fraction = divmod(hundredths, 100)
    minutes, second = divmod(seconds, 60)
    return f'0:{minutes:02d}:{second:02d}.{fraction:02d}'


def glyph(points):
    start, *rest = [f'{round(x * 1.2)} {round(y * 1.2)}' for x, y in points]
    return f'm {start} l ' + ' '.join(rest)


def torque_glyph(angle):
    # Plate-specific coordinates in the authored 640x360 axial shot. The
    # gold seat revolves around the spindle. The guide illustrates the tangent
    # of the spring at that seat. Its arrow carries no force magnitude.
    pivot_x, pivot_y = 288, 170
    dx = -34 * cos(angle) - 101 * sin(angle)
    dy = -34 * sin(angle) + 101 * cos(angle)
    seat_x, seat_y = pivot_x + dx, pivot_y + dy
    radius = hypot(dx, dy)
    rx, ry = dx / radius, dy / radius
    tx, ty = ry, -rx
    radius_mark = glyph([(pivot_x + rx * distance + ry * side, pivot_y + ry * distance - rx * side)
                         for distance, side in [(7, -1.3), (radius, -1.3), (radius, 1.3), (7, 1.3)]])
    arrow = glyph([(seat_x + tx * length + rx * width, seat_y + ty * length + ry * width)
                   for length, width in [(0, -2), (41, -2), (41, -6), (54, 0),
                                         (41, 6), (41, 2), (0, 2)]])
    pivot = glyph([(pivot_x, pivot_y - 5), (pivot_x + 5, pivot_y),
                   (pivot_x, pivot_y + 5), (pivot_x - 5, pivot_y)])
    return radius_mark + ' ' + arrow + ' ' + pivot


def door_torque(out, previous):
    plan = json.loads((previous / 'after-blueprint.json').read_text())['timeline']
    measured = json.loads((previous / 'after-neil.json').read_text())
    samples = json.loads((previous / 'native-motion.json').read_text())['samples']
    release = plan['shots'][-1]
    source_shift = release['source_start_frame'] - release['start_frame']
    cue = next(row for row in plan['narration'] if row['id'] == 'release-2')
    start = cue['start_frame']
    home = 883 - source_shift
    captions = (previous / 'after.ass').read_text().replace(
        '[Events]',
        'Style: Guide,Heiti SC,18,&H008EF6FF,&H00FFFFFF,&H00163142,&HFF000000,'
        '0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1\n[Events]')
    captions = '\n'.join(line for line in captions.splitlines()
                         if not line.startswith('Dialogue: 0,0:00:17.00')) + '\n'
    for frame in range(start, home):
        angle = radians(samples[frame + source_shift]['active_driver'])
        vector = torque_glyph(angle)
        style = r'{\an7\pos(0,0)\bord1\shad0\1c&H8EF6FF&\3c&H163142&\p1}'
        captions += f'Dialogue: 1,{ass_clock(frame)},{ass_clock(frame + 1)},Guide,,0,0,0,,{style}{vector}\n'
    # The final explanation still uses the same Neil and foley edit. Use the
    # exact source AAC packets so the new picture leaves the mix untouched.
    subtitles = out.with_suffix('.ass')
    subtitles.write_text(captions)
    picture = previous / 'after-picture.mp4'
    original = previous / 'door-handle-pacing-candidate.mp4'
    bound(measured['narration_audio'])
    ffmpeg(out, '-i', picture, '-i', original, '-vf', f'ass={subtitles.name}', '-map', '0:v',
           '-map', '1:a', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart')
    return [start, home]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    out = parser.parse_args().out.resolve()
    previous_door = ROOT / 'output/door-handle-pacing-regression-20261123'
    bin_source = out / 'bin-source.mp4'
    bin_detail = out / 'bin-contacts.mp4'
    door_before = previous_door / 'door-handle-pacing-candidate.mp4'
    door_after = out / 'door-torque.mp4'
    bin_contacts(bin_detail, bin_source, out / 'bin-upper.mp4', out / 'bin-lower.mp4')
    pair(out / 'bin-before-after.mp4', bin_source, bin_detail)
    pair(out / 'rice-camera-only.mp4', out / 'rice-wide.mp4', out / 'rice-focus.mp4')
    pair(out / 'rice-before-after.mp4', out / 'rice-wide.mp4', out / 'rice-panel.mp4')
    guide_frames = door_torque(door_after, previous_door)
    pair(out / 'door-before-after.mp4', door_before, door_after, audio=True)
    inputs = [bin_source, bin_detail, door_before, door_after,
              out / 'rice-wide.mp4', out / 'rice-focus.mp4', out / 'rice-panel.mp4']
    writejson(out / 'media.json', {'media': [dict(binding(path), duration=probe(path)['format']['duration'])
                                           for path in inputs], 'door_guide_frames': guide_frames})


if __name__ == '__main__':
    main()
