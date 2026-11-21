"""Assemble a silent film, its chapter track, and an animated repository preview."""
import argparse
import json
import math
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORY = json.loads((Path(__file__).parent / "story.json").read_text(encoding="utf-8"))


def ffmpeg(*args):
    executable = os.environ.get("FFMPEG", "ffmpeg")
    subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


def load_chapters(work):
    timeline = json.loads((work / "timeline.json").read_text(encoding="utf-8"))
    beats = timeline["beats"]
    if [beat["id"] for beat in beats] != [spec["id"] for spec in STORY]:
        raise ValueError("The captured chapters do not match story.json")
    boundaries = [0, *(beat["at"] for beat in beats[1:]), timeline["end"]]
    chapters = []
    for spec, start, stop in zip(STORY, boundaries, boundaries[1:]):
        if not math.isfinite(stop) or not start < stop:
            raise ValueError(f"Invalid timing for {spec['id']}")
        chapters.append((spec, round(start * 1000), round(stop * 1000)))
    return chapters


def timestamp(ms):
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{ms:03}"


def caption_rail(chapters, work):
    from PIL import Image, ImageDraw, ImageFont
    font = os.environ.get("CAPTION_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")
    small, medium, large = (ImageFont.truetype(font, n) for n in (18, 26, 32))
    manifest = []
    for index, (spec, start, stop) in enumerate(chapters):
        rail = Image.new("RGB", (1600, 108), "#132f38")
        draw = ImageDraw.Draw(rail)
        color = "#efcd8c" if "panel" in spec else "#94d6d1"
        label = "源码导读  /  CODE" if "panel" in spec else "家庭场景  /  APP"
        draw.text((38, 18), label, font=small, fill=color)
        draw.text((37, 48), spec["chapter"], font=medium, fill="#f4f7f5")
        draw.line((289, 20, 289, 85), fill="#46616a")
        if draw.textlength(spec["line"], font=large) > 1235:
            raise ValueError("Subtitle exceeds safe area: " + spec["line"])
        draw.text((323, 36), spec["line"], font=large, fill="#f8faf9")
        draw.rectangle((0, 104, round(1600 * stop / chapters[-1][2]) - 1, 107), fill=color)
        name = f"caption-{index:02}.png"
        rail.save(work / name)
        manifest.extend([f"file '{name}'", f"duration {(stop - start) / 1000:.3f}"])
    manifest.append(f"file '{name}'")
    (work / "panels.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")


def chapter_tracks(chapters, work, media):
    metadata = [";FFMETADATA1"]
    vtt = ["WEBVTT", ""]
    for spec, start, stop in chapters:
        metadata.extend(["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={stop}", "title=" + spec["chapter"]])
        vtt.extend([spec["id"], f"{timestamp(start)} --> {timestamp(stop)}", spec["chapter"], ""])
    (work / "chapters.ffmeta").write_text("\n".join(metadata) + "\n", encoding="utf-8")
    (media / "family-chapters.vtt").write_text("\n".join(vtt), encoding="utf-8")


def make_preview(chapters, movie, output):
    # A compact loop showing the proposal, its source rule and the per-device receipt.
    by_id = {spec["id"]: start / 1000 for spec, start, _ in chapters}
    excerpts = [("arrival", 1.8, 2.4), ("planning", .35, 4.5), ("receipt", 1.1, 3.2)]
    filters = ["[0:v]split=3[v0][v1][v2]"]
    for i, (chapter, offset, duration) in enumerate(excerpts):
        at = by_id[chapter] + offset
        filters.append(f"[v{i}]trim=start={at:.3f}:duration={duration},setpts=PTS-STARTPTS[c{i}]")
    filters.extend(["[c0][c1][c2]concat=n=3:v=1:a=0,fps=4,scale=800:-2:flags=lanczos,split[a][b]",
                    "[a]palettegen=max_colors=128[p]", "[b][p]paletteuse=dither=bayer"])
    ffmpeg("-i", movie, "-filter_complex", ";".join(filters), "-loop", "0", output)


def render(work, media):
    media.mkdir(parents=True, exist_ok=True)
    chapters = load_chapters(work)
    end = chapters[-1][2] / 1000
    caption_rail(chapters, work)
    chapter_tracks(chapters, work, media)
    movie = media / "family-evening.mp4"
    layout = ("[0:v]fps=24,setsar=1,tpad=stop_duration=0.5:stop_mode=clone[top];"
              "[1:v]fps=24,setsar=1[bottom];[top][bottom]vstack=inputs=2[v]")
    ffmpeg("-i", work / "capture.webm", "-f", "concat", "-safe", "0", "-i", work / "panels.txt",
           "-f", "ffmetadata", "-i", work / "chapters.ffmeta", "-filter_complex", layout,
           "-map", "[v]", "-map_metadata", "2", "-map_chapters", "2", "-an", "-t", f"{end:.3f}",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-preset", "medium",
           "-movflags", "+faststart", movie)
    planning_start = next(start for spec, start, _ in chapters if spec["id"] == "planning")
    ffmpeg("-ss", f"{planning_start / 1000 + 1:.3f}", "-i", movie, "-frames:v", "1",
           "-q:v", "2", media / "family-planning.jpg")
    make_preview(chapters, movie, media / "family-preview.gif")
    print(f"{end:.1f}s · {len(chapters)} chapters · {movie.stat().st_size:,} bytes · {movie}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["render"])
    parser.add_argument("work", type=Path)
    parser.add_argument("--media", type=Path, default=ROOT / "docs/media")
    args = parser.parse_args()
    render(args.work, args.media)
