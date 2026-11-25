"""Assemble the full mechanical revision from the new Blender sequences."""

import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from mechanical_video_next.episode import assemble
from mechanical_video_next.text_layout import measure_text
from revision import EPISODE, FPS, REMOVED_CLAUSE, SEAL_CUT_FRAME, close_speech, encode, frames, label
from scripts.common import ROOT, filehash, probe, run, writejson


OUTPUT = "水龙头只转一点，水为什么就停了-机械修订版.mp4"
BASELINE = "水龙头只转一点，水为什么就停了-修订版.mp4"
BASELINE_SHA = "ea655b5ebc09a465342da001baa914da359371a798f7417428bb50a983b2ab5b"
SHOT_FRAMES = (150, 289, 319, 327, 264, 283, 240)
REMOVED_DEFINITION = "阀杆和外面的铜壳加在一起，就是这颗阀芯。"


def clean_shots(work, previous, original_reopening):
    pictures = [previous / "revised-opening.mp4"]
    for shot, count in zip(("extract", "plates", "flow"), SHOT_FRAMES[1:4], strict=True):
        output = work / f"{shot}.mp4"
        encode(frames(work, shot), "[0:v]setsar=1[out]", count, output)
        pictures.append(output)

    closure = work / "closure.mp4"
    encode([*frames(work, "turn"), "-i", previous / "revised-closure.mp4"], (
        "[0:v]setsar=1[turn];"
        f"[1:v]trim=start_frame={SEAL_CUT_FRAME},setpts=PTS-STARTPTS,setsar=1[seal];"
        "[turn][seal]concat=n=2:v=1:a=0[out]"
    ), SHOT_FRAMES[4], closure)
    pictures.extend((closure, original_reopening))

    replay = work / "replay.mp4"
    left = label("把手与出水嘴", 44, 47)
    right = label("陶瓷片通水口", 1104, 47)
    encode(frames(work, "replay-exterior") + frames(work, "replay-ports"), (
        "[0:v]crop=1056:1080:400:0[left];[1:v]crop=864:1080[right];"
        f"[left][right]hstack,drawbox=x=1053:y=0:w=6:h=ih:color=0x142321:t=fill,{left},{right},setsar=1[out]"
    ), SHOT_FRAMES[6], replay)
    pictures.append(replay)
    return pictures


def extraction_speech(work, row):
    first, second = row["cues"]
    if second["text"] != REMOVED_DEFINITION:
        raise ValueError("Unexpected cartridge definition in the original narration")
    cut = (first["end"] + second["start"]) / 2
    output = work / "extraction-voice.wav"
    run(["ffmpeg", "-y", "-v", "error", "-xerror", "-i", row["audio"],
         "-af", f"atrim=end={cut},apad=whole_dur={row['frames'] / FPS}",
         "-c:a", "pcm_s16le", output])
    return output, [first], row["frames"]


def restore_opening_frame(output, opening):
    # The clean opening has no overlaid subtitles or cues at frame zero.
    # The reviewed Remotion export showed a tiled copy of the opening at frame zero.
    before_sha = filehash(output)
    with TemporaryDirectory(prefix=".opening-frame-", dir=output.parent) as folder:
        candidate = Path(folder) / output.name
        run(["ffmpeg", "-v", "error", "-xerror", "-i", output, "-i", opening,
             "-filter_complex",
             "[1:v]trim=end_frame=1,setpts=PTS-STARTPTS[head];"
             "[0:v]trim=start_frame=1,setpts=PTS-STARTPTS[tail];"
             f"[head][tail]concat=n=2:v=1:a=0,setpts=N/({FPS}*TB)[picture]",
             "-map", "[picture]", "-map", "0:a:0",
             "-c:v", "libx264", "-preset", "fast", "-crf", "15",
             "-r", str(FPS), "-pix_fmt", "yuv420p", "-color_range", "pc", "-colorspace", "bt470bg",
             "-c:a", "copy", "-movflags", "+faststart", candidate])
        if int(probe(candidate)["streams"][0]["nb_frames"]) != sum(SHOT_FRAMES):
            raise ValueError("Opening frame repair changed the runtime")
        run(["ffmpeg", "-v", "error", "-xerror", "-i", candidate,
             "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
        candidate.replace(output)
    return {"source_sha256": filehash(opening), "before_sha256": before_sha, "frame_index": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-work", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_work.resolve()
    previous = args.previous.resolve()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    baseline = ROOT / "output" / EPISODE.name / BASELINE
    if filehash(baseline) != BASELINE_SHA:
        raise ValueError("The previous export differs from the reviewed MP4")

    edit = json.loads((EPISODE / "edit.json").read_text())
    rows = json.loads((source / "local-speech.json").read_text())
    original_pictures = json.loads((source / "picture-sources.json").read_text())
    speech = [(Path(row["audio"]), row["cues"], row["frames"]) for row in rows]
    for row, (path, _, _) in zip(rows, speech, strict=True):
        if filehash(path) != row["sha256"]:
            raise ValueError(f"Original Neil cache mismatch: {path}")
    speech[1] = extraction_speech(work, rows[1])
    speech[4] = close_speech(work, rows[4])
    if tuple(row[2] for row in speech) != SHOT_FRAMES:
        raise ValueError("Narration timings differ from the Blender sequences")
    narration = "\n\n".join("\n".join(cue["text"] for cue in cues) for _, cues, _ in speech) + "\n"
    expected = (EPISODE / "narration.txt").read_text().replace(REMOVED_DEFINITION + "\n", "", 1)
    expected = expected.replace(REMOVED_CLAUSE, "", 1)
    if narration != expected:
        raise ValueError("Narration differs from the planned edit")

    pictures = clean_shots(work, previous, Path(original_pictures[5]))
    edit["output"] = OUTPUT
    edit["shots"][1]["labels"] = [[5.28, SHOT_FRAMES[1] / FPS, "旋出整颗阀芯"]]
    seal = edit["shots"][4]
    seal["subtitle_breaks"]["1"] = [[7.28, "实心的陶瓷盖住通水口，"]]
    output = assemble(EPISODE, edit, pictures, speech, work)

    props = json.loads((work / "edit-props.json").read_text())
    cues = props["cues"]
    if "".join(cue["text"] for cue in cues) != "".join(narration.splitlines()):
        raise ValueError("Subtitle text differs from narration")
    for cue in cues:
        if measure_text(cue["text"], size=64)["width"] > 1740:
            raise ValueError(f"Subtitle exceeds the safe width: {cue}")
    if any(left["end"] > right["start"] for left, right in zip(cues, cues[1:])):
        raise ValueError("Subtitle cues overlap")
    if cues[0]["start"] < 1 / FPS:
        raise ValueError("The first subtitle needs to be composited over the replacement frame")
    opening_repair = restore_opening_frame(output, pictures[0])
    script = work / "narration.txt"
    script.write_text(narration, encoding="utf-8")
    shutil.copyfile(script, output.with_name(f"{output.stem}-配音文案.txt"))
    writejson(work / "revision-sources.json", {
        "baseline_sha256": BASELINE_SHA,
        "final_sha256": filehash(output),
        "opening_frame_repair": opening_repair,
        "frames_by_shot": SHOT_FRAMES,
        "picture_sha256": [filehash(path) for path in pictures],
        "voice_sha256": [filehash(path) for path, _, _ in speech],
        "render_source_sha256": {
            name: filehash(EPISODE / name)
            for name in ("scene.py", "revision_scene.py", "revision.py",
                         "mechanism_revision_scene.py", "mechanism_revision.py")
        },
    })
    print(output)


if __name__ == "__main__":
    main()
