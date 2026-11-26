#!/usr/bin/env python3
"""
Assemble-MushroomGaiden.py

Assembles MUSHROOM GAIDEN: DRAGON OF THE SHADOW CAP (Toad as Ryu Hayabusa &
Toadette as Ayane) from Google Flow keyframes and Omni 1.2 Flash video clips:
  1. Synthesizes a custom 142 BPM Japanese Taiko / Shamisen / Shakuhachi action
     score with frame-accurate vacuum-silence drops and sub-bass crater impacts.
  2. Grades and edits all 9 shots to 1920x1080 @ 24fps with kinetic pacing,
     1.0x locked JP lip-sync shots, and 3-5 frame Impact Hit-Stops (stylized ink
     flash + RGB chromatic split + damped camera shake).
  3. Preserves native Omni 1.2 Flash audio and optionally reinforces quiet JP
     dialogue shots via edge-tts, with -10 dB BGM ducking during speech.
  4. Exports two-pass EBU R128 mastered (-14.0 LUFS, -1.0 dBTP) dual masters:
       - masters/MUSHROOM_GAIDEN_ACTION_SHORT_JP_SUB.mp4
       - masters/MUSHROOM_GAIDEN_ACTION_SHORT_CLEAN.mp4
     plus storyboard_sheet.png and publish/MUSHROOM_GAIDEN_THUMBNAIL.png.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = PROJECT_ROOT / "frames"
VIDEOS_DIR = PROJECT_ROOT / "videos"
AUDIO_DIR = PROJECT_ROOT / "audio"
MASTERS_DIR = PROJECT_ROOT / "masters"
PUBLISH_DIR = PROJECT_ROOT / "publish"
SHOTS_PATH = PROJECT_ROOT / "shots.json"

WIDTH, HEIGHT = 1920, 1080
FPS = 24
SR = 48000
TARGET_LUFS = -14.0
TARGET_TP = -1.0

FONT_IMPACT = r"C:\Windows\Fonts\impact.ttf"
FONT_JP_BOLD = r"C:\Windows\Fonts\YuGothB.ttc"
FONT_DISPLAY = r"C:\Windows\Fonts\bahnschrift.ttf"
FONT_MONO = r"C:\Windows\Fonts\consolab.ttf"


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font with safe fallback."""
    if Path(path).is_file():
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def run_cmd(cmd: List[str], desc: str) -> subprocess.CompletedProcess:
    """Run a subprocess command and raise detailed context on non-zero exit."""
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({desc}):\n{' '.join(cmd)}\n{proc.stderr}")
    return proc


def probe_media(path: Path) -> Dict[str, Any]:
    """Return ffprobe metadata and EBU R128 loudness stats for a media file."""
    pr = run_cmd(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        f"ffprobe {path.name}",
    )
    info = json.loads(pr.stdout)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    ln = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", f"loudnorm=I={TARGET_LUFS:.1f}:TP={TARGET_TP:.1f}:LRA=11:print_format=json",
            "-f", "null", os.devnull,
        ],
        capture_output=True, text=True, check=False,
    )
    m = re.search(r'\{\s*"input_i"\s*:.*?\}', ln.stderr, flags=re.DOTALL)
    ld = json.loads(m.group(0)) if m else {}
    return {
        "path": str(path),
        "duration_sec": round(float(info["format"]["duration"]), 3),
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": v.get("r_frame_rate", ""),
        "pix_fmt": v.get("pix_fmt", ""),
        "sample_rate": int(a.get("sample_rate", 0)) if a else 0,
        "channels": int(a.get("channels", 0)) if a else 0,
        "integrated_lufs": round(float(ld["input_i"]), 2) if "input_i" in ld else None,
        "true_peak_db": round(float(ld["input_tp"]), 2) if "input_tp" in ld else None,
        "bytes": path.stat().st_size,
    }


def detect_audio_mean_db(path: Path) -> float:
    """Measure mean audio volume in dB for a clip."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", os.devnull],
        capture_output=True, text=True, check=False,
    )
    m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", proc.stderr)
    return float(m.group(1)) if m else -91.0


def fit_cover_pil(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize and center-crop an image cleanly to fill target dimensions."""
    src = img.convert("RGB")
    sw, sh = src.size
    scale = max(target_w / float(sw), target_h / float(sh))
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    x0 = (nw - target_w) // 2
    y0 = (nh - target_h) // 2
    return resized.crop((x0, y0, x0 + target_w, y0 + target_h))


