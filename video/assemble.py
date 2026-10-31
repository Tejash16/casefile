"""Assemble video/casefile-demo.mp4 from cards, clips and narration (a1).

Each segment lasts its narration + 0.3 s. Missing clips fall back to a still built from the real
run in out/career_overlap (S5b: the Substantiated finding; S6: verify.py on the log and on a
one-digit tampered copy).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "video"
RUN = ROOT / "out" / "career_overlap"
BUILD = V / "build"
ORDER = ["S1", "S2", "S3", "S4", "S5a", "S5b", "S6", "S7"]
CARDS = {"S1", "S2", "S7"}
W, H = 1920, 1080


def ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    hits = glob.glob(
        os.path.expanduser(r"~\AppData\Local\uv\cache\**\imageio_ffmpeg\binaries\ffmpeg*.exe"),
        recursive=True,
    )
    if not hits:
        sys.exit("no ffmpeg found; set FFMPEG")
    return hits[0]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=f) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return [*lines, cur] if cur else lines


def still(path: Path, title: str, blocks: list[tuple[str, str]]) -> None:
    """White 1920x1080 card: a title, then (colour, text) blocks."""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 18], fill="#6d28d9")
    d.text((110, 90), title, font=font(64, True), fill="#111827")
    y = 230
    for colour, text in blocks:
        f = font(44, colour != "#374151")
        for line in wrap(d, text, f, W - 220):
            d.text((110, y), line, font=f, fill=colour)
            y += 62
        y += 34
    img.save(path)


def s5b_still(path: Path) -> None:
    findings = json.loads((RUN / "findings.json").read_text(encoding="utf-8"))
    sub = [f for f in findings if f["verdict"] == "Substantiated"]
    rest = [f for f in findings if f["verdict"] != "Substantiated"]
    case = (RUN / "case_file.md").read_text(encoding="utf-8")
    m = re.search(r"^- (H\d+ is Substantiated:.*?)(?: \[\[E|$)", case, re.M)
    blocks = []
    for f in sub:
        who = f"{', '.join(f.get('subjects') or [])} -> {', '.join(f.get('objects') or [])}"
        blocks.append(("#b91c1c", f"SUBSTANTIATED  {f['hypothesis_id']} "
                                  f"{f.get('typology', '')}  {who}"))
    if m:
        blocks.append(("#374151", m.group(1)))
    blocks.append(("#374151", "Two independent kinds of proof (Crustdata career record + ledger "
                              "billing pattern); the coded gate decides, not the AI."))
    blocks.append(("#6b7280", f"{len(rest)} other allegations: Unfounded or Unsubstantiated. "
                              "Nobody is accused without evidence."))
    still(path, "Findings", blocks)


def s6_still(path: Path) -> None:
    log = RUN / "log.jsonl"
    ok = subprocess.run([sys.executable, str(ROOT / "verify.py"), str(log)],
                        capture_output=True, text=True).stdout.strip().splitlines()
    lines = log.read_text(encoding="utf-8").splitlines()
    mid = len(lines) // 2
    tampered = re.sub(r"\d", lambda d: str((int(d.group()) + 1) % 10), lines[mid], count=1)
    tdir = BUILD / "tamper"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "log.jsonl").write_text("\n".join([*lines[:mid], tampered, *lines[mid + 1:]]) + "\n",
                                    encoding="utf-8")
    shutil.copy(RUN / "root.txt", tdir / "root.txt")
    bad = subprocess.run([sys.executable, str(ROOT / "verify.py"), str(tdir / "log.jsonl")],
                         capture_output=True, text=True).stdout.strip().splitlines()
    still(path, "Audit log: hash-chained, verifiable", [
        ("#374151", f"$ python verify.py out/{RUN.name}/log.jsonl   ({len(lines)} records)"),
        ("#15803d", ok[-1] if ok else "VERIFY OK"),
        ("#374151", f"Change one digit in record {mid} and verify again:"),
        ("#b91c1c", next((x for x in bad if "FAIL" in x), bad[-1] if bad else "FAILED")),
    ])


def segment(seg: str, dur: float, out: Path, ff: str) -> None:
    audio = V / "audio" / f"{seg}.wav"
    clip = V / "clips" / f"{seg}.webm"
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:white,fps=30,format=yuv420p")
    if seg in CARDS:
        vin = ["-loop", "1", "-t", f"{dur}", "-i", str(V / "cards" / f"{seg}.png")]
    elif clip.exists():
        vin = ["-i", str(clip)]
        vf = f"tpad=stop_mode=clone:stop_duration={dur}," + vf
    else:
        png = BUILD / f"{seg}.png"
        {"S5b": s5b_still, "S6": s6_still}[seg](png)
        vin = ["-loop", "1", "-t", f"{dur}", "-i", str(png)]
    cmd = [ff, "-y", "-loglevel", "error", *vin, "-i", str(audio), "-map", "0:v:0", "-map",
           "1:a:0", "-vf", vf, "-af", "apad", "-t", f"{dur}", "-c:v", "libx264", "-preset",
           "veryfast", "-crf", "20", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)]
    subprocess.run(cmd, check=True)


def main() -> None:
    ff = ffmpeg()
    BUILD.mkdir(parents=True, exist_ok=True)
    timings = json.loads((V / "audio" / "timings.json").read_text(encoding="utf-8"))
    parts = []
    for seg in ORDER:
        dur = round(float(timings[seg]) + 0.3, 2)
        out = BUILD / f"{seg}.mp4"
        segment(seg, dur, out, ff)
        parts.append(out)
        print(f"{seg}: {dur}s")
    listing = BUILD / "concat.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    final = V / "casefile-demo.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                    str(listing), "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    probe = subprocess.run([ff, "-i", str(final)], capture_output=True, text=True).stderr
    print(re.search(r"Duration: [\d:.]+", probe).group(), final)


if __name__ == "__main__":
    main()
