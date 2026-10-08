"""Render the PostTrainLLM launch film from repo-owned evidence screenshots.

Run: python3 marketing/video/x-launch-2026-09-26/render.py --preview
     python3 marketing/video/x-launch-2026-09-26/render.py

Uses Pillow and ffmpeg already present on the creator's Mac. No model is loaded.
The captions are deliberately readable with audio muted on X.
"""

from __future__ import annotations

import argparse
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
W, H, FPS = 1920, 1080, 30
DURATION = 30.0
SCENES = [0.0, 3.7, 7.4, 11.1, 14.8, 18.7, 22.5, 26.1, 30.0]
INK = (235, 240, 242)
MUTED = (151, 164, 170)
TEAL = (75, 224, 189)
CORAL = (255, 113, 99)
PAPER = (10, 14, 17)
MONO_PATH = "/Users/sarthak/Library/Fonts/JetBrainsMonoNerdFontMono-Regular.ttf"
DISPLAY_PATH = "/System/Library/Fonts/Avenir Next.ttc"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    if weight == "mono":
        return ImageFont.truetype(MONO_PATH, size)
    return ImageFont.truetype(
        DISPLAY_PATH, size, index={"bold": 0, "demi": 2, "regular": 7}[weight]
    )


F = {
    "brand": font(30, "demi"),
    "mono20": font(20, "mono"),
    "mono24": font(24, "mono"),
    "mono28": font(28, "mono"),
    "body32": font(32),
    "body38": font(38),
    "head60": font(60, "demi"),
    "head82": font(82, "bold"),
    "head100": font(100, "bold"),
    "head118": font(118, "bold"),
    "metric170": font(170, "bold"),
}


def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


def smooth(x: float) -> float:
    x = clamp(x)
    return x * x * (3 - 2 * x)


def visible(t: float, start: float = 0.1, span: float = 0.65) -> float:
    return smooth((t - start) / span)


def faded(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return tuple(round(PAPER[i] * (1 - alpha) + color[i] * alpha) for i in range(3))


def label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    color=TEAL,
    alpha=1.0,
    size="mono24",
) -> None:
    draw.text(xy, text.upper(), font=F[size], fill=faded(color, alpha), spacing=3)


def line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    size="head100",
    color=INK,
    alpha=1.0,
) -> None:
    draw.text(xy, text, font=F[size], fill=faded(color, alpha), stroke_width=0)


def make_base() -> Image.Image:
    im = Image.new("RGB", (W, H), PAPER)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((690, -380, 2190, 920), fill=(24, 75, 65, 110))
    glow = glow.filter(ImageFilter.GaussianBlur(170))
    im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(im)
    for x in range(80, W, 120):
        d.line((x, 0, x, H), fill=(17, 24, 26), width=1)
    for y in range(70, H, 120):
        d.line((0, y, W, y), fill=(17, 24, 26), width=1)
    return im


def screenshot_card(filename: str, width: int = 1190) -> Image.Image:
    source = Image.open(ROOT / "artifacts/design/issue-176" / filename).convert("RGB")
    height = round(source.height * width / source.width)
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (1, 1, width - 2, height - 2), radius=22, fill=255
    )
    rgba = source.convert("RGBA")
    rgba.putalpha(mask)
    return rgba


BASE = make_base()
GALLERY = screenshot_card("after-gallery.png")
RUN = screenshot_card("after-generate.png")


def chrome(im: Image.Image, t: float, scene_number: int) -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((90, 60, 127, 97), radius=9, outline=TEAL, width=2)
    d.arc((98, 67, 120, 89), 195, 350, fill=TEAL, width=4)
    d.text((145, 60), "posttrainllm", font=F["brand"], fill=INK)
    label(d, (1480, 67), "ONE MAC / OPEN RESEARCH", color=MUTED, size="mono20")
    d.line((90, 124, W - 90, 124), fill=(48, 65, 62), width=1)
    label(d, (90, 1024), f"{scene_number:02d} / 08", color=MUTED, size="mono20")
    d.line((220, 1042, W - 90, 1042), fill=(44, 62, 59), width=2)
    d.line((220, 1042, 220 + round((W - 310) * t / DURATION), 1042), fill=TEAL, width=2)
    return d


