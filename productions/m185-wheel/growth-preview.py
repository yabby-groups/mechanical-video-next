"""Compare both directions using the M185 PCB revision's original Blender clips."""

import argparse
from pathlib import Path

from mechanical_video_next.episode import assemble, measure_narration
from scripts.common import digest, filehash, run
from scripts.narration import load_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    episode = Path(__file__).resolve().parent
    work = args.cache.resolve() / "growth-preview"
    work.mkdir(exist_ok=True)
    load_env(args.env_file)
    edit = {
        "title": "", "narration": "growth-narration.txt",
        "output": "M185｜两路触点的先后顺序.mp4",
        "bgm": "assets/audio/bgm/starter/quiet-link-technology.flac",
        "shots": [{"tail": .35}, {"tail": .35}],
    }
    speech = measure_narration(episode, edit)
    scene = filehash(episode / "scene.py")

    def source(shot, frames):
        key = digest(dict(scene=scene, shot=shot, frames=frames, fps=30))
        return args.cache.resolve() / key / f"shot-{shot}.mp4"

    comparison, teardown = work / "comparison.mp4", work / "teardown.mp4"
    font = "/System/Library/Fonts/STHeiti Medium.ttc"
    run([
        "ffmpeg", "-v", "error", "-y", "-ss", "1.10", "-i", source(3, 242),
        "-ss", "1.975", "-i", source(4, 261), "-i", source(0, 164),
        "-filter_complex",
        "[0:v]crop=1500:920:225:110,scale=940:576,setsar=1,tpad=stop_mode=clone:stop_duration=6[f];"
        "[1:v]crop=1500:920:225:110,scale=940:576,setsar=1,tpad=stop_mode=clone:stop_duration=6[r];"
        "[f][r]hstack,pad=1920:1080:20:230:0x17282f[base];"
        "[2:v]crop=1400:1080:0:0,scale=240:-2,setsar=1,tpad=stop_mode=clone:stop_duration=8[inset];"
        "[base][inset]overlay=840:24:eof_action=pass,"
        f"drawtext=fontfile='{font}':text='正拨':fontsize=54:fontcolor=white:x=422:y=139,"
        f"drawtext=fontfile='{font}':text='反拨':fontsize=54:fontcolor=white:x=1362:y=139,"
        f"drawtext=fontfile='{font}':text='观察灯 · 示意':fontsize=30:fontcolor=white:x=w-tw-52:y=52",
        "-frames:v", speech[0][2], "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", comparison,
    ])
    run([
        "ffmpeg", "-v", "error", "-y", "-ss", "0.32", "-i", source(1, 322),
        "-vf", "tpad=stop_mode=clone:stop_duration=3", "-frames:v", speech[1][2],
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", teardown,
    ])
    print(assemble(episode, edit, [comparison, teardown], speech, work, preview_shots=2))


if __name__ == "__main__":
    main()
