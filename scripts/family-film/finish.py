"""Prepare narration and assemble the recording with a separate, legible caption rail."""
import argparse
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORY = json.loads((Path(__file__).parent / "story.json").read_text(encoding="utf-8"))


def run(*command):
    subprocess.run([str(x) for x in command], check=True)


def ffmpeg(*args):
    run(os.environ.get("FFMPEG", "ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args)


def prepare(work):
    lengths = []
    for number, beat in enumerate(STORY):
        target = work / f"voice-{number}.wav"
        if not target.exists():
            aiff = work / f"voice-{number}.aiff"
            run("say", "-v", os.environ.get("NARRATOR", "Tingting"), "-r", "212", "-o", aiff, beat["line"])
            ffmpeg("-i", aiff, "-ac", "1", "-ar", "22050", target)
        with wave.open(str(target), "rb") as track:
            duration = track.getnframes() / track.getframerate()
            if duration < 1:
                raise ValueError(f"No narration rendered for {beat['id']}; supply a WAV in {target}")
            lengths.append(round(duration, 3))
    (work / "durations.json").write_text(json.dumps(lengths))
    print("Narrated seconds", round(sum(lengths), 1))


def render(work, media):
    from PIL import Image, ImageDraw, ImageFont
    media.mkdir(parents=True, exist_ok=True)
    timing = json.loads((work / "timeline.json").read_text())
    beats = timing["beats"]
    end = timing["end"]
    size = (1600, 108)
    font_path = os.environ.get("CAPTION_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")
    fonts = {n: ImageFont.truetype(font_path, n) for n in (16, 22, 31)}
    manifest = []
    pcm = bytearray(int((end + .35) * 22050) * 2)
    for index, beat in enumerate(beats):
        spec = STORY[index]
        start = beat["at"] if index else 0
        stop = beats[index + 1]["at"] if index + 1 < len(beats) else end
        rail = Image.new("RGB", size, "#132f38")
        draw = ImageDraw.Draw(rail)
        draw.text((37, 21), "LIVINGMIND  /  FAMILY FILM", font=fonts[16], fill="#8fc5d0")
        draw.text((36, 53), spec["chapter"], font=fonts[22], fill="#deeef0")
        draw.line((336, 23, 336, 86), fill="#43606a", width=1)
        draw.text((367, 40), spec["line"], font=fonts[31], fill="#f8faf9")
        if draw.textlength(spec["line"], font=fonts[31]) > 1198:
            raise ValueError("Subtitle exceeds safe area: " + spec["line"])
        draw.rectangle((0, 104, round(1600*(index+1)/len(STORY)), 107), fill="#74b9c9")
        name = f"caption-{index}.png"
        rail.save(work / name)
        manifest += [f"file '{name}'", f"duration {stop-start:.3f}"]
        with wave.open(str(work / f"voice-{index}.wav"), "rb") as stream:
            samples = stream.readframes(stream.getnframes())
        offset = round((beat["at"]+.24)*22050)*2
        if offset + len(samples) > round((stop+.1)*22050)*2:
            raise ValueError("Narration overlaps next shot: " + beat["id"])
        pcm[offset:offset+len(samples)] = samples
    manifest.append(f"file 'caption-{len(beats)-1}.png'")
    (work / "panels.txt").write_text("\n".join(manifest)+"\n")
    with wave.open(str(work / "narration.wav"), "wb") as track:
        track.setparams((1, 2, 22050, 0, "NONE", "PCM"))
        track.writeframes(pcm)
    movie = media / "family-evening.mp4"
    ffmpeg("-i", work / "capture.webm", "-f", "concat", "-safe", "0", "-i", work/"panels.txt",
           "-i", work/"narration.wav", "-filter_complex",
           "[0:v]fps=24,setsar=1,tpad=stop_duration=0.5:stop_mode=clone[top];[1:v]fps=24,setsar=1[bottom];[top][bottom]vstack=inputs=2[v]",
           "-map", "[v]", "-map", "2:a", "-t", f"{end:.3f}", "-c:v", "libx264",
           "-crf", "20", "-pix_fmt", "yuv420p", "-preset", "medium", "-c:a", "aac", "-b:a", "96k",
           "-movflags", "+faststart", movie)
    # Excerpt the text edit and device readback. Preserve the native screen recording.
    start = beats[2]["at"]
    duration = min(13, beats[4]["at"] - start)
    ffmpeg("-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", movie, "-filter_complex",
           "fps=4,scale=768:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=112[p];[b][p]paletteuse=dither=bayer",
           "-loop", "0", media/"family-preview.gif")
    for name in ("arrival", "coordination", "receipts"):
        shutil.copyfile(work / f"{name}.jpg", media / f"{name}.jpg")
    print(f"{end:.1f}s · {movie.stat().st_size:,} bytes · {movie}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["voices", "render"])
    parser.add_argument("work", type=Path)
    parser.add_argument("--media", type=Path, default=ROOT / "docs/media")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.step == "voices":
        prepare(args.work)
    else:
        render(args.work, args.media)
