"""Re-edit the original M185 Blender plates against the measured Neil cues."""

import argparse
import json
from pathlib import Path

from mechanical_video_next.episode import FPS, assemble, measure_narration
from scripts.common import filehash, probe, run, writejson
from scripts.narration import load_env


def encode(args, frames, output):
    run(["ffmpeg", "-v", "error", "-xerror", "-y", *args, "-an",
         "-frames:v", frames, "-c:v", "libx264", "-preset", "fast", "-crf", 16,
         "-pix_fmt", "yuv420p", output])
    if int(probe(output)["streams"][0]["nb_frames"]) != frames:
        raise ValueError(f"Incorrect picture duration: {output}")
    return output


def retime(source, output, frames, marks):
    """Map output frame landmarks to the original plate in source seconds."""
    splits = len(marks) - 1
    names = [f"[in{i}]" for i in range(splits)]
    segments = [f"[part{i}]" for i in range(splits)]
    filters = [f"[0:v]split={splits}{''.join(names)}"]
    for i, ((first, start), (last, end)) in enumerate(zip(marks, marks[1:])):
        count = last - first
        ratio = count / FPS / (end - start)
        filters.append(
            f"{names[i]}trim=start={start:.6f}:end={end:.6f},"
            f"setpts=(PTS-STARTPTS)*{ratio:.8f},fps={FPS},"
            f"tpad=stop_mode=clone:stop={count},trim=end_frame={count}{segments[i]}"
        )
    filters.append(f"{''.join(segments)}concat=n={splits}:v=1:a=0,"
                   f"tpad=stop_mode=clone:stop={frames}[out]")
    return encode(["-i", source, "-filter_complex", ";".join(filters), "-map", "[out]"],
                  frames, output)


def comparison(sources, work, frames, answer_end):
    # Compare the same four state changes at the same real output times.
    # The first single-channel states settle inside the first second.
    timeline = (0, 8, 26, answer_end - 8, answer_end + 7,
                answer_end + 18, answer_end + 33, answer_end + 44, answer_end + 60)
    forward_time = (1.22, 1.30, 1.94, 3.58, 4.20, 5.37, 6.00, 6.79, 7.43)
    reverse_time = (2.10, 2.175, 2.958, 3.654, 4.35, 5.568, 6.264, 6.525, 7.308)
    forward = retime(sources[3], work / "forward.mp4", frames,
                     list(zip(timeline, forward_time, strict=True)))
    reverse = retime(sources[4], work / "reverse.mp4", frames,
                     list(zip(timeline, reverse_time, strict=True)))
    font = "/System/Library/Fonts/STHeiti Medium.ttc"
    filters = [
        "[0:v]crop=1500:930:225:110,scale=930:576,setsar=1[left]",
        "[1:v]crop=1500:930:225:110,scale=930:576,setsar=1[right]",
        "[left][right]hstack,pad=1920:1080:30:272:0x192b33[base]",
        "[2:v]crop=850:1040:190:0,scale=198:242,setsar=1[mouse]",
        "[base][mouse]overlay=861:16",
        f"drawtext=fontfile='{font}':text='正拨':fontsize=61:fontcolor=white:x=435:y=164",
        f"drawtext=fontfile='{font}':text='反拨':fontsize=61:fontcolor=white:x=1365:y=164[out]",
    ]
    graph = ";".join(filters[:4]) + ";" + ",".join(filters[4:])
    return encode(["-i", forward, "-i", reverse, "-i", sources[0],
                   "-filter_complex_threads", 2, "-filter_complex", graph, "-map", "[out]"],
                  frames, work / "comparison.mp4")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_receipt", type=Path)
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--opening-preview", action="store_true")
    args = parser.parse_args()
    episode = Path(__file__).resolve().parent
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    load_env(args.env_file)
    edit = json.loads((episode / "recut-edit.json").read_text())
    speech = measure_narration(episode, edit)
    source_rows = json.loads(args.source_receipt.read_text())["shots"]
    sources = {}
    for source in source_rows:
        path = Path(source["file"])
        if filehash(path) != source["sha256"]:
            raise ValueError(f"Source clip hash mismatch: {path}")
        sources[source["shot"]] = path

    counts = [frames for _, _, frames in speech]
    answer_end = round(speech[0][1][1]["end"] * FPS)
    opening = comparison(sources, work, counts[0], answer_end)
    if args.opening_preview:
        print(assemble(episode, dict(edit, shots=edit["shots"][:1]),
                       [opening], speech[:1], work, preview_shots=1))
        return

    teardown = retime(sources[1], work / "teardown.mp4", counts[1], [
        (0, .40), (76, 3.22), (96, 4.83), (161, 6.91), (counts[1], 7.35),
    ])
    macro = retime(sources[2], work / "macro.mp4", counts[2], [
        (0, 0), (53, 2.91), (88, 6.42), (216, 7.87), (counts[2], 10.68),
    ])
    cycle = retime(sources[3], work / "full-cycle.mp4", counts[3], [
        (0, 0), (41, 1.30), (74, 1.94), (92, 3.58), (127, 4.20),
        (167, 5.37), (198, 6.00), (218, 6.79), (246, 7.43),
        (counts[3], 8.03),
    ])
    closing = encode(["-i", sources[5], "-vf", "tpad=stop_mode=clone:stop=60"],
                     counts[4], work / "closing.mp4")
    writejson(work / "timing.json", counts)
    print(assemble(episode, edit, [opening, teardown, macro, cycle, closing], speech, work))


if __name__ == "__main__":
    main()
