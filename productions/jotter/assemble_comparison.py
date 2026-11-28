"""Assemble the Jotter recut and a synchronized view of both openings."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

from scripts.narration import effective_profile, load_env, sentence

work = Path('work/creation-upgrade/jotter')
out = Path('output/creation-upgrade/jotter')
base = Path('output/jotter/按压式圆珠笔的工作原理.mp4')
music = Path('assets/audio/bgm/starter/quiet-link-curiosity.flac')
font = '/System/Library/Fonts/STHeiti Medium.ttc'

def prepare_audio(env_file):
    load_env(env_file)
    profile = effective_profile({'narration_profile': 'config/narration-neil.json'})
    script = {
        'opening': '同样按到底，左边的凸轮停在台阶上，右边却能退进导槽。笔尖就这样一出一进。',
        'ending': '两个按钮都弹回原位了，只有左边的笔芯还留在前面。记住上一次状态的，是这个转过一格的凸轮。',
    }
    for name, text in script.items():
        path, _ = sentence(text, profile)
        shutil.copyfile(path, work / f'{name}.wav')


def encode(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *map(str, args)], check=True)

def label(text, x, y, size, enable=None):
    active = f":enable='{enable}'" if enable else ''
    return (f"drawtext=fontfile='{font}':text='{text}':fontcolor=white:"
            f"fontsize={size}:x={x}:y={y}{active}")

def panel(start, motion, length, titles, captions, name):
    stream = f'trim=start={start}:duration={motion},setpts=PTS-STARTPTS,fps=30,scale=624:351,setsar=1,tpad=stop_mode=clone:stop_duration={length}'
    filters = f'[0:v]{stream}[a];[1:v]{stream}[b];[a][b]hstack=inputs=2,pad=1280:720:16:161:color=0x18242b'
    filters += ',' + label(titles[0], 48, 109, 30)
    filters += ',' + label(titles[1], 672, 109, 30)
    filters += ',drawbox=x=637:y=161:w=6:h=351:color=0x18242b:t=fill'
    for first, last, line in captions:
        filters += ',' + label(line, '(w-tw)/2', 588, 31, f'between(t,{first},{last})')
    filters += '[v];[2:a]adelay=140:all=1,volume=1.2[n];[3:a]volume=0.095[m];[n][m]amix=inputs=2:duration=longest:normalize=0[a]'
    encode('-framerate', 10, '-i', work/'frames/0-%03d.jpg',
           '-framerate', 10, '-i', work/'frames/1-%03d.jpg',
           '-i', work/f'{name}.wav', '-stream_loop', -1, '-i', music,
           '-filter_complex', filters, '-map', '[v]', '-map', '[a]', '-t', length,
           '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-preset', 'fast', '-crf', 18,
           '-ar', 48000, '-ac', 2, '-c:a', 'aac', '-b:a', '192k', work/f'{name}.mp4')

def timecode(ms):
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}'

def ms(code):
    h, m, s, t = map(int, re.split('[:,]', code))
    return (h*3600 + m*60 + s)*1000 + t

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    out.mkdir(parents=True, exist_ok=True)
    prepare_audio(args.env_file)
    opening = [(0.14, 1.24, '同样按到底，'),
                   (1.24, 3.22, '左边的凸轮停在台阶上，'),
                   (3.22, 5.34, '右边却能退进导槽。'),
                   (5.55, 7.5, '笔尖就这样一出一进。')]
    ending = [(0, 2.18, '两个按钮都弹回原位了。'),
              (2.18, 5.0, '只有左边的笔芯还留在前面。')]
    panel(0, 2.85, 7.5, ('初态一 · 笔尖收着', '初态二 · 笔尖伸出'), opening, 'opening')
    panel(0.75, 4.25, 5.0, ('停止在台阶 · 笔尖伸出', '退进导槽 · 笔尖收回'), ending, 'ending')
    encode('-i', work/'opening.mp4', '-ss', 7, '-t', '51.4', '-i', base, '-i', work/'ending.mp4',
           '-filter_complex', '[1:v]scale=1280:720,setsar=1,fps=30[mid];[1:a]aresample=48000,'
                              'aformat=channel_layouts=stereo[a1];[0:v][0:a][mid][a1][2:v][2:a]'
                              'concat=n=3:v=1:a=1[v][a]',
           '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', 18, '-preset', 'fast',
           '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out/'jotter-recut.mp4')

    cues = [(int(a*1000), int(b*1000), t) for a,b,t in opening]
    for row in base.with_suffix('.srt').read_text().strip().split('\n\n'):
        _, span, line = row.split('\n', 2)
        a, b = map(ms, span.split(' --> '))
        if a >= 7000 and b <= 58400:
            cues.append((a+500, b+500, line))
    cues.extend((58900+int(a*1000), 58900+int(b*1000), t) for a,b,t in ending)
    (out/'jotter-recut.srt').write_text('\n\n'.join(f'{i}\n{timecode(a)} --> {timecode(b)}\n{t}' for i,(a,b,t) in enumerate(cues,1))+'\n')

    # Left and right audio channels carry the corresponding version.
    encode('-i', base, '-i', out/'jotter-recut.mp4',
           '-filter_complex', "[0:v]scale=640:360,setsar=1[old];"
                              "[1:v]scale=640:360,setsar=1[new];"
                              "[old][new]hstack[v0];"
                              "[v0]pad=1280:424:0:64:color=0x18242b,"
                              +label('原版', 27, 14, 30)+','+label('改版', 667, 14, 30)+'[v];'
                              '[0:a]pan=mono|c0=0.5*c0+0.5*c1[oldaudio];'
                              '[1:a]pan=mono|c0=0.5*c0+0.5*c1[newaudio];'
                              '[oldaudio][newaudio]amerge=inputs=2[a]',
           '-map', '[v]', '-map', '[a]', '-t', '7.5', '-c:v', 'libx264', '-crf', 17,
           '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out/'jotter-opening-ab.mp4')



if __name__ == '__main__':
    main()
