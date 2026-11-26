"""Compare both complete encoder cycles in the existing moving draft."""

import argparse
import json
from pathlib import Path

from mechanical_video_next.episode import assemble, measure_narration, recut_picture
from scripts.common import ROOT, filehash, probe
from scripts.narration import load_env

from recut import encode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_receipt", type=Path)
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    episode = Path(__file__).resolve().parent
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    load_env(args.env_file)
    edit = json.loads((episode / "value-edit.json").read_text())
    edit["output"] = "鼠标滚轮｜四步顺序怎样辨方向.mp4"
    forward, reverse = sorted(
        (row for row in json.loads(args.source_receipt.read_text())["shots"] if row["shot"] in (3, 4)),
        key=lambda row: row["shot"],
    )
    sources = [ROOT / row["file"] for row in (forward, reverse)]
    for path, row in zip(sources, (forward, reverse), strict=True):
        if filehash(path) != row["sha256"]:
            raise ValueError(f"Original 3D plate hash differs: {path}")
    speech = measure_narration(episode, edit)
    frames = speech[3][2]
    for path in sources:
        available = int(probe(path)["streams"][0]["nb_frames"])
        if not frames - 30 <= available <= frames:
            raise ValueError("The comparison must show one complete cycle at original speed")
    font = "/System/Library/Fonts/STHeiti Medium.ttc"
    graph = (
        "[0:v]crop=1500:930:225:110,scale=930:576,setsar=1,tpad=stop_mode=clone:stop=30[f];"
        "[1:v]crop=1500:930:225:110,scale=930:576,setsar=1,tpad=stop_mode=clone:stop=30[r];"
        "[f][r]hstack,pad=1920:1080:30:243:0x192b33,"
        f"drawtext=fontfile='{font}':text='正拨':fontsize=58:fontcolor=white:x=435:y=98,"
        f"drawtext=fontfile='{font}':text='反拨':fontsize=58:fontcolor=white:x=1365:y=98,"
        f"drawtext=fontfile='{font}':text='左边先亮甲，右边先亮乙':fontsize=43:fontcolor=white:x=(w-tw)/2:y=171:"
        "enable='gte(t,1.7)',"
        f"drawtext=fontfile='{font}':text='两边都变化四次，方向要看先后':fontsize=43:fontcolor=white:"
        "x=(w-tw)/2:y=846:enable='gte(t,7.3)'[out]"
    )
    cycle = encode(["-i", sources[0], "-i", sources[1], "-filter_complex_threads", "2",
                    "-filter_complex", graph, "-map", "[out]"], frames, work / "direction-cycle.mp4")
    plates = [cycle if index == 3 else recut_picture(episode, shot["picture"], count, work)
              for index, (shot, (_, _, count)) in enumerate(zip(edit["shots"], speech, strict=True))]
    print(assemble(episode, edit, plates, speech, work, preview_shots=len(plates)))


if __name__ == "__main__":
    main()
