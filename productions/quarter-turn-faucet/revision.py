"""Assemble the faucet revision from original clean shots and revised Blender views."""

import argparse
import json
from pathlib import Path
import shutil

from mechanical_video_next.episode import assemble
from mechanical_video_next.text_layout import measure_text
from scripts.common import ROOT, filehash, probe, run, writejson

EPISODE = Path(__file__).resolve().parent
FPS = 30
OUTPUT = "水龙头只转一点，水为什么就停了-修订版.mp4"
BASELINE_SHA = "ef42007f8a0a2a09c2b1263acdb9fd9132f19ed6c1aae4c655b63d8bd9d7dce7"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
SEAL_CUT_FRAME = 138
REMOVED_CLAUSE = "等两个孔完全错开，"


def label(text, x, y, size=54, timing=""):
    return (f"drawtext=fontfile='{FONT}':text='{text}':x={x}:y={y}:fontsize={size}:"
            f"fontcolor=white:box=1:boxcolor=0x142321@0.88:boxborderw=12{timing}")


def frames(work, view):
    return ["-framerate", str(FPS), "-i", work / "full" / view / "%05d.jpg"]


def encode(args, filters, count, output):
    run(["ffmpeg", "-y", "-v", "error", "-xerror", *args, "-filter_complex", filters,
         "-map", "[out]", "-frames:v", count, "-c:v", "libx264", "-preset", "fast",
         "-crf", 16, "-pix_fmt", "yuv420p", output])
    picture = probe(output)["streams"][0]
    if (picture["width"], picture["height"], picture["r_frame_rate"], int(picture["nb_frames"])) != (
            1920, 1080, "30/1", count):
        raise ValueError(f"Incorrect revised shot length or size: {output}")


def opening(work):
    left = label("左把手与出水嘴", 44, 47)
    right = label("陶瓷片通水口", 1104, 47)
    # Labels enter once the camera has pulled back far enough to see each connection.
    stem = label("阀杆带动上片", 1390, 405, timing=":enable='gte(t,1.17)'")
    tab = label("下片卡在阀壳", 1390, 757, timing=":enable='gte(t,1.72)'")
    filters = (
        "[0:v]crop=1056:1080:400:0[left];[1:v]crop=864:1080[right];"
        f"[left][right]hstack,drawbox=x=1053:y=0:w=6:h=ih:color=0x142321:t=fill,{left},{right},setsar=1[head];"
        f"[2:v]{stem},{tab},setsar=1[tail];[head][tail]concat=n=2:v=1:a=0[out]"
    )
    output = work / "revised-opening.mp4"
    encode(frames(work, "exterior") + frames(work, "ports") + frames(work, "stem-final"),
           filters, 150, output)
    return output


def closure(work, original, count):
    ceramic = label("上片实心处", 1374, 386)
    inlet = label("水止于贴合面", 1374, 472, timing=":enable='gte(t,1.0)'")
    ceramic_leader = "drawbox=x=1200:y=411:w=162:h=3:color=white@0.85:t=fill"
    seal_leader = "drawbox=x=1115:y=484:w=247:h=3:color=0x78dcff:t=fill:enable='gte(t,1.0)'"
    # Resample the complete turn to fit the shorter cue.
    filters = (
        f"[0:v]trim=end_frame=173,setpts=(PTS-STARTPTS)*{SEAL_CUT_FRAME}/173,"
        f"fps={FPS},trim=end_frame={SEAL_CUT_FRAME},setsar=1[turn];"
        f"[1:v]trim=end_frame={count - SEAL_CUT_FRAME},{ceramic_leader},{seal_leader},"
        f"{ceramic},{inlet},setsar=1[seal];"
        "[turn][seal]concat=n=2:v=1:a=0[out]"
    )
    output = work / "revised-closure.mp4"
    encode(["-i", original, *frames(work, "seal")], filters, count, output)
    return output


def close_speech(work, source):
    first, final = source["cues"]
    text = final["text"].removeprefix(REMOVED_CLAUSE)
    if text == final["text"]:
        raise ValueError("Original Neil cue does not contain the expected clause")
    # Both joins are inside quiet intervals measured in the original Neil track.
    # The next intact phrase starts after 6.475 s in the source.
    audio = work / "revised-closure-voice.wav"
    run(["ffmpeg", "-v", "error", "-xerror", "-y", "-i", source["audio"],
         "-filter_complex",
         "[0:a]atrim=end=4.849,asetpts=PTS-STARTPTS[a];"
         "[0:a]atrim=start=6.379,asetpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=0:a=1[out]",
         "-map", "[out]", "-c:a", "pcm_s16le", audio])
    return audio, [first, {**final, "text": text, "end": round(final["end"] - 1.53, 3)}], 264


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-work", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--pictures-only", action="store_true")
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    edit = json.loads((EPISODE / "edit.json").read_text())
    baseline = ROOT / "output" / EPISODE.name / edit["output"]
    if filehash(baseline) != BASELINE_SHA:
        raise ValueError("The supplied original film does not match this revision")
    rows = json.loads((args.source_work / "local-speech.json").read_text())
    pictures = [Path(path) for path in json.loads((args.source_work / "picture-sources.json").read_text())]
    speech = [(Path(row["audio"]), row["cues"], row["frames"]) for row in rows]
    for row, (path, _, _) in zip(rows, speech, strict=True):
        if filehash(path) != row["sha256"]:
            raise ValueError(f"Original Neil cache mismatch: {path}")
    speech[4] = close_speech(work, rows[4])
    pictures[0] = opening(work)
    pictures[4] = closure(work, pictures[4], speech[4][-1])
    if args.pictures_only:
        return

    edit["output"] = OUTPUT
    seal = edit["shots"][4]
    seal["subtitle_breaks"]["1"] = [[7.28, "实心的陶瓷盖住通水口，"]]
    narration = "\n\n".join("\n".join(cue["text"] for cue in cues) for _, cues, _ in speech) + "\n"
    expected = (EPISODE / "narration.txt").read_text().replace(REMOVED_CLAUSE, "", 1)
    if narration != expected:
        raise ValueError("Revised narration does not match the planned edit")
    output = assemble(EPISODE, edit, pictures, speech, work)
    props = json.loads((work / "edit-props.json").read_text())
    if "".join(cue["text"] for cue in props["cues"]) != "".join(narration.splitlines()):
        raise ValueError("Subtitle text differs from the revised Neil track")
    for cue in props["cues"]:
        if measure_text(cue["text"], size=64)["width"] > 1740:
            raise ValueError(f"Subtitle exceeds the safe width: {cue}")
    if any(left["end"] > right["start"] for left, right in zip(props["cues"], props["cues"][1:])):
        raise ValueError("Revised subtitle cues overlap")
    script = work / "narration.txt"
    script.write_text(narration, encoding="utf-8")
    shutil.copyfile(script, output.with_name(f"{output.stem}-配音文案.txt"))
    writejson(work / "revision-sources.json", {
        "baseline_sha256": BASELINE_SHA,
        "final_sha256": filehash(output),
        "frames_by_shot": [row[2] for row in speech],
        "render_source_sha256": {
            name: filehash(EPISODE / name)
            for name in ("scene.py", "opening_scene.py", "revision_scene.py", "revision.py")
        },
        "edited_voice": {"original_sha256": rows[4]["sha256"], "removed_seconds": [4.849, 6.379],
                         "edited_sha256": filehash(speech[4][0])},
    })
    print(output)


if __name__ == "__main__":
    main()