def build_vignette_mask(w: int, h: int, strength: float = 0.28) -> np.ndarray:
    """Create a smooth float32 radial cinema vignette multiplier array (H, W, 1)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w * 0.5) / (w * 0.5)
    ny = (yy - h * 0.5) / (h * 0.5)
    r2 = nx * nx + ny * ny
    vig = np.clip(1.0 - strength * np.power(r2, 1.35), 0.55, 1.0)
    return vig[:, :, None]


VIGNETTE_1080P = build_vignette_mask(WIDTH, HEIGHT, strength=0.22)


def grade_cinema_frame(bgr: np.ndarray) -> np.ndarray:
    """Resize to 1080p and apply cohesive theatrical S-curve & subtle vignette."""
    if bgr.shape[1] != WIDTH or bgr.shape[0] != HEIGHT:
        bgr = cv2.resize(bgr, (WIDTH, HEIGHT), interpolation=cv2.INTER_LANCZOS4)
    f = bgr.astype(np.float32) / 255.0
    # Gentle filmic contrast S-curve + cool shadow / warm highlight separation
    f = np.clip((f - 0.5) * 1.06 + 0.5, 0.0, 1.0)
    f[:, :, 0] = np.clip(f[:, :, 0] + 0.015 * (1.0 - f[:, :, 0]), 0.0, 1.0)
    f[:, :, 2] = np.clip(f[:, :, 2] + 0.012 * f[:, :, 2], 0.0, 1.0)
    f *= VIGNETTE_1080P
    return np.clip(f * 255.0, 0, 255).astype(np.uint8)


def apply_hit_stop_fx(
    bgr: np.ndarray,
    step_idx: int,
    total_fx_frames: int,
    color_mode: str = "azure",
) -> np.ndarray:
    """
    Generate sakuga impact hit-stop frames:
      step 0: inverted stylized ink / high-contrast impact frame
      step 1: duotone burst frame (azure, magenta, or climax crimson-cyan)
      step 2+: RGB chromatic split + damped camera shake recovery
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    if step_idx == 0:
        # High-contrast inverted impact frame with crisp radial speed streak
        edges = cv2.Canny(gray, 70, 160)
        inv = 255 - np.clip(gray.astype(np.int32) * 1.35 - 40, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(inv, cv2.COLOR_GRAY2BGR)
        out[edges > 0] = (255, 255, 255)
        return out

    if step_idx == 1 and total_fx_frames >= 4:
        # High-energy duotone sakuga flash frame
        norm = np.clip((gray.astype(np.float32) - 45.0) / 170.0, 0.0, 1.0)
        out = np.zeros_like(bgr)
        if color_mode == "magenta":
            # Deep violet shadows -> electric pink-white highlights
            out[:, :, 0] = np.clip(45 + 210 * norm, 0, 255).astype(np.uint8)
            out[:, :, 1] = np.clip(10 + 185 * (norm ** 1.6), 0, 255).astype(np.uint8)
            out[:, :, 2] = np.clip(60 + 195 * norm, 0, 255).astype(np.uint8)
        elif color_mode == "climax":
            # High-contrast black shadows -> blistering gold-cyan highlights
            out[:, :, 0] = np.clip(255 * (norm ** 1.2), 0, 255).astype(np.uint8)
            out[:, :, 1] = np.clip(235 * (norm ** 1.1), 0, 255).astype(np.uint8)
            out[:, :, 2] = np.clip(255 * (norm ** 0.8), 0, 255).astype(np.uint8)
        else:
            # Azure-gold flash
            out[:, :, 0] = np.clip(55 + 200 * norm, 0, 255).astype(np.uint8)
            out[:, :, 1] = np.clip(35 + 215 * (norm ** 1.25), 0, 255).astype(np.uint8)
            out[:, :, 2] = np.clip(15 + 165 * (norm ** 1.7), 0, 255).astype(np.uint8)
        return out

    # Chromatic RGB split + damped camera shake
    decay = max(0.25, 1.0 - (step_idx / max(1, total_fx_frames)))
    split_px = int(round(10 * decay))
    shake_amp = 14.0 if color_mode == "climax" else 10.0
    dx = int(round(math.sin(step_idx * 2.4) * shake_amp * decay))
    dy = int(round(math.cos(step_idx * 3.1) * shake_amp * decay))

    out = bgr.copy()
    if split_px > 0:
        b, g, r = cv2.split(bgr)
        r_shift = np.roll(r, split_px, axis=1)
        b_shift = np.roll(b, -split_px, axis=1)
        out = cv2.merge([b_shift, g, r_shift])

    M = np.float32([[1, 0, dx], [0, 1, dy]])
    out = cv2.warpAffine(out, M, (w, h), borderMode=cv2.BORDER_REFLECT_101)
    return out


def render_opening_title_frames(duration_sec: float = 2.8) -> List[np.ndarray]:
    """Render animated 2.8s moonlit crimson opening title with diagonal gold sword wipe."""
    n_frames = int(round(duration_sec * FPS))
    f_main = load_font(FONT_IMPACT, 118)
    f_jp = load_font(FONT_JP_BOLD, 48)
    f_sub = load_font(FONT_DISPLAY, 30)

    # Use shot_01 keyframe blurred dark moodily behind crimson moon glow
    bg_src = Image.open(FRAMES_DIR / "shot_01_canon.webp") if (FRAMES_DIR / "shot_01_canon.webp").is_file() else Image.new("RGB", (WIDTH, HEIGHT), (10, 10, 18))
    bg_base = fit_cover_pil(bg_src, WIDTH, HEIGHT).filter(ImageFilter.GaussianBlur(radius=14))
    bg_base = ImageEnhance.Brightness(bg_base).enhance(0.28)

    frames: List[np.ndarray] = []
    for i in range(n_frames):
        t = i / float(max(1, n_frames - 1))
        canvas = bg_base.copy().convert("RGBA")

        # Crimson full moon bloom rising center-back
        moon_ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        md = ImageDraw.Draw(moon_ov)
        moon_alpha = int(175 * min(1.0, t * 2.2))
        md.ellipse([WIDTH // 2 - 230, HEIGHT // 2 - 260, WIDTH // 2 + 230, HEIGHT // 2 + 200], fill=(165, 24, 42, moon_alpha))
        moon_ov = moon_ov.filter(ImageFilter.GaussianBlur(radius=45))
        canvas = Image.alpha_composite(canvas, moon_ov)

        # Diagonal gold-azure katana slash light wipe across t in [0.12, 0.50]
        if 0.10 <= t <= 0.65:
            slash_prog = min(1.0, max(0.0, (t - 0.10) / 0.30))
            fade = max(0.0, 1.0 - max(0.0, (t - 0.38) / 0.27))
            slash_ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            sd = ImageDraw.Draw(slash_ov)
            x1 = int(200 + (WIDTH - 400) * slash_prog)
            y1 = int(760 - 440 * slash_prog)
            sd.line([(200, 760), (x1, y1)], fill=(90, 215, 255, int(235 * fade)), width=18)
            sd.line([(200, 760), (x1, y1)], fill=(255, 245, 200, int(255 * fade)), width=6)
            slash_ov = slash_ov.filter(ImageFilter.GaussianBlur(radius=3))
            canvas = Image.alpha_composite(canvas, slash_ov)

        # Typography fade-in after slash hits t >= 0.24
        if t >= 0.20:
            alpha = int(255 * min(1.0, (t - 0.20) / 0.22))
            if t > 0.84:
                alpha = int(alpha * max(0.0, (1.0 - t) / 0.16))
            txt_ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            td = ImageDraw.Draw(txt_ov)

            title = "MUSHROOM GAIDEN"
            tb = td.textbbox((0, 0), title, font=f_main)
            tw = tb[2] - tb[0]
            tx = (WIDTH - tw) // 2
            td.text((tx + 5, 345), title, font=f_main, fill=(8, 6, 12, alpha))
            td.text((tx, 340), title, font=f_main, fill=(252, 246, 232, alpha), stroke_width=5, stroke_fill=(14, 10, 18, alpha))

            jp = "キノコ伝 — 龍隼の影"
            jb = td.textbbox((0, 0), jp, font=f_jp)
            jx = (WIDTH - (jb[2] - jb[0])) // 2
            td.text((jx, 495), jp, font=f_jp, fill=(240, 192, 82, alpha), stroke_width=3, stroke_fill=(10, 8, 14, alpha))

            sub = "TOAD AS RYU HAYABUSA   •   TOADETTE AS AYANE"
            sb = td.textbbox((0, 0), sub, font=f_sub)
            sx = (WIDTH - (sb[2] - sb[0])) // 2
            td.text((sx, 575), sub, font=f_sub, fill=(195, 165, 255, alpha), stroke_width=2, stroke_fill=(10, 8, 14, alpha))

            canvas = Image.alpha_composite(canvas, txt_ov)

        rgb = np.array(canvas.convert("RGB"))
        frames.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return frames


def render_ending_card_frames(duration_sec: float = 3.8) -> List[np.ndarray]:
    """Render 3.8s moonlit shinobi ending credits plate with drifting sakura petals."""
    n_frames = int(round(duration_sec * FPS))
    f_hdr = load_font(FONT_IMPACT, 80)
    f_jp = load_font(FONT_JP_BOLD, 38)
    f_role = load_font(FONT_DISPLAY, 30)
    f_small = load_font(FONT_MONO, 22)

    bg_src = Image.open(FRAMES_DIR / "shot_09_canon.webp") if (FRAMES_DIR / "shot_09_canon.webp").is_file() else Image.new("RGB", (WIDTH, HEIGHT), (10, 12, 20))
    bg_base = fit_cover_pil(bg_src, WIDTH, HEIGHT).filter(ImageFilter.GaussianBlur(radius=10))
    bg_base = ImageEnhance.Brightness(bg_base).enhance(0.25)

    rng = np.random.default_rng(1337)
    petals = [(rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT), rng.uniform(3, 8), rng.uniform(0.7, 1.8)) for _ in range(32)]

    frames: List[np.ndarray] = []
    for i in range(n_frames):
        t = i / float(max(1, n_frames - 1))
        alpha_master = min(1.0, t / 0.16)
        if t > 0.78:
            alpha_master *= max(0.0, (1.0 - t) / 0.22)
        a = int(255 * alpha_master)

        canvas = bg_base.copy().convert("RGBA")
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # Drifting sakura petals & golden embers
        for idx, (px0, py0, rad, spd) in enumerate(petals):
            px = (px0 + i * 3.2 * spd) % WIDTH
            py = (py0 + i * 2.1 * spd) % HEIGHT
            col = (240, 145, 225, int(190 * alpha_master)) if idx % 3 != 0 else (255, 205, 95, int(190 * alpha_master))
            d.ellipse([px - rad, py - rad * 0.6, px + rad, py + rad * 0.6], fill=col)

        d.rectangle([80, 70, WIDTH - 80, HEIGHT - 70], outline=(240, 192, 82, int(130 * alpha_master)), width=2)

        def center_text(y: int, text: str, font: ImageFont.FreeTypeFont, color: Tuple[int, int, int]) -> None:
            bb = d.textbbox((0, 0), text, font=font)
            x = (WIDTH - (bb[2] - bb[0])) // 2
            d.text((x, y), text, font=font, fill=(*color, a), stroke_width=3, stroke_fill=(8, 6, 12, a))

        center_text(210, "MUSHROOM GAIDEN", f_hdr, (252, 246, 232))
        center_text(312, "キノコ伝 — DRAGON OF THE SHADOW CAP", f_jp, (240, 192, 82))
        d.line([(540, 390), (1380, 390)], fill=(240, 192, 82, int(180 * alpha_master)), width=2)

        center_text(440, "DRAGON TOAD  —  RYU HAYABUSA", f_role, (125, 220, 255))
        center_text(500, "BLOSSOM TOADETTE  —  AYANE", f_role, (235, 165, 255))
        center_text(560, "LORD KURO-KAME  —  OBSIDIAN DRAGON-SHELL SHOGUN", f_role, (255, 130, 115))

        center_text(690, "PRODUCED WITH GOOGLE FLOW (NANO BANANA 2 + OMNI 1.2 FLASH)  •  142 BPM TAIKO-SHAMISEN SCORE", f_small, (205, 200, 192))
        center_text(740, "MASTERED AT 1920x1080 24FPS  //  -14.0 LUFS", f_small, (160, 156, 150))

        canvas = Image.alpha_composite(canvas, ov)
        rgb = np.array(canvas.convert("RGB"))
        frames.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return frames


def burn_subtitle_frame(bgr: np.ndarray, speaker: str, text: str) -> np.ndarray:
    """Render clean theatrical English cinema subtitle near bottom safe zone."""
    pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    f_spk = load_font(FONT_DISPLAY, 24)
    f_sub = load_font(FONT_DISPLAY, 40)

    # Bottom gradient scrim behind text for guaranteed readability
    for y in range(HEIGHT - 190, HEIGHT):
        alpha = int(145 * ((y - (HEIGHT - 190)) / 190.0))
        d.line([(0, y), (WIDTH, y)], fill=(6, 5, 10, alpha))

    if speaker and speaker != "SFX / Impact":
        sb = d.textbbox((0, 0), speaker.upper(), font=f_spk)
        sx = (WIDTH - (sb[2] - sb[0])) // 2
        spk_color = (235, 165, 255, 255) if "Toadette" in speaker else (255, 135, 120, 255) if "Kuro" in speaker else (120, 220, 255, 255)
        d.text((sx, HEIGHT - 154), speaker.upper(), font=f_spk, fill=spk_color, stroke_width=3, stroke_fill=(8, 6, 12, 245))

    tb = d.textbbox((0, 0), text, font=f_sub)
    tx = (WIDTH - (tb[2] - tb[0])) // 2
    ty = HEIGHT - 114
    d.text((tx + 3, ty + 4), text, font=f_sub, fill=(4, 3, 8, 220))
    d.text((tx, ty), text, font=f_sub, fill=(252, 248, 238, 255), stroke_width=5, stroke_fill=(8, 6, 12, 255))

    merged = Image.alpha_composite(pil, ov).convert("RGB")
    return cv2.cvtColor(np.array(merged), cv2.COLOR_RGB2BGR)


def karplus_strong_pluck(freq: float, dur_sec: float, brightness: float = 0.42) -> np.ndarray:
    """Synthesize a crisp plucked Tsugaru Shamisen string note using Karplus-Strong."""
    n = int(round(dur_sec * SR))
    period = max(2, int(round(SR / freq)))
    rng = np.random.default_rng(int(freq * 100))
    # Bright crisp plectrum excitation noise burst
    buf = (rng.uniform(-1.0, 1.0, period) * 0.85).astype(np.float32)
    out = np.zeros(n, dtype=np.float32)
    decay = 0.994 - 0.002 * (1.0 - brightness)
    idx = 0
    for i in range(n):
        nxt = (idx + 1) % period
        val = buf[idx]
        out[i] = val
        buf[idx] = decay * (brightness * val + (1.0 - brightness) * buf[nxt])
        idx = nxt
    # Add shamisen bachi skin-slap transient
    slap_len = min(n, int(0.012 * SR))
    t_slap = np.arange(slap_len, dtype=np.float32) / SR
    out[:slap_len] += 0.35 * np.exp(-t_slap * 240.0) * rng.uniform(-1.0, 1.0, slap_len)
    return out


def taiko_hit(dur_sec: float = 0.45, f_start: float = 135.0, f_end: float = 42.0, drive: float = 1.8) -> np.ndarray:
    """Synthesize a punchy O-daiko or Shime-daiko drum hit."""
    n = int(round(dur_sec * SR))
    t = np.arange(n, dtype=np.float32) / SR
    freq_env = f_end + (f_start - f_end) * np.exp(-t * 28.0)
    phase = 2.0 * np.pi * np.cumsum(freq_env) / SR
    body = np.sin(phase) * np.exp(-t * 8.5)
    rng = np.random.default_rng(int(f_start * 10))
    stick = rng.uniform(-1.0, 1.0, n) * np.exp(-t * 140.0) * 0.45
    sig = np.tanh((body + stick) * drive)
    return sig.astype(np.float32)


def synthesize_shinobi_score(
    total_sec: float,
    shot_timeline: List[Dict[str, Any]],
    out_wav: Path,
) -> Path:
    """
    Synthesize custom 142 BPM Japanese Shinobi Action Score with vacuum-silence drops,
    crater booms, katana overtone rings, and dialogue ducking windows.
    """
    n_samples = int(round(total_sec * SR))
    left = np.zeros(n_samples, dtype=np.float32)
    right = np.zeros(n_samples, dtype=np.float32)

    def add_mono(start_t: float, mono: np.ndarray, gain: float = 1.0, pan: float = 0.0) -> None:
        i0 = int(round(start_t * SR))
        if i0 >= n_samples or i0 + len(mono) <= 0:
            return
        s0 = max(0, -i0)
        d0 = max(0, i0)
        cnt = min(len(mono) - s0, n_samples - d0)
        if cnt <= 0:
            return
        lg = gain * math.sqrt(max(0.0, (1.0 - pan) * 0.5))
        rg = gain * math.sqrt(max(0.0, (1.0 + pan) * 0.5))
        left[d0:d0 + cnt] += mono[s0:s0 + cnt] * lg
        right[d0:d0 + cnt] += mono[s0:s0 + cnt] * rg

    # 1. Intro Hyoshigi wooden clappers + Temple Gong + Katana Title Wipe (0.0s .. 2.8s)
    for clack_t in (0.12, 0.48, 0.84, 1.24):
        tc = np.arange(int(0.09 * SR), dtype=np.float32) / SR
        clack = (np.sin(2 * np.pi * 2150 * tc) + 0.6 * np.sin(2 * np.pi * 3240 * tc)) * np.exp(-tc * 65.0)
        add_mono(clack_t, clack, gain=0.42, pan=-0.15)

    # Bronze temple gong at 0.60s
    tg = np.arange(int(2.6 * SR), dtype=np.float32) / SR
    gong = (
        0.55 * np.sin(2 * np.pi * 98.0 * tg) * np.exp(-tg * 1.1)
        + 0.35 * np.sin(2 * np.pi * 147.0 * tg) * np.exp(-tg * 1.5)
        + 0.25 * np.sin(2 * np.pi * 241.0 * tg) * np.exp(-tg * 2.4)
    )
    add_mono(0.55, gong, gain=0.55, pan=0.0)

    # Katana slash metallic ring on opening wipe (~0.58s)
    ts = np.arange(int(0.9 * SR), dtype=np.float32) / SR
    slash = (np.sin(2 * np.pi * 2880 * ts) + 0.5 * np.sin(2 * np.pi * 4320 * ts)) * np.exp(-ts * 7.5)
    add_mono(0.56, slash, gain=0.22, pan=0.25)

    # 2. 142 BPM Driving Taiko + Shamisen + Octave Bass (from 2.4s until Finale start)
    bpm = 142.0
    beat = 60.0 / bpm
    step16 = beat / 4.0

    # Find Shot 09 start & Ending start to resolve cleanly into shakuhachi finale
    s06_start = next((s["start_sec"] for s in shot_timeline if s["id"] == "shot_06"), total_sec * 0.55)
    s09_start = next((s["start_sec"] for s in shot_timeline if s["id"] == "shot_09"), total_sec - 9.5)

    odaiko = taiko_hit(0.45, 132.0, 40.0, 2.0)
    shime = taiko_hit(0.22, 270.0, 95.0, 1.5)

    # D Hirajoshi frequencies: D4, E4, F4, A4, Bb4, D5, E5, F5
    riff_notes = [293.66, 293.66, 440.0, 349.23, 329.63, 293.66, 466.16, 440.0,
                  587.33, 440.0, 466.16, 440.0, 349.23, 329.63, 440.0, 293.66]
    pluck_cache: Dict[float, np.ndarray] = {}
    for f in set(riff_notes):
        pluck_cache[f] = karplus_strong_pluck(f, 0.42)

    t_cur = 2.40
    step_idx = 0
    while t_cur < s09_start:
        in_boss = t_cur >= s06_start
        # Drums
        m16 = step_idx % 16
        if m16 in (0, 6, 8, 14):
            add_mono(t_cur, odaiko, gain=0.68 if in_boss else 0.58, pan=0.0)
        if m16 in (4, 12) or (in_boss and m16 in (2, 10)):
            add_mono(t_cur, shime, gain=0.42, pan=-0.12 if (m16 % 4 == 0) else 0.14)

        # Shamisen 8th-note driving riff
        if step_idx % 2 == 0:
            note_f = riff_notes[(step_idx // 2) % len(riff_notes)]
            pan = 0.22 if ((step_idx // 2) % 2 == 0) else -0.22
            add_mono(t_cur, pluck_cache[note_f], gain=0.38 if not in_boss else 0.44, pan=pan)

        # Synth-rock bass on quarter pulses
        if step_idx % 4 == 0:
            bar = (step_idx // 16) % 4
            bf = [73.42, 73.42, 58.27, 65.41][bar]  # D2, D2, Bb1, C2
            if in_boss:
                bf *= 0.75 if bar == 2 else 1.0
            tb = np.arange(int(beat * 0.9 * SR), dtype=np.float32) / SR
            bass = np.tanh(2.2 * (np.sin(2 * np.pi * bf * tb) + 0.4 * np.sin(4 * np.pi * bf * tb))) * np.exp(-tb * 4.5)
            add_mono(t_cur, bass, gain=0.34, pan=0.0)

        t_cur += step16
        step_idx += 1

    # 3. Heroic Finale Shakuhachi-style airy bamboo flute + warm D minor pad (s09_start -> end)
    fin_dur = max(1.0, total_sec - s09_start)
    tf = np.arange(int(fin_dur * SR), dtype=np.float32) / SR
    rng_fl = np.random.default_rng(77)
    breath = rng_fl.uniform(-1.0, 1.0, len(tf)).astype(np.float32) * 0.04
    # Smooth breath noise slightly
    breath = np.convolve(breath, np.ones(16, dtype=np.float32) / 16.0, mode="same")
    flute_env = np.minimum(1.0, tf / 0.8) * np.maximum(0.0, 1.0 - np.maximum(0.0, tf - (fin_dur - 1.4)) / 1.4)
    flute = (np.sin(2 * np.pi * 587.33 * tf + 0.3 * np.sin(2 * np.pi * 4.5 * tf)) * 0.28 + breath) * flute_env
    pad = (0.22 * np.sin(2 * np.pi * 146.83 * tf) + 0.16 * np.sin(2 * np.pi * 220.0 * tf) + 0.14 * np.sin(2 * np.pi * 349.23 * tf)) * flute_env
    add_mono(s09_start, flute + pad, gain=0.55, pan=0.0)
    add_mono(s09_start, gong, gain=0.45, pan=0.0)

    # 4. Apply Vacuum-Silence Drops & Impact Booms + Katana Rings
    env = np.ones(n_samples, dtype=np.float32)
    for s in shot_timeline:
        vac = float(s.get("vacuum_cut_sec", 0.0) or 0.0)
        imp_t = s.get("impact_sec")
        if vac > 0.0 and imp_t is not None:
            i_end = int(round(imp_t * SR))
            i_start = max(0, int(round((imp_t - vac) * SR)))
            env[i_start:i_end] = 0.04

        # Duck score -10 dB (0.32x) during spoken subtitles
        for sub in s.get("subtitles", []):
            if sub.get("speaker") == "SFX / Impact":
                continue
            d0 = max(0, int(round((s["start_sec"] + float(sub["start_rel"]) - 0.1) * SR)))
            d1 = min(n_samples, int(round((s["start_sec"] + float(sub["end_rel"]) + 0.15) * SR)))
            env[d0:d1] = np.minimum(env[d0:d1], 0.34)

    left *= env
    right *= env

    # Add impacts AFTER vacuum-silence envelope so booms explode cleanly out of silence
    for s in shot_timeline:
        imp_t = s.get("impact_sec")
        if imp_t is not None and s.get("hit_stop_frames", 0) > 0:
            strength = 0.95 if s.get("hit_stop_color") == "climax" else 0.72
            tb = np.arange(int(0.85 * SR), dtype=np.float32) / SR
            f_drop = 28.0 + 95.0 * np.exp(-tb * 24.0)
            boom = np.tanh(2.4 * np.sin(2 * np.pi * np.cumsum(f_drop) / SR)) * np.exp(-tb * 4.5)
            ring = (np.sin(2 * np.pi * 2850 * tb) + 0.55 * np.sin(2 * np.pi * 4320 * tb)) * np.exp(-tb * 9.0) * 0.25
            add_mono(imp_t, boom + ring, gain=strength, pan=0.0)

    # Gentle stereo limiter
    stereo = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(stereo))) if len(stereo) else 1.0
    if peak > 0.92:
        stereo *= 0.92 / peak

    pcm = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return out_wav


async def generate_edge_tts_for_shot(shot: Dict[str, Any], tmp_dir: Path) -> List[Tuple[float, Path]]:
    """Generate backup Japanese voice stems for a single shot when native audio is weak."""
    voice_map = {
        "Toad (Ryu)": ("ja-JP-KeitaNeural", "+8%", "+4Hz"),
        "Toadette (Ayane)": ("ja-JP-NanamiNeural", "+10%", "+14Hz"),
        "Lord Kuro-Kame": ("ja-JP-KeitaNeural", "-10%", "-20Hz"),
        "Toad & Toadette": ("ja-JP-KeitaNeural", "+12%", "+6Hz"),
    }
    jp = shot.get("dialogue_jp")
    if not jp:
        return []
    lines = [part.strip() for part in jp.split("/") if part.strip()]
    subs = [s for s in shot.get("subtitles", []) if s.get("speaker") != "SFX / Impact"]
    shot_lines: List[Tuple[float, Path]] = []
    for idx, text_jp in enumerate(lines):
        spk = subs[idx]["speaker"] if idx < len(subs) else "Toad (Ryu)"
        start_rel = float(subs[idx]["start_rel"]) if idx < len(subs) else 0.35
        voice, rate, pitch = voice_map.get(spk, ("ja-JP-KeitaNeural", "+5%", "+0Hz"))
        mp3_p = tmp_dir / f"{shot['id']}_jp_{idx}.mp3"
        wav_p = tmp_dir / f"{shot['id']}_jp_{idx}.wav"
        comm = edge_tts.Communicate(text_jp, voice=voice, rate=rate, pitch=pitch)
        await comm.save(str(mp3_p))
        run_cmd(
            ["ffmpeg", "-y", "-v", "error", "-i", str(mp3_p), "-ar", str(SR), "-ac", "2", str(wav_p)],
            f"decode tts {wav_p.name}",
        )
        shot_lines.append((start_rel, wav_p))
    return shot_lines


def build_storyboard_sheet(manifest: Dict[str, Any], out_path: Path) -> None:
    """Assemble a crisp 3x3 labeled storyboard contact sheet of all 9 canonical keyframes."""
    cell_w, cell_h = 760, 428
    pad_x, pad_y, hdr_h = 28, 28, 110
    W = pad_x * 4 + cell_w * 3
    H = hdr_h + pad_y * 4 + cell_h * 3
    canvas = Image.new("RGB", (W, H), (11, 9, 16))
    d = ImageDraw.Draw(canvas)

    f_title = load_font(FONT_IMPACT, 48)
    f_sub = load_font(FONT_JP_BOLD, 24)
    f_cell = load_font(FONT_DISPLAY, 22)
    f_cap = load_font(FONT_JP_BOLD, 18)

    d.text((pad_x, 22), "MUSHROOM GAIDEN: DRAGON OF THE SHADOW CAP  //  STORYBOARD", font=f_title, fill=(252, 246, 232))
    jp_hdr = "キノコ伝 — TOAD & TOADETTE SHINOBI"
    jb = d.textbbox((0, 0), jp_hdr, font=f_sub)
    d.text((W - pad_x - (jb[2] - jb[0]), 34), jp_hdr, font=f_sub, fill=(240, 192, 82))
    d.line([(pad_x, 90), (W - pad_x, 90)], fill=(240, 192, 82), width=2)

    for idx, shot in enumerate(manifest["shots"][:9]):
        row, col = divmod(idx, 3)
        x0 = pad_x + col * (cell_w + pad_x)
        y0 = hdr_h + pad_y + row * (cell_h + pad_y)
        kf_path = PROJECT_ROOT / shot["keyframe"]
        img = fit_cover_pil(Image.open(kf_path), cell_w, cell_h)
        canvas.paste(img, (x0, y0))
        d.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], outline=(240, 192, 82), width=2)
        d.rectangle([x0, y0 + cell_h - 62, x0 + cell_w, y0 + cell_h], fill=(10, 8, 16))
        d.text((x0 + 12, y0 + cell_h - 56), f"{shot['id'].upper()}  •  {shot['title']} ({shot['shot_size']})", font=f_cell, fill=(252, 246, 232))
        cap = shot.get("dialogue_jp") or "[ACTION / SAKUGA BEAT]"
        d.text((x0 + 12, y0 + cell_h - 28), cap[:66], font=f_cap, fill=(175, 220, 255))

    canvas.save(str(out_path), format="PNG", optimize=True)


def build_thumbnail(out_path: Path) -> None:
    """Create 1280x720 high-CTR theatrical poster thumbnail from the climax frame."""
    PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    src = FRAMES_DIR / "shot_08_canon.webp"
    if not src.is_file():
        src = FRAMES_DIR / "shot_01_canon.webp"

    base = fit_cover_pil(Image.open(src), 1280, 720)
    base = ImageEnhance.Contrast(base).enhance(1.16)
    base = ImageEnhance.Color(base).enhance(1.14)
    canvas = base.convert("RGBA")

    grad = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(420, 720):
        a = int(205 * (((y - 420) / 300.0) ** 1.35))
        gd.line([(0, y), (1280, y)], fill=(8, 6, 12, a))
    # Smooth corner shadow behind lower-left headline with zero vertical seam
    corner = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    cd = ImageDraw.Draw(corner)
    cd.ellipse([-180, 340, 640, 860], fill=(8, 6, 12, 175))
    corner = corner.filter(ImageFilter.GaussianBlur(radius=65))
    canvas = Image.alpha_composite(canvas, grad)
    canvas = Image.alpha_composite(canvas, corner)

    d = ImageDraw.Draw(canvas)
    f_big = load_font(FONT_IMPACT, 118)
    f_jp = load_font(FONT_JP_BOLD, 34)
    f_badge = load_font(FONT_DISPLAY, 24)

    d.rectangle([12, 12, 1267, 707], outline=(240, 192, 82, 180), width=3)
    d.text((38, 30), "キノコ伝 // MUSHROOM GAIDEN", font=f_jp, fill=(240, 192, 82, 255), stroke_width=4, stroke_fill=(8, 6, 12, 255))

    # Top-right character cast badge (auto-sized padding)
    badge_txt = "TOAD × RYU  •  TOADETTE × AYANE"
    bb = d.textbbox((0, 0), badge_txt, font=f_badge)
    bw = (bb[2] - bb[0]) + 36
    bx1 = 1244
    bx0 = bx1 - bw
    d.rectangle([bx0, 28, bx1, 80], fill=(12, 8, 18, 225), outline=(205, 110, 255, 240), width=2)
    d.text((bx0 + 18, 41), badge_txt, font=f_badge, fill=(252, 246, 232, 255))

    # Bold lower-left 2-word punch headline
    d.text((44, 434), "DRAGON", font=f_big, fill=(252, 248, 238, 255), stroke_width=8, stroke_fill=(8, 6, 12, 255))
    d.text((44, 548), "SHINOBI.", font=f_big, fill=(240, 192, 82, 255), stroke_width=8, stroke_fill=(8, 6, 12, 255))

    canvas.convert("RGB").save(str(out_path), format="PNG", optimize=True)


def write_raw_video(path: Path, frames: List[np.ndarray]) -> None:
    """Pipe BGR24 frames into lossless-ish H.264 intermediate via FFmpeg."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "15",
        "-pix_fmt", "yuv420p", str(path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for fr in frames:
        proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg video encode failed for {path} (code {rc})")


def two_pass_loudnorm_mux(video_path: Path, wav_path: Path, final_out: Path) -> None:
    """Mux video and audio with two-pass EBU R128 normalization (-14.0 LUFS, -1.0 dBTP)."""
    p1 = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(wav_path),
            "-af", f"loudnorm=I={TARGET_LUFS:.1f}:TP={TARGET_TP:.1f}:LRA=11:print_format=json",
            "-f", "null", os.devnull,
        ],
        capture_output=True, text=True, check=False,
    )
    m = re.search(r'\{\s*"input_i"\s*:.*?\}', p1.stderr, flags=re.DOTALL)
    if m:
        stats = json.loads(m.group(0))
        af = (
            f"loudnorm=I={TARGET_LUFS:.1f}:TP={TARGET_TP:.1f}:LRA=11:"
            f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}:linear=true:print_format=summary"
        )
    else:
        af = f"loudnorm=I={TARGET_LUFS:.1f}:TP={TARGET_TP:.1f}:LRA=11"

    run_cmd(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(video_path), "-i", str(wav_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-af", f"{af},alimiter=limit=0.88:level=false",
            "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2",
            "-movflags", "+faststart", "-shortest", str(final_out),
        ],
        f"mux {final_out.name}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble Mushroom Gaiden action short masters & publish assets.")
    parser.add_argument("--reinforce-tts", action="store_true", help="Always layer edge-tts JP dialogue over native audio.")
    args = parser.parse_args()

    manifest = json.loads(SHOTS_PATH.read_text(encoding="utf-8"))
    MASTERS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Storyboard & Thumbnail
    build_storyboard_sheet(manifest, PROJECT_ROOT / "storyboard_sheet.png")
    build_thumbnail(PUBLISH_DIR / "MUSHROOM_GAIDEN_THUMBNAIL.png")
    print("Generated storyboard_sheet.png and publish/MUSHROOM_GAIDEN_THUMBNAIL.png")

    with tempfile.TemporaryDirectory(prefix="mg_build_") as tmp_str:
        tmp_dir = Path(tmp_str)

        # 2. Render Opening Title
        title_frames = render_opening_title_frames(duration_sec=2.8)
        clean_frames: List[np.ndarray] = list(title_frames)
        sub_frames: List[np.ndarray] = list(title_frames)
        cur_sec = len(title_frames) / float(FPS)

        shot_timeline: List[Dict[str, Any]] = []
        audio_tracks: List[Tuple[float, Path, float]] = []  # (start_sec, wav_path, gain)

        # 3. Process all 9 shots
        for shot in manifest["shots"]:
            sid = shot["id"]
            mp4_path = VIDEOS_DIR / f"{sid}.mp4"
            if not mp4_path.is_file():
                raise FileNotFoundError(f"Missing generated video clip: {mp4_path}")

            cap = cv2.VideoCapture(str(mp4_path))
            raw_frames: List[np.ndarray] = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                raw_frames.append(grade_cinema_frame(frame))
            cap.release()
            if not raw_frames:
                raise RuntimeError(f"Zero frames decoded from {mp4_path}")

            speed = float(shot.get("playback_speed", 1.0))
            if shot.get("dialogue_jp"):
                # Keep dialogue lines locked near 1.0x unless explicitly marked fast action
                if sid in ("shot_02", "shot_06", "shot_09"):
                    speed = 1.0

            # Sample frames according to playback speed
            sampled_idx = []
            acc = 0.0
            while int(round(acc)) < len(raw_frames):
                sampled_idx.append(int(round(acc)))
                acc += speed
            shot_clean = [raw_frames[idx] for idx in sampled_idx]

            # Inject Impact Hit-Stop if specified
            hs_frames = int(shot.get("hit_stop_frames", 0) or 0)
            impact_abs_sec: Optional[float] = None
            if hs_frames > 0 and len(shot_clean) > 8:
                hs_rel = float(shot.get("hit_stop_rel", 0.62))
                hs_idx = max(4, min(len(shot_clean) - 4, int(round(len(shot_clean) * hs_rel))))
                impact_abs_sec = cur_sec + (hs_idx / float(FPS))
                anchor = shot_clean[hs_idx]
                fx_seq = [
                    apply_hit_stop_fx(anchor, k, hs_frames, shot.get("hit_stop_color", "azure"))
                    for k in range(hs_frames)
                ]
                shot_clean = shot_clean[:hs_idx] + fx_seq + shot_clean[hs_idx:]

            shot_dur = len(shot_clean) / float(FPS)

            # Build subtitled twin frames
            subs = shot.get("subtitles", [])
            shot_sub = []
            for fi, fr in enumerate(shot_clean):
                rel_t = fi / float(FPS)
                active_sub = next((sb for sb in subs if float(sb["start_rel"]) <= rel_t <= float(sb["end_rel"])), None)
                if active_sub:
                    shot_sub.append(burn_subtitle_frame(fr, active_sub.get("speaker", ""), active_sub["text"]))
                else:
                    shot_sub.append(fr)

            # Smooth 10-frame cross-dissolve into the Victory Finale (shot_09)
            if sid == "shot_09" and len(clean_frames) >= 10 and len(shot_clean) >= 10:
                for k in range(10):
                    a = (k + 1) / 11.0
                    clean_frames[-10 + k] = cv2.addWeighted(clean_frames[-10 + k], 1.0 - a, shot_clean[k], a, 0)
                    sub_frames[-10 + k] = cv2.addWeighted(sub_frames[-10 + k], 1.0 - a, shot_sub[k], a, 0)
                clean_frames.extend(shot_clean[10:])
                sub_frames.extend(shot_sub[10:])
                start_this = cur_sec - (10.0 / float(FPS))
                cur_sec = len(clean_frames) / float(FPS)
            else:
                start_this = cur_sec
                clean_frames.extend(shot_clean)
                sub_frames.extend(shot_sub)
                cur_sec = len(clean_frames) / float(FPS)

            # Extract & time-match native clip audio
            native_wav = tmp_dir / f"{sid}_native.wav"
            atempo_filter = f"atempo={speed:.3f}," if abs(speed - 1.0) > 0.01 else ""
            run_cmd(
                [
                    "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path),
                    "-af", f"{atempo_filter}aresample={SR}", "-ac", "2", "-t", f"{shot_dur:.3f}",
                    str(native_wav),
                ],
                f"extract audio {sid}",
            )
            mean_db = detect_audio_mean_db(native_wav)
            audio_tracks.append((start_this, native_wav, 0.92))

            # Reinforce with edge-tts JP dialogue ONLY if native audio is quiet (<-34 dB) or --reinforce-tts
            if shot.get("dialogue_jp") and (args.reinforce_tts or mean_db < -34.0):
                print(f"[{sid}] Native audio mean={mean_db:.1f} dB -> layering edge-tts JP dialogue")
                for rel_start, tts_wav in asyncio.run(generate_edge_tts_for_shot(shot, tmp_dir)):
                    audio_tracks.append((start_this + rel_start, tts_wav, 1.05))
            else:
                print(f"[{sid}] Native audio mean={mean_db:.1f} dB -> preserving native Flow audio")

            shot_timeline.append({
                "id": sid,
                "start_sec": start_this,
                "duration_sec": shot_dur,
                "hit_stop_frames": hs_frames,
                "hit_stop_color": shot.get("hit_stop_color"),
                "vacuum_cut_sec": float(shot.get("vacuum_cut_sec", 0.0) or 0.0),
                "impact_sec": impact_abs_sec,
                "subtitles": subs,
            })

        # 4. Append Ending Card
        end_frames = render_ending_card_frames(duration_sec=3.8)
        clean_frames.extend(end_frames)
        sub_frames.extend(end_frames)
        total_sec = len(clean_frames) / float(FPS)

        # 5. Synthesize Custom Score & Mix Full Master Audio
        score_wav = AUDIO_DIR / "mushroom_gaiden_score.wav"
        synthesize_shinobi_score(total_sec, shot_timeline, score_wav)

        # Mix score + all shot native/TTS tracks in NumPy to avoid complex FFmpeg filter graph limits
        def read_wav_f32(p: Path) -> np.ndarray:
            with wave.open(str(p), "rb") as wf:
                raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32767.0
                ch = wf.getnchannels()
                if ch == 1:
                    raw = np.repeat(raw[:, None], 2, axis=1)
                else:
                    raw = raw.reshape(-1, ch)[:, :2]
                return raw

        mix = read_wav_f32(score_wav) * 0.85
        n_tot = len(mix)
        for st_sec, trk_path, gain in audio_tracks:
            arr = read_wav_f32(trk_path)
            i0 = max(0, int(round(st_sec * SR)))
            cnt = min(len(arr), n_tot - i0)
            if cnt > 0:
                # 25ms fade-in/out on clip native audio to prevent clicks
                fade = min(cnt // 2, int(0.025 * SR))
                seg = arr[:cnt].copy()
                if fade > 0:
                    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)[:, None]
                    seg[:fade] *= ramp
                    seg[-fade:] *= ramp[::-1]
                mix[i0:i0 + cnt] += seg * gain

        # Prevent pre-loudnorm clipping
        pk = float(np.max(np.abs(mix))) if len(mix) else 1.0
        if pk > 0.94:
            mix *= 0.94 / pk
        mix_wav = tmp_dir / "master_mix_pre_norm.wav"
        with wave.open(str(mix_wav), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(np.clip(mix * 32767.0, -32767, 32767).astype(np.int16).tobytes())

        # 6. Encode & Master Both Deliverables
        raw_clean = tmp_dir / "video_clean.mp4"
        raw_sub = tmp_dir / "video_sub.mp4"
        write_raw_video(raw_clean, clean_frames)
        write_raw_video(raw_sub, sub_frames)

        out_clean = MASTERS_DIR / "MUSHROOM_GAIDEN_ACTION_SHORT_CLEAN.mp4"
        out_sub = MASTERS_DIR / "MUSHROOM_GAIDEN_ACTION_SHORT_JP_SUB.mp4"
        two_pass_loudnorm_mux(raw_clean, mix_wav, out_clean)
        two_pass_loudnorm_mux(raw_sub, mix_wav, out_sub)

        report = {
            "total_duration_sec": round(total_sec, 3),
            "clean_master": probe_media(out_clean),
            "subbed_master": probe_media(out_sub),
        }
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