def card(im: Image.Image, source: Image.Image, x: int, y: int, reveal: float) -> None:
    reveal = smooth(reveal)
    if reveal <= 0:
        return
    sw, sh = source.size
    width = max(1, round(sw * reveal))
    cropped = source.crop((0, 0, width, sh))
    shadow = Image.new("RGBA", (sw + 70, sh + 70), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((20, 20, 20 + sw, 20 + sh), radius=26, fill=(0, 0, 0, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    im.paste(shadow, (x - 35, y - 22), shadow)
    im.paste(cropped, (x, y), cropped)


def scene(im: Image.Image, n: int, local: float, global_t: float) -> None:
    d = chrome(im, global_t, n + 1)
    a = visible(local)
    dy = round(25 * (1 - a))
    if n == 0:
        label(d, (110, 245), "INTRODUCING / POSTTRAINLLM")
        line(d, (100, 338), "A research lab.", size="head118")
        line(
            d,
            (100, 470),
            "One Mac.",
            size="head118",
            color=TEAL,
            alpha=visible(local, 0.02, 0.45),
        )
        d.line(
            (108, 658, 100 + round(720 * visible(local, 0.62, 1.1)), 658),
            fill=TEAL,
            width=3,
        )
        line(
            d,
            (110, 712),
            "Train  ·  adapt  ·  evaluate  ·  package",
            size="body38",
            color=MUTED,
            alpha=visible(local, 0.75),
        )
        label(
            d,
            (110, 842),
            "OPEN SOURCE  /  APPLE SILICON",
            color=MUTED,
            alpha=visible(local, 1.0),
            size="mono28",
        )
    elif n == 1:
        label(d, (110, 244), "NATIVE MAC APP  /  0.2.0", alpha=a)
        line(d, (100, 337 + dy), "Pick a model.", size="head82", alpha=a)
        line(
            d,
            (100, 435 + dy),
            "Start a run.",
            size="head82",
            color=TEAL,
            alpha=visible(local, 0.35),
        )
        line(
            d,
            (110, 595),
            "Local checkpoints.",
            size="body38",
            color=MUTED,
            alpha=visible(local, 0.8),
        )
        line(
            d,
            (110, 650),
            "One place to work.",
            size="body38",
            color=MUTED,
            alpha=visible(local, 0.9),
        )
        card(im, GALLERY, round(770 + 42 * (1 - a)), 180, (local - 0.38) / 0.85)
    elif n == 2:
        label(d, (110, 244), "LOCAL EXECUTION  /  REAL OUTPUT", alpha=a)
        line(d, (100, 337 + dy), "Run locally.", size="head82", alpha=a)
        line(
            d,
            (100, 435 + dy),
            "Inspect the result.",
            size="head82",
            color=TEAL,
            alpha=visible(local, 0.35),
        )
        line(
            d,
            (110, 595),
            "Prompt, completion,",
            size="body38",
            color=MUTED,
            alpha=visible(local, 0.8),
        )
        line(
            d,
            (110, 650),
            "settings, device.",
            size="body38",
            color=MUTED,
            alpha=visible(local, 0.9),
        )
        card(im, RUN, round(770 + 42 * (1 - a)), 180, (local - 0.38) / 0.85)
    elif n == 3:
        label(d, (110, 226), "THE FACTORY LOOP", alpha=a)
        line(d, (100, 316 + dy), "From target to report.", size="head100", alpha=a)
        d.line((110, 595, 1780, 595), fill=(52, 71, 67), width=3)
        progress = visible(local, 0.4, 2.0)
        d.line((110, 595, 110 + round(1670 * progress), 595), fill=TEAL, width=4)
        names = ["target", "data", "post-train", "eval", "package", "report"]
        for i, name in enumerate(names):
            x = 110 + i * 286
            active = visible(local, 0.45 + i * 0.28, 0.45)
            d.rounded_rectangle(
                (x, 550, x + 260, 770),
                radius=18,
                fill=(19, 27, 30),
                outline=(43, 91, 80) if active else (45, 59, 59),
                width=2,
            )
            label(d, (x + 24, 576), f"0{i + 1}", alpha=active, size="mono20")
            line(d, (x + 24, 649), name, size="body38", alpha=active)
        label(
            d,
            (110, 843),
            "FROZEN BASELINE FIRST  /  REGRESSIONS INCLUDED",
            color=MUTED,
            alpha=visible(local, 1.5),
            size="mono24",
        )
    elif n == 4:
        label(d, (110, 215), "ONE SPECIALIST  /  MEASURED AGAINST STOCK", alpha=a)
        line(d, (100, 303 + dy), "A real, bounded win.", size="head100", alpha=a)
        d.rounded_rectangle(
            (100, 505, 1000, 838),
            radius=20,
            fill=(19, 29, 30),
            outline=(44, 86, 77),
            width=2,
        )
        line(
            d,
            (135, 540),
            "12/12",
            size="metric170",
            color=TEAL,
            alpha=visible(local, 0.48),
        )
        label(
            d,
            (140, 762),
            "FILE-OPS HARD GATE",
            color=INK,
            alpha=visible(local, 0.7),
            size="mono28",
        )
        d.rounded_rectangle(
            (1030, 505, 1815, 838),
            radius=20,
            fill=(19, 29, 30),
            outline=(44, 86, 77),
            width=2,
        )
        line(d, (1070, 540), "2.42×", size="metric170", alpha=visible(local, 0.75))
        label(
            d,
            (1080, 762),
            "DEPTH WALL SPEED",
            color=INK,
            alpha=visible(local, 0.94),
            size="mono28",
        )
        label(
            d,
            (110, 890),
            "QWEN3-4B REST FUSED  /  ROUTED FILE OPERATIONS",
            color=MUTED,
            alpha=visible(local, 1.15),
            size="mono20",
        )
    elif n == 5:
        label(d, (110, 215), "THE REGRESSION STAYS VISIBLE", color=CORAL, alpha=a)
        line(d, (100, 314 + dy), "25/45", size="metric170", color=CORAL, alpha=a)
        line(d, (110, 553), "on breadth.", size="head82", alpha=visible(local, 0.42))
        d.line((110, 695, 1810, 695), fill=(74, 67, 65), width=2)
        line(
            d,
            (110, 735),
            "Decision: keep it routed.",
            size="head60",
            color=INK,
            alpha=visible(local, 0.75),
        )
        label(
            d,
            (110, 855),
            "ROUTED FILE OPS ONLY  /  TRADEOFF REPORTED",
            color=MUTED,
            alpha=visible(local, 1.12),
            size="mono24",
        )
    elif n == 6:
        label(d, (110, 228), "THE LAB IS PUBLIC", alpha=a)
        line(d, (100, 316 + dy), "76 experiments.", size="head100", alpha=a)
        line(
            d,
            (100, 426 + dy),
            "18 recipes.",
            size="head100",
            color=TEAL,
            alpha=visible(local, 0.25),
        )
        line(
            d,
            (100, 536 + dy),
            "9 learning paths.",
            size="head100",
            alpha=visible(local, 0.48),
        )
        d.line((110, 714, 1810, 714), fill=(57, 77, 73), width=2)
        label(
            d,
            (110, 765),
            "NEXT: CHOOSE A NEW SPECIALIST TARGET. FROZEN EVAL FIRST.",
            color=INK,
            alpha=visible(local, 0.8),
            size="mono24",
        )
        label(
            d,
            (110, 838),
            "WEEKLY UPDATES: WINS, FAILURES, AND LESSONS.",
            color=TEAL,
            alpha=visible(local, 1.1),
            size="mono24",
        )
    else:
        label(d, (110, 228), "OPEN SOURCE  /  SIGNED AND NOTARIZED FOR MAC", alpha=a)
        line(d, (100, 340 + dy), "Build a specialist.", size="head118", alpha=a)
        line(
            d,
            (100, 475 + dy),
            "Prove it on one Mac.",
            size="head100",
            color=TEAL,
            alpha=visible(local, 0.3),
        )
        d.line(
            (110, 685, 110 + round(1700 * visible(local, 0.6, 1.5)), 685),
            fill=TEAL,
            width=3,
        )
        line(
            d, (110, 737), "posttrainllm.com", size="head60", alpha=visible(local, 1.0)
        )
        label(
            d,
            (110, 860),
            "GET THE MAC APP  /  EXPLORE THE BROWSER LAB",
            color=MUTED,
            alpha=visible(local, 1.3),
            size="mono24",
        )


def render_at(t: float) -> Image.Image:
    idx = min(
        len(SCENES) - 2,
        next(
            (i for i in range(len(SCENES) - 1) if SCENES[i] <= t < SCENES[i + 1]),
            len(SCENES) - 2,
        ),
    )
    im = BASE.copy()
    scene(im, idx, t - SCENES[idx] + (1.25 if idx else 0), t)
    blend_start = SCENES[idx + 1] - 0.55
    if idx < len(SCENES) - 2 and t >= blend_start:
        nxt = BASE.copy()
        scene(nxt, idx + 1, t - SCENES[idx + 1] + 1.25, t)
        progress = smooth((t - blend_start) / 0.55)
        edge = round(-100 + (W + 200) * progress)
        mask = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mask)
        if edge > 60:
            md.rectangle((0, 0, min(W, edge - 60), H), fill=255)
        for x in range(max(0, edge - 60), min(W, edge + 60)):
            md.line((x, 0, x, H), fill=round(255 * (edge + 60 - x) / 120))
        im = Image.composite(nxt, im, mask)
    return im


def make_audio(path: Path) -> None:
    """Compose an original 128 BPM electronic cue; all information stays on screen."""
    sample_rate = 48000
    count = round(DURATION * sample_rate)
    beat = 60 / 128
    section = beat * 8
    rng = np.random.default_rng(20260926)
    audio = np.zeros((count, 2), dtype=np.float32)

    def add(start: float, signal: np.ndarray, pan: float = 0.0) -> None:
        offset = round(start * sample_rate)
        if offset < 0 or offset >= count:
            return
        signal = signal[: count - offset]
        angle = (pan + 1) * np.pi / 4
        audio[offset : offset + len(signal), 0] += signal * np.cos(angle)
        audio[offset : offset + len(signal), 1] += signal * np.sin(angle)

    def note(
        start: float,
        length: float,
        hz: float,
        level: float,
        kind: str,
        pan: float = 0.0,
    ) -> None:
        n = round(length * sample_rate)
        u = np.arange(n, dtype=np.float32) / sample_rate
        phase = 2 * np.pi * hz * u
        if kind == "pad":
            wave = (
                np.sin(phase + 0.12 * np.sin(2 * np.pi * 0.21 * u))
                + 0.28 * np.sin(2 * phase + 0.7)
                + 0.13 * np.sin(phase * 1.003 + 1.4)
            )
            env = np.minimum(1, u / 0.55) * np.minimum(1, (length - u) / 0.8)
        elif kind == "bass":
            wave = np.sin(phase) + 0.24 * np.sin(2 * phase)
            env = np.minimum(1, u / 0.025) * np.exp(-u * 1.55)
        elif kind == "bell":
            mod = 2.1 * np.exp(-u * 12) * np.sin(2 * phase)
            wave = np.sin(phase + mod) + 0.18 * np.sin(3 * phase)
            env = np.minimum(1, u / 0.008) * np.exp(-u * 3.8)
        elif kind == "lead":
            wave = np.sin(phase) + 0.18 * np.sin(2 * phase + 0.4)
            env = np.minimum(1, u / 0.025) * np.minimum(1, (length - u) / 0.22)
        add(start, (wave * env * level).astype(np.float32), pan)

    # Two bars per card. The harmony lifts for the proof, thins for the
    # disclosed regression, then resolves under the weekly-update card.
    chords = [
        (73.42, [293.66, 349.23, 440.00, 523.25, 659.25]),  # Dm9
        (58.27, [293.66, 349.23, 440.00, 587.33, 659.25]),  # Bbmaj9
        (87.31, [261.63, 329.63, 392.00, 440.00, 587.33]),  # Fmaj9
        (65.41, [261.63, 329.63, 392.00, 523.25, 587.33]),  # Cadd9
    ]
    for section_index in range(8):
        start = section_index * section
        root, tones = chords[section_index % 4]
        pad_level = 0.018 if section_index == 5 else 0.025
        for i, hz in enumerate(tones):
            note(start - 0.08, section + 0.34, hz, pad_level, "pad", -0.55 + i * 0.275)
        for beat_index in range(8):
            position = start + beat_index * beat
            if section_index >= 1:
                note(
                    position, 0.68, root, 0.105 if section_index != 5 else 0.055, "bass"
                )
            if section_index != 5 and beat_index in (0, 3, 4, 6):
                tone = tones[(beat_index + section_index) % len(tones)]
                note(
                    position + beat * 0.5,
                    0.56,
                    tone * 2,
                    0.034 if section_index < 4 else 0.042,
                    "bell",
                    -0.5 if beat_index % 2 else 0.5,
                )
        if section_index in (0, 4, 6, 7):
            melody = [tones[2], tones[3], tones[4], tones[3]]
            for i, hz in enumerate(melody):
                note(
                    start + (i * 2 + 0.5) * beat,
                    beat * 1.3,
                    hz,
                    0.024 if section_index == 0 else 0.035,
                    "lead",
                    -0.2 if i % 2 else 0.2,
                )

    def kick(start: float, level: float) -> None:
        u = np.arange(round(0.48 * sample_rate), dtype=np.float32) / sample_rate
        phase = 2 * np.pi * (47 * u + 24 * (1 - np.exp(-u * 24)) / 24)
        body = np.sin(phase) * np.exp(-u * 11)
        click = rng.standard_normal(len(u)).astype(np.float32) * np.exp(-u * 110)
        add(start, level * (body + 0.12 * click))

    def snare(start: float) -> None:
        u = np.arange(round(0.26 * sample_rate), dtype=np.float32) / sample_rate
        noise = rng.standard_normal(len(u)).astype(np.float32)
        snap = (noise * 0.7 + np.sin(2 * np.pi * 185 * u) * 0.3) * np.exp(-u * 22)
        add(start, 0.052 * snap)

    def hat(start: float, level: float, pan: float) -> None:
        u = np.arange(round(0.075 * sample_rate), dtype=np.float32) / sample_rate
        noise = rng.standard_normal(len(u)).astype(np.float32)
        hiss = noise - np.convolve(noise, np.ones(19) / 19, mode="same")
        add(start, (level * hiss * np.exp(-u * 55)).astype(np.float32), pan)

    for beat_index in range(64):
        position = beat_index * beat
        section_index = beat_index // 8
        if section_index == 0:
            if beat_index % 4 == 0:
                kick(position, 0.09)
            continue
        kick(position, 0.16 if section_index in (4, 6, 7) else 0.13)
        if beat_index % 4 in (1, 3) and section_index != 5:
            snare(position)
        if section_index != 5:
            hat(position, 0.026, -0.4)
            hat(position + beat / 2, 0.016, 0.45)

    # Small scene accents follow the picture rather than fighting the beat.
    for start in SCENES[1:-1]:
        kick(start, 0.12)
        note(start, 0.9, 880, 0.025, "bell", 0.3)

    t = np.arange(count, dtype=np.float32) / sample_rate
    fade = np.minimum(1.0, t / 0.6) * np.minimum(1.0, (DURATION - t) / 1.1)
    audio *= fade[:, None]
    audio *= 2.7
    audio *= min(1.0, 0.89 / float(np.max(np.abs(audio))))
    audio = np.clip(audio, -0.9, 0.9)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.preview:
        for t in (2.0, 5.5, 9.2, 13.1, 16.7, 20.4, 24.5, 28.0):
            render_at(t).save(OUT / f"preview-{t:04.1f}.png")
        print("Saved eight storyboard frames")
        return

    audio_path = OUT / "score-original.wav"
    make_audio(audio_path)
    output_path = OUT / "posttrainllm-x-launch.mp4"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(audio_path),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_path),
    ]
    with (OUT / "ffmpeg.log").open("wb") as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        assert process.stdin is not None
        try:
            for i in range(round(DURATION * FPS)):
                t = i / FPS
                frame = render_at(t)
                if i == round(5.5 * FPS):
                    frame.save(OUT / "posttrainllm-x-launch-poster.png")
                process.stdin.write(frame.tobytes())
                if i % (FPS * 5) == 0:
                    print(f"rendering {t:04.1f} / {DURATION:.1f}s", flush=True)
        finally:
            process.stdin.close()
        return_code = process.wait()
    if return_code:
        raise SystemExit(
            f"ffmpeg failed with code {return_code}; inspect {OUT / 'ffmpeg.log'}"
        )
    print(output_path)


if __name__ == "__main__":
    main()
