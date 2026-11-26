#!/usr/bin/env python3
"""
Build-DeadChannel13PublishSuite.py

Generates publishable YouTube masters (with animated 90s cel Ending Credits
layered with `yyh01-sunset-credits-suite.mp3`), high-CTR 1280x720 thumbnails,
and zero-black-bar 1080x1920 9:16 vertical Shorts teasers for DEAD CHANNEL 13.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MASTERS_DIR = PROJECT_ROOT / "masters"
PUBLISH_DIR = PROJECT_ROOT / "publish"
THUMBS_DIR = PUBLISH_DIR / "thumbnails"
SHORTS_DIR = PUBLISH_DIR / "shorts"

DEFAULT_CREDITS_AUDIO = Path(r"G:\My Drive\Antigravity\Projects\Google Flow-music\exports\hits\yyh01-sunset-credits-suite.mp3")
DEFAULT_SHORTS_MUSIC = Path(r"G:\My Drive\Antigravity\Projects\Google Flow-music\exports\hits\rom01-palace-shorts-hook.mp3")

FONT_JP_BOLD = r"C:\Windows\Fonts\YuGothB.ttc"
FONT_JP_MED = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_DISPLAY = r"C:\Windows\Fonts\bahnschrift.ttf"
FONT_IMPACT = r"C:\Windows\Fonts\impact.ttf"
FONT_MONO = r"C:\Windows\Fonts\consolab.ttf"

TARGET_LUFS = -14.0


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    if Path(path).is_file():
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def run_ffmpeg(cmd: List[str], desc: str) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed ({desc}):\n{proc.stderr}")


def probe_media(path: Path) -> Dict[str, Any]:
    pr = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    j = json.loads(pr.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    ln = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", f"loudnorm=I={TARGET_LUFS:.1f}:TP=-1.0:LRA=11:print_format=json", "-f", "null", os.devnull],
        capture_output=True,
        text=True,
        check=False,
    )
    m = re.search(r'\{\s*"input_i"\s*:.*?\}', ln.stderr, flags=re.DOTALL)
    ld = json.loads(m.group(0)) if m else {}
    return {
        "path": str(path),
        "duration_sec": round(float(j["format"]["duration"]), 3),
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": v.get("r_frame_rate", ""),
        "sample_rate": int(a.get("sample_rate", 0)) if a else 0,
        "channels": int(a.get("channels", 0)) if a else 0,
        "integrated_lufs": round(float(ld["input_i"]), 2) if "input_i" in ld else None,
        "true_peak_db": round(float(ld["input_tp"]), 2) if "input_tp" in ld else None,
        "bytes": path.stat().st_size,
    }


def measure_gain_db(wav_or_mp4: Path, target_lufs: float = TARGET_LUFS) -> float:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav_or_mp4), "-af", f"loudnorm=I={target_lufs:.1f}:TP=-1.0:LRA=11:print_format=json", "-f", "null", os.devnull],
        capture_output=True,
        text=True,
        check=False,
    )
    m = re.search(r'\{\s*"input_i"\s*:.*?\}', proc.stderr, flags=re.DOTALL)
    if not m:
        return 0.0
    in_i = float(json.loads(m.group(0))["input_i"])
    return max(-18.0, min(18.0, round(target_lufs - in_i, 3)))


def fit_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src = img.convert("RGB")
    sw, sh = src.size
    scale = max(target_w / float(sw), target_h / float(sh))
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    x0 = (nw - target_w) // 2
    y0 = (nh - target_h) // 2
    return resized.crop((x0, y0, x0 + target_w, y0 + target_h))


def add_crt_scanlines(rgba: Image.Image, alpha: int = 20, step: int = 4) -> Image.Image:
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = rgba.size
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(8, 6, 12, alpha), width=1)
    return Image.alpha_composite(rgba, overlay)


def draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    outline: Tuple[int, int, int, int] = (8, 6, 11, 255),
    stroke_w: int = 5,
    shadow_offset: Tuple[int, int] = (4, 5),
) -> None:
    x, y = xy
    if shadow_offset != (0, 0):
        draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=(4, 3, 8, 200))
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=outline)


def build_thumbnails() -> Dict[str, str]:
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    thumb_specs = [
        {
            "out": THUMBS_DIR / "EP01_THUMBNAIL_13001.png",
            "src": PROJECT_ROOT / "frames_ep1" / "ep1_kf17_time_tear_counter.webp",
            "top_line": "TIME",
            "bot_line": "BROKE.",
            "bot_color": (227, 184, 87, 255),
            "badge": "13.001",
            "sub_badge": "CH-13 // BREACH",
            "accent": (56, 189, 248, 255),
        },
        {
            "out": THUMBS_DIR / "EP02_THUMBNAIL_Y2K_PURGE.png",
            "src": PROJECT_ROOT / "frames_ep2" / "ep2_kf8_cobalt_ricochet.webp",
            "top_line": "6 DAYS",
            "bot_line": "LEFT.",
            "bot_color": (239, 68, 68, 255),
            "badge": "99.12.25",
            "sub_badge": "PURGE PROTOCOL",
            "accent": (239, 68, 68, 255),
        },
    ]

    results: Dict[str, str] = {}
    f_big = load_font(FONT_IMPACT, 128)
    f_badge = load_font(FONT_MONO, 58)
    f_sub = load_font(FONT_DISPLAY, 24)
    f_brand = load_font(FONT_JP_BOLD, 24)

    for sp in thumb_specs:
        if not sp["src"].is_file():
            raise FileNotFoundError(f"Thumbnail keyframe missing: {sp['src']}")
        base = fit_cover(Image.open(sp["src"]), 1280, 720)
        base = ImageEnhance.Contrast(base).enhance(1.14)
        base = ImageEnhance.Color(base).enhance(1.10)
        canvas = base.convert("RGBA")

        # Left-bottom cinema vignette so bold type reads cleanly on mobile feeds
        grad = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for x in range(720):
            a = int(195 * ((720 - x) / 720.0) ** 1.65)
            gd.line([(x, 0), (x, 720)], fill=(8, 6, 11, a))
        for y in range(440, 720):
            a = int(165 * ((y - 440) / 280.0))
            gd.line([(0, y), (1280, y)], fill=(8, 6, 11, a))
        canvas = Image.alpha_composite(canvas, grad)
        canvas = add_crt_scanlines(canvas, alpha=16, step=4)

        draw = ImageDraw.Draw(canvas)
        # Subtle editorial frame rule
        draw.rectangle([14, 14, 1265, 705], outline=(227, 184, 87, 140), width=2)

        # Top-left clean JP series stamp
        draw_outlined_text(draw, (44, 38), "DEAD CHANNEL 13 // デッドチャンネル13", f_brand, (227, 184, 87, 235), stroke_w=3, shadow_offset=(2, 2))

        # Top-right Nixie/countdown callout box
        box_w, box_h = 310, 118
        bx0, by0 = 1280 - 44 - box_w, 38
        draw.rectangle([bx0, by0, bx0 + box_w, by0 + box_h], fill=(12, 8, 16, 225), outline=sp["accent"], width=3)
        draw.text((bx0 + 18, by0 + 12), sp["sub_badge"], font=f_sub, fill=(210, 202, 192, 240))
        draw_outlined_text(draw, (bx0 + 18, by0 + 44), sp["badge"], f_badge, sp["bot_color"], stroke_w=3, shadow_offset=(0, 0))

        # Lower-left 2-word punch headline (never repeats title!)
        draw_outlined_text(draw, (44, 412), sp["top_line"], f_big, (251, 246, 236, 255), stroke_w=8, shadow_offset=(6, 7))
        draw_outlined_text(draw, (44, 536), sp["bot_line"], f_big, sp["bot_color"], stroke_w=8, shadow_offset=(6, 7))

        out_path: Path = sp["out"]
        canvas.convert("RGB").save(str(out_path), format="PNG", optimize=True)
        results[out_path.name] = str(out_path)

    return results


def create_credits_plates(
    tmp_dir: Path,
    ep_num: int,
    ep_title_en: str,
    ep_title_jp: str,
    next_ep_label: str,
    next_ep_sub: str,
    next_ep_preview_img: Path,
) -> Tuple[Path, Path, Path, Path, int]:
    """Generate bg_plate.png, credits_strip.png, mask.png, and next_card.png in tmp_dir."""
    W, H = 1920, 1080
    # 1. Sunset-noir backdrop plate with brass inset window [940, 220, 1830, 720]
    bg = Image.new("RGBA", (W, H), (11, 7, 15, 255))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / float(H)
        r = int(12 + 44 * (t ** 1.4) + 28 * max(0.0, 1.0 - abs(t - 0.68) * 3.0))
        g = int(7 + 16 * (t ** 1.3) + 12 * max(0.0, 1.0 - abs(t - 0.68) * 3.0))
        b = int(18 + 20 * (1.0 - abs(t - 0.35)))
        bd.line([(0, y), (W, y)], fill=(min(255, r), min(255, g), min(255, b), 255))
    bg = add_crt_scanlines(bg, alpha=22, step=4)
    bd = ImageDraw.Draw(bg)
    # Gallery inset chrome frame
    bd.rectangle([936, 216, 1834, 724], fill=(8, 6, 11, 255), outline=(227, 184, 87, 230), width=3)
    bd.line([(90, 128), (1830, 128)], fill=(227, 184, 87, 110), width=2)
    f_hdr = load_font(FONT_MONO, 24)
    f_hdr_jp = load_font(FONT_JP_BOLD, 28)
    bd.text((90, 74), f"DEAD CHANNEL 13 // EP {ep_num:02d} ENDING CREDITS", font=f_hdr, fill=(227, 184, 87, 240))
    bd.text((1350, 70), "デッドチャンネル13", font=f_hdr_jp, fill=(251, 246, 236, 220))
    bd.text((940, 744), f"ARCHIVE KEYFRAME FEED // {ep_title_en}", font=load_font(FONT_MONO, 20), fill=(199, 190, 176, 210))

    bg_path = tmp_dir / f"ep{ep_num}_credits_bg.png"
    bg.convert("RGB").save(str(bg_path), format="PNG")

    # 2. Vertical edge fade mask over credits viewport (x=60..900, y=132..900 transparent)
    mask = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mask)
    for y in range(132, 220):
        a = int(255 * (220 - y) / 88.0)
        md.line([(60, y), (900, y)], fill=(14, 8, 18, a))
    for y in range(900, 1080):
        a = int(255 * min(1.0, (y - 900) / 110.0))
        md.line([(60, y), (900, y)], fill=(18, 9, 16, a))
    md.rectangle([60, 0, 900, 131], fill=(13, 8, 17, 255))
    md.line([(90, 128), (900, 128)], fill=(227, 184, 87, 110), width=2)
    md.text((90, 74), f"DEAD CHANNEL 13 // EP {ep_num:02d} ENDING CREDITS", font=f_hdr, fill=(227, 184, 87, 240))
    mask_path = tmp_dir / f"ep{ep_num}_mask.png"
    mask.save(str(mask_path), format="PNG")

    # 3. Scrolling bilingual credits strip (width=780)
    lines: List[Tuple[str, str, Tuple[int, int, int, int], str]] = [
        ("head_jp", "デッドチャンネル 13", (227, 184, 87, 255), ""),
        ("head_en", f"EPISODE {ep_num:02d} // {ep_title_en}", (251, 246, 236, 255), ""),
        ("sub_jp", ep_title_jp, (199, 190, 176, 255), ""),
        ("spacer", "", (0, 0, 0, 0), ""),
        ("sec", "声の出演 / VOICE CAST", (56, 189, 248, 255), ""),
        ("role", "黒瀬 拓真  TOMA KUROSE", (251, 246, 236, 255), "Phase-Tape Tuner (13.001s)"),
        ("role", "高梨 連司  RENJI TAKANASHI", (251, 246, 236, 255), "Ghost Number Seven (#07)"),
        ("role", "早川 ソラ  SORA HAYAKAWA", (251, 246, 236, 255), "Bureau Defector Telemetry"),
        ("role", "黒羽       KUROHA (VESPER)", (251, 246, 236, 255), "Obsidian Dead-Fire"),
        ("role", "黒沢 真人  MASATO KUROSAWA", (251, 246, 236, 255), "Division 1 Zero Beat"),
        ("role", "黒瀬 祐希  YUKI KUROSE", (251, 246, 236, 255), "Shibuya Broadcast Core"),
        ("spacer", "", (0, 0, 0, 0), ""),
        ("sec", "エンディングテーマ / ENDING THEME", (227, 184, 87, 255), ""),
        ("role", "YYH01 SUNSET CREDITS SUITE", (251, 246, 236, 255), "124 BPM Connected 4-Stem Mix"),
        ("role", "GOOGLE FLOW MUSIC HUB", (199, 190, 176, 255), "Mastered -14.5 LUFS Audio Score"),
        ("spacer", "", (0, 0, 0, 0), ""),
        ("sec", "制作・アニメーション / PRODUCTION", (56, 189, 248, 255), ""),
        ("role", "1990s HAND-INKED CEL STANDARD", (251, 246, 236, 255), "Zero 3D CGI / 35mm Film Grain"),
        ("role", "GOOGLE FLOW + INVIDEO + HIGGSFIELD", (251, 246, 236, 255), "Hybrid Episode & Sakuga Pipeline"),
        ("role", "EXECUTIVE PRODUCER", (227, 184, 87, 255), "Chase (@chaseham00)"),
    ]

    f_hjp = load_font(FONT_JP_BOLD, 48)
    f_hen = load_font(FONT_DISPLAY, 36)
    f_subjp = load_font(FONT_JP_MED, 26)
    f_sec = load_font(FONT_JP_BOLD, 28)
    f_rjp = load_font(FONT_JP_BOLD, 27)
    f_subr = load_font(FONT_DISPLAY, 23)

    strip_h = 2280
    strip = Image.new("RGBA", (780, strip_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    cy = 40
    for kind, text, color, sub in lines:
        if kind == "spacer":
            cy += 44
        elif kind == "head_jp":
            sd.text((0, cy), text, font=f_hjp, fill=color)
            cy += 64
        elif kind == "head_en":
            sd.text((0, cy), text, font=f_hen, fill=color)
            cy += 48
        elif kind == "sub_jp":
            sd.text((0, cy), text, font=f_subjp, fill=color)
            cy += 44
        elif kind == "sec":
            sd.text((0, cy), text, font=f_sec, fill=color)
            sd.line([(0, cy + 40), (620, cy + 40)], fill=color, width=2)
            cy += 62
        elif kind == "role":
            sd.text((0, cy), text, font=f_rjp, fill=color)
            cy += 38
            if sub:
                sd.text((22, cy), sub, font=f_subr, fill=(199, 190, 176, 230))
                cy += 38
            cy += 18

    strip_h_used = cy + 60
    strip = strip.crop((0, 0, 780, strip_h_used))
    strip_path = tmp_dir / f"ep{ep_num}_credits_strip.png"
    strip.save(str(strip_path), format="PNG")

    # 4. Next Episode End-Screen Card (1920x1080) with YouTube End-Screen safe layout
    nc = Image.new("RGBA", (W, H), (9, 6, 13, 255))
    if next_ep_preview_img.is_file():
        bg_next = fit_cover(Image.open(next_ep_preview_img), W, H).filter(ImageFilter.GaussianBlur(radius=14))
        bg_next = ImageEnhance.Brightness(bg_next).enhance(0.28)
        nc = bg_next.convert("RGBA")
    nc = add_crt_scanlines(nc, alpha=24, step=4)
    nd = ImageDraw.Draw(nc)
    nd.rectangle([36, 36, W - 36, H - 36], outline=(227, 184, 87, 150), width=2)

    # Left editorial hook column
    nd.text((100, 140), "STAY ON CHANNEL 13", font=load_font(FONT_MONO, 30), fill=(56, 189, 248, 255))
    draw_outlined_text(nd, (96, 195), "NEXT EPISODE:", font=load_font(FONT_IMPACT, 66), fill=(227, 184, 87, 255), stroke_w=5)
    draw_outlined_text(nd, (96, 285), next_ep_label, font=load_font(FONT_DISPLAY, 54), fill=(251, 246, 236, 255), stroke_w=4)
    nd.text((100, 365), next_ep_sub, font=load_font(FONT_JP_MED, 30), fill=(208, 200, 190, 240))

    # Reserved YouTube End-Screen Card Frame right side [1040, 250, 1780, 666] (16:9 740x416 video card dock)
    nd.rectangle([1036, 246, 1784, 670], fill=(12, 8, 16, 230), outline=(227, 184, 87, 240), width=4)
    if next_ep_preview_img.is_file():
        inset = fit_cover(Image.open(next_ep_preview_img), 740, 416)
        nc.paste(inset, (1040, 250))
        nd = ImageDraw.Draw(nc)
    nd.text((1040, 686), "CLICK TO WATCH NEXT EPISODE", font=load_font(FONT_MONO, 24), fill=(227, 184, 87, 245))
    # Bottom-left Subscribe zone reminder graphic
    nd.ellipse([100, 560, 280, 740], outline=(227, 184, 87, 220), width=3)
    nd.text((140, 632), "CH-13", font=load_font(FONT_MONO, 34), fill=(227, 184, 87, 245))
    nd.text((310, 620), "SUBSCRIBE TO DEAD CHANNEL 13", font=load_font(FONT_DISPLAY, 28), fill=(251, 246, 236, 240))
    nd.text((310, 662), "Full 1990s Cel Anime Series in JP Sub + EN Dub", font=load_font(FONT_DISPLAY, 22), fill=(199, 190, 176, 210))

    next_path = tmp_dir / f"ep{ep_num}_next_card.png"
    nc.convert("RGB").save(str(next_path), format="PNG")

    return bg_path, strip_path, mask_path, next_path, strip_h_used


def render_credits_sequence(
    tmp_dir: Path,
    ep_num: int,
    ep_title_en: str,
    ep_title_jp: str,
    gallery_imgs: List[Path],
    next_ep_label: str,
    next_ep_sub: str,
    next_ep_preview_img: Path,
    credits_audio_path: Path,
    audio_offset_sec: float,
    out_mp4: Path,
    next_ep_preview_video: Optional[Path] = None,
) -> Path:
    """Render 48.0s 1920x1080@24fps anime Ending Credits sequence with yyh01 Sunset Suite audio."""
    dur_total = 48.0
    scroll_dur = 40.7
    endcard_dur = 8.0
    xf_end = 0.7  # 40.7 + 8.0 - 0.7 = 48.0s exact

    bg_path, strip_path, mask_path, next_path, strip_h = create_credits_plates(
        tmp_dir, ep_num, ep_title_en, ep_title_jp, next_ep_label, next_ep_sub, next_ep_preview_img
    )

    # 1. Build 40.7s 890x500 gallery slideshow via FFmpeg xfade across 6 keyframes
    slides = gallery_imgs[:6]
    slide_d = 7.35  # 6 * 7.35 - 5 * 0.65 = 40.85s >= 40.7s
    xf = 0.65
    gal_mp4 = tmp_dir / f"ep{ep_num}_gallery.mp4"
    g_inputs: List[str] = []
    g_filters: List[str] = []
    for i, sp in enumerate(slides):
        if not sp.is_file():
            raise FileNotFoundError(f"Gallery keyframe missing: {sp}")
        g_inputs.extend(["-loop", "1", "-t", f"{slide_d:.2f}", "-i", str(sp)])
        g_filters.append(
            f"[{i}:v]fps=24,scale=890:500:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop=890:500,setsar=1,format=yuv420p[s{i}]"
        )
    prev = "[s0]"
    for i in range(1, len(slides)):
        offset = i * slide_d - i * xf
        out_lbl = "[gal_out]" if i == len(slides) - 1 else f"[x{i}]"
        g_filters.append(f"{prev}[s{i}]xfade=transition=fade:duration={xf:.2f}:offset={offset:.2f}{out_lbl}")
        prev = out_lbl

    run_ffmpeg(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *g_inputs, "-filter_complex", ";".join(g_filters),
         "-map", "[gal_out]", "-t", f"{scroll_dur:.2f}", "-r", "24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
         "-pix_fmt", "yuv420p", str(gal_mp4)],
        f"ep{ep_num} credits gallery",
    )

    # 2. Build 40.7s scrolling credits visual part
    scroll_mp4 = tmp_dir / f"ep{ep_num}_scroll_part.mp4"
    fc_scroll = (
        "[0:v]fps=24,format=rgba[bg];"
        "[1:v]fps=24,format=rgba[gal];"
        "[2:v]fps=24,format=rgba[strip];"
        "[3:v]fps=24,format=rgba[mask];"
        "[bg][gal]overlay=x=940:y=220[v1];"
        f"[v1][strip]overlay=x=90:y='940-(t/40.2)*(940+{strip_h})'[v2];"
        "[v2][mask]overlay=x=0:y=0,setsar=1,format=yuv420p[vout]"
    )
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", f"{scroll_dur:.2f}", "-i", str(bg_path),
            "-i", str(gal_mp4),
            "-loop", "1", "-t", f"{scroll_dur:.2f}", "-i", str(strip_path),
            "-loop", "1", "-t", f"{scroll_dur:.2f}", "-i", str(mask_path),
            "-filter_complex", fc_scroll,
            "-map", "[vout]", "-t", f"{scroll_dur:.2f}", "-r", "24",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            str(scroll_mp4),
        ],
        f"ep{ep_num} scroll part",
    )

    # 3. Build 8.0s Next Episode end-card part (with optional live sakuga preview clip!)
    endcard_mp4 = tmp_dir / f"ep{ep_num}_endcard_part.mp4"
    if next_ep_preview_video is not None and next_ep_preview_video.is_file():
        fc_end = (
            "[0:v]fps=24,format=rgba[nc];"
            "[1:v]setpts=1.35*PTS,fps=24,scale=740:416:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=740:416,setsar=1,format=rgba[prev];"
            "[nc][prev]overlay=x=1040:y=250:shortest=0,setsar=1,format=yuv420p[vout]"
        )
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-t", f"{endcard_dur:.2f}", "-i", str(next_path),
                "-i", str(next_ep_preview_video),
                "-filter_complex", fc_end,
                "-map", "[vout]", "-t", f"{endcard_dur:.2f}", "-r", "24",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
                str(endcard_mp4),
            ],
            f"ep{ep_num} animated endcard",
        )
    else:
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-t", f"{endcard_dur:.2f}", "-i", str(next_path),
                "-vf", "fps=24,setsar=1,format=yuv420p",
                "-t", f"{endcard_dur:.2f}", "-r", "24",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
                str(endcard_mp4),
            ],
            f"ep{ep_num} static endcard",
        )

    # 4. Prepare 48s credits audio segment with smooth fade-in and closing fade-out
    cred_wav = tmp_dir / f"ep{ep_num}_credits_audio.wav"
    fi_d = 1.2 if ep_num == 1 else 2.2
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{audio_offset_sec:.3f}", "-t", f"{dur_total:.3f}",
            "-i", str(credits_audio_path),
            "-af", f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d={fi_d:.2f},afade=t=out:st={dur_total - 4.5:.2f}:d=4.5",
            "-c:a", "pcm_s16le", str(cred_wav),
        ],
        f"ep{ep_num} credits audio trim",
    )

    # 5. Crossfade scroll_part -> endcard_part & mux credits audio cleanly
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(scroll_mp4),
            "-i", str(endcard_mp4),
            "-i", str(cred_wav),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={xf_end:.2f}:offset={scroll_dur - xf_end:.2f},"
            "fade=t=in:st=0:d=0.6,fade=t=out:st=46.8:d=1.2,setsar=1,format=yuv420p[vout]",
            "-map", "[vout]", "-map", "2:a",
            "-t", f"{dur_total:.2f}", "-r", "24",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
            str(out_mp4),
        ],
        f"ep{ep_num} credits final",
    )
    return out_mp4


def render_publish_episode(
    tmp_dir: Path,
    tag: str,
    hook_clips: List[Tuple[Path, float, float]],
    main_master: Path,
    credits_mp4: Path,
    out_mp4: Path,
) -> Dict[str, Any]:
    """Concatenate [Cold Hook + 0.2s Vacuum Black + Full Master + Credits] at 1920x1080@24fps with 1.5s audio overlap into credits."""
    hook_dur_sum = 0.0
    hook_aac_segs: List[Path] = []
    for idx, (clip_p, s0, dur) in enumerate(hook_clips):
        seg = tmp_dir / f"{tag}_h_{idx}.mkv"
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{s0:.3f}", "-t", f"{dur:.3f}", "-i", str(clip_p),
                "-vf", "fps=24,scale=1920:1080:flags=lanczos,setsar=1,eq=contrast=1.06:saturation=1.06,format=yuv420p",
                "-af", "aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.04,afade=t=out:st={:.3f}:d=0.06".format(max(0.1, dur - 0.06)),
                "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                "-c:a", "pcm_s16le", str(seg),
            ],
            f"{tag} hook mkv {idx}",
        )
        hook_aac_segs.append(seg)
        hook_dur_sum += dur

    vac_mkv = tmp_dir / f"{tag}_vac.mkv"
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-t", "0.20", "-i", "color=c=black:s=1920x1080:r=24",
            "-f", "lavfi", "-t", "0.20", "-i", "anullsrc=r=48000:cl=stereo",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le", str(vac_mkv),
        ],
        f"{tag} vacuum snap",
    )
    hook_dur_sum += 0.20

    main_info = probe_media(main_master)
    main_dur = main_info["duration_sec"]
    main_mkv = tmp_dir / f"{tag}_main_1080.mkv"
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(main_master),
            "-vf", f"fps=24,scale=1920:1080:flags=lanczos,setsar=1,eq=contrast=1.04:saturation=1.04,fade=t=in:st=0:d=0.12,fade=t=out:st={max(0, main_dur - 0.55):.3f}:d=0.55,format=yuv420p",
            "-af", f"aresample=48000,aformat=channel_layouts=stereo,afade=t=out:st={max(0, main_dur - 1.50):.3f}:d=1.50",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-c:a", "pcm_s16le", str(main_mkv),
        ],
        f"{tag} main 1080p",
    )

    cred_info = probe_media(credits_mp4)
    cred_dur = cred_info["duration_sec"]
    cred_mkv = tmp_dir / f"{tag}_cred_v.mkv"
    # Video track for credits starts right when main ends; its audio track will be delayed so it overlaps final 1.5s of main!
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(credits_mp4), "-an",
            "-c:v", "copy", str(cred_mkv),
        ],
        f"{tag} credits video copy",
    )

    # Concatenate video segments cleanly `[hooks..., vac, main, cred_v]`
    vid_inputs: List[str] = []
    concat_inputs = hook_aac_segs + [vac_mkv, main_mkv]
    v_concat_str = ""
    a_pre_str = ""
    for i, p in enumerate(concat_inputs):
        vid_inputs.extend(["-i", str(p)])
        v_concat_str += f"[{i}:v]"
        a_pre_str += f"[{i}:a]"
    idx_cv = len(concat_inputs)
    vid_inputs.extend(["-i", str(cred_mkv)])
    idx_ca = idx_cv + 1
    vid_inputs.extend(["-i", str(credits_mp4)])

    v_concat_all = v_concat_str + f"[{idx_cv}:v]"
    n_v = len(concat_inputs) + 1
    n_pre_a = len(concat_inputs)
    delay_ms = max(0, int(round((hook_dur_sum + main_dur - 1.50) * 1000.0)))
    total_target_dur = hook_dur_sum + main_dur + cred_dur

    raw_mix_mkv = tmp_dir / f"{tag}_pre_master.mkv"
    fc_all = (
        f"{v_concat_all}concat=n={n_v}:v=1:a=0[v_full];"
        f"{a_pre_str}concat=n={n_pre_a}:v=0:a=1,apad=whole_dur={total_target_dur:.3f}[a_pre];"
        f"[{idx_ca}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay_ms}|{delay_ms},apad=whole_dur={total_target_dur:.3f}[a_cred];"
        "[a_pre][a_cred]amix=inputs=2:normalize=0:duration=first[a_raw]"
    )
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *vid_inputs,
            "-filter_complex", fc_all,
            "-map", "[v_full]", "-map", "[a_raw]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le",
            "-t", f"{total_target_dur:.3f}",
            str(raw_mix_mkv),
        ],
        f"{tag} pre-master assembly",
    )

    gain_db = measure_gain_db(raw_mix_mkv, TARGET_LUFS)
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_mix_mkv),
            "-c:v", "copy",
            "-af", f"volume={gain_db:.3f}dB,alimiter=limit=0.88:level=false",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        f"{tag} final loudness master",
    )
    return probe_media(out_mp4)


def make_short_text_overlay(tmp_dir: Path, name: str, top_text: str, sub_text: str, accent: Tuple[int, int, int, int]) -> Path:
    """Create a 1080x1920 transparent emphasis caption plate in top/bottom safe zones (off action center)."""
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_top = load_font(FONT_IMPACT, 86)
    f_sub = load_font(FONT_DISPLAY, 44)
    f_tag = load_font(FONT_MONO, 28)

    # Top safe header band (y=210..470 — below YT Shorts top icons, above center hero window!)
    d.text((64, 210), "DEAD CHANNEL 13 // 1990s CEL ANIME", font=f_tag, fill=(227, 184, 87, 235))
    draw_outlined_text(d, (60, 255), top_text, f_top, (251, 246, 236, 255), stroke_w=7, shadow_offset=(4, 5))
    draw_outlined_text(d, (62, 365), sub_text, f_sub, accent, stroke_w=4, shadow_offset=(3, 3))

    # Bottom crisp hairline pill above Shorts caption UI (y=1370..1460)
    d.line([(64, 1368), (1016, 1368)], fill=(227, 184, 87, 160), width=2)
    out = tmp_dir / f"{name}.png"
    img.save(str(out), format="PNG")
    return out


def render_vertical_short(
    tmp_dir: Path,
    slug: str,
    beats: List[Dict[str, Any]],
    cta_bg_img: Path,
    cta_title: str,
    cta_sub: str,
    cta_dur: float,
    shorts_music_path: Path,
    music_start_sec: float,
    duck_silence_window: Optional[Tuple[float, float]],
    out_mp4: Path,
) -> Dict[str, Any]:
    """Render 1080x1920@24fps zero-black-bar vertical Short mixing original SFX/voice + ducked music."""
    beat_mkvs: List[Path] = []
    tot_dur = 0.0
    for idx, bt in enumerate(beats):
        ov_png = make_short_text_overlay(tmp_dir, f"{slug}_ov_{idx}", bt["top_text"], bt["sub_text"], bt["accent"])
        b_out = tmp_dir / f"{slug}_beat_{idx}.mkv"
        # Full-height blurred noir atmospheric fill (ZERO black bars!) + crisp 1080x760 center hero window w/ gold rules!
        vf = (
            "[0:v]fps=24,setsar=1,split=2[bg_src][fg_src];"
            "[bg_src]scale=1080:1920:force_original_aspect_ratio=increase:flags=bilinear,crop=1080:1920,"
            "boxblur=26:2,eq=brightness=-0.38:saturation=1.25[bg];"
            "[fg_src]crop=iw*0.86:ih,scale=1080:740:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:740,"
            "eq=contrast=1.08:saturation=1.08,drawbox=x=0:y=0:w=1080:h=3:color=0xe3b857@0.85:t=fill,"
            "drawbox=x=0:y=737:w=1080:h=3:color=0xe3b857@0.85:t=fill[fg];"
            "[bg][fg]overlay=x=0:y=560[comp];"
            "[1:v]format=rgba[ov];"
            "[comp][ov]overlay=x=0:y=0,format=yuv420p[vout]"
        )
        run_ffmpeg(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{bt['src_start']:.3f}", "-t", f"{bt['dur']:.3f}", "-i", str(bt["src"]),
                "-loop", "1", "-t", f"{bt['dur']:.3f}", "-i", str(ov_png),
                "-filter_complex", vf,
                "-map", "[vout]", "-map", "0:a",
                "-af", f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.05,afade=t=out:st={max(0.05, bt['dur']-0.06):.3f}:d=0.06",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                "-c:a", "pcm_s16le", str(b_out),
            ],
            f"{slug} beat {idx}",
        )
        beat_mkvs.append(b_out)
        tot_dur += float(bt["dur"])

    # Build final vertical CTA card (zero black bars!)
    cta_img = Image.new("RGBA", (1080, 1920), (10, 7, 14, 255))
    bg_cta = fit_cover(Image.open(cta_bg_img), 1080, 1920).filter(ImageFilter.GaussianBlur(radius=10))
    bg_cta = ImageEnhance.Brightness(bg_cta).enhance(0.38).convert("RGBA")
    cta_img = add_crt_scanlines(bg_cta, alpha=20, step=4)
    hero_inset = fit_cover(Image.open(cta_bg_img), 960, 540)
    cta_img.paste(hero_inset, (60, 560))
    cd = ImageDraw.Draw(cta_img)
    cd.rectangle([58, 558, 1022, 1102], outline=(227, 184, 87, 240), width=4)
    draw_outlined_text(cd, (64, 270), cta_title, load_font(FONT_IMPACT, 94), (227, 184, 87, 255), stroke_w=7)
    draw_outlined_text(cd, (64, 390), cta_sub, load_font(FONT_DISPLAY, 48), (251, 246, 236, 255), stroke_w=4)
    draw_outlined_text(cd, (64, 1180), "WATCH FULL EPISODE ON CHANNEL", load_font(FONT_MONO, 36), (56, 189, 248, 255), stroke_w=4)
    cta_png = tmp_dir / f"{slug}_cta.png"
    cta_img.convert("RGB").save(str(cta_png), format="PNG")

    cta_mkv = tmp_dir / f"{slug}_cta.mkv"
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", f"{cta_dur:.2f}", "-i", str(cta_png),
            "-f", "lavfi", "-t", f"{cta_dur:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", "fps=24,setsar=1,fade=t=in:st=0:d=0.18,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-c:a", "pcm_s16le", str(cta_mkv),
        ],
        f"{slug} cta mkv",
    )
    beat_mkvs.append(cta_mkv)
    tot_dur += cta_dur

    # Concatenate video & original dialogue/SFX track
    raw_av = tmp_dir / f"{slug}_concat.mkv"
    in_args: List[str] = []
    c_str = ""
    for i, p in enumerate(beat_mkvs):
        in_args.extend(["-i", str(p)])
        c_str += f"[{i}:v][{i}:a]"
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *in_args,
            "-filter_complex", f"{c_str}concat=n={len(beat_mkvs)}:v=1:a=1[vo][ao]",
            "-map", "[vo]", "-map", "[ao]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le",
            str(raw_av),
        ],
        f"{slug} concat beats",
    )

    # Mix ducked rom01 shorts beat (-11 dB base + optional vacuum dip) underneath SFX/dialogue
    duck_expr = ""
    if duck_silence_window is not None:
        d0, d1 = duck_silence_window
        duck_expr = f",volume=enable='between(t,{d0:.2f},{d1:.2f})':volume=0.08"

    pre_m = tmp_dir / f"{slug}_pre_master.mkv"
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_av),
            "-ss", f"{music_start_sec:.2f}", "-t", f"{tot_dur:.3f}", "-i", str(shorts_music_path),
            "-filter_complex",
            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=-11dB{duck_expr},"
            f"afade=t=out:st={max(0.5, tot_dur - 1.2):.2f}:d=1.2[mus];"
            f"[0:a][mus]amix=inputs=2:normalize=0:duration=first[amix_out]",
            "-map", "0:v", "-map", "[amix_out]",
            "-c:v", "copy", "-c:a", "pcm_s16le",
            "-t", f"{tot_dur:.3f}",
            str(pre_m),
        ],
        f"{slug} music mix",
    )

    gain_db = measure_gain_db(pre_m, TARGET_LUFS)
    run_ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(pre_m),
            "-c:v", "copy",
            "-af", f"volume={gain_db:.3f}dB,alimiter=limit=0.88:level=false",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        f"{slug} final short master",
    )
    return probe_media(out_mp4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DEAD CHANNEL 13 YouTube Publish Masters, Credits, Thumbnails, and Shorts.")
    parser.add_argument("--credits-audio", type=Path, default=DEFAULT_CREDITS_AUDIO, help="Path to ending credits audio master.")
    parser.add_argument("--shorts-music", type=Path, default=DEFAULT_SHORTS_MUSIC, help="Path to 9:16 Shorts backing beat.")
    args = parser.parse_args()

    if not args.credits_audio.is_file():
        raise FileNotFoundError(f"Credits audio not found: {args.credits_audio}")
    if not args.shorts_music.is_file():
        raise FileNotFoundError(f"Shorts music not found: {args.shorts_music}")

    PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    SHORTS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    thumbs = build_thumbnails()

    ep1_gallery = [
        PROJECT_ROOT / "frames_ep1" / "ep1_kf1_toma_shop.webp",
        PROJECT_ROOT / "frames_ep1" / "ep1_kf4_nixie_13001.webp",
        PROJECT_ROOT / "frames_ep1" / "ep1_kf10_kuroha_steps_in.webp",
        PROJECT_ROOT / "frames_ep1" / "ep1_kf13_deadfire_nullify.webp",
        PROJECT_ROOT / "frames_ep1" / "ep1_kf19_yuki_fresh.png",
        PROJECT_ROOT / "frames_ep1" / "ep1_kf20_masato_broadcast_hook.webp",
    ]
    ep2_gallery = [
        PROJECT_ROOT / "frames_ep2" / "ep2_kf1_jammer_drop.webp",
        PROJECT_ROOT / "frames_ep2" / "ep2_kf4_sweeper_alley_raid.webp",
        PROJECT_ROOT / "frames_ep2" / "ep2_kf8_cobalt_ricochet.webp",
        PROJECT_ROOT / "frames_ep2" / "ep2_kf11_pirate_bunker.webp",
        PROJECT_ROOT / "frames_ep2" / "ep2_kf14_sora_confession.webp",
        PROJECT_ROOT / "frames_ep2" / "ep2_kf15_ep02_cliffhanger.webp",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        ep1_cred = render_credits_sequence(
            tmp_dir=tmp_dir,
            ep_num=1,
            ep_title_en="RAIN ON THE GLASS",
            ep_title_jp="第一話「雨のガラス」",
            gallery_imgs=ep1_gallery,
            next_ep_label="EP 02 // THE Y2K PURGE",
            next_ep_sub="第2話 — Y2Kパージ // 06 DAYS REMAINING",
            next_ep_preview_img=PROJECT_ROOT / "frames_ep2" / "ep2_kf4_sweeper_alley_raid.webp",
            credits_audio_path=args.credits_audio,
            audio_offset_sec=0.0,
            out_mp4=tmp_dir / "ep1_credits.mp4",
            next_ep_preview_video=PROJECT_ROOT / "videos_ep2" / "ep2_04_sweeper_alley_raid.mp4",
        )

        ep2_cred = render_credits_sequence(
            tmp_dir=tmp_dir,
            ep_num=2,
            ep_title_en="THE Y2K PURGE",
            ep_title_jp="第2話「Y2Kパージ」",
            gallery_imgs=ep2_gallery,
            next_ep_label="EP 03 // GHOST #07",
            next_ep_sub="第3話 — 七番の亡霊 // 1998 DELETION LEDGER",
            next_ep_preview_img=PROJECT_ROOT / "frames_ep2" / "ep2_kf15_ep02_cliffhanger.webp",
            credits_audio_path=args.credits_audio,
            audio_offset_sec=86.2,
            out_mp4=tmp_dir / "ep2_credits.mp4",
        )

        ep1_hooks = [
            (PROJECT_ROOT / "videos_ep1" / "ep1_16_nixie_overclock_dial.mp4", 1.8, 1.5),
            (PROJECT_ROOT / "videos_ep1" / "ep1_17_time_tear_counter.mp4", 1.2, 2.5),
        ]
        ep2_hooks = [
            (PROJECT_ROOT / "videos_ep2" / "ep2_01_jammer_drop.mp4", 0.6, 1.8),
            (PROJECT_ROOT / "videos_ep2" / "ep2_08_cobalt_ricochet.mp4", 0.8, 1.8),
        ]

        ep1_jp = render_publish_episode(
            tmp_dir, "ep1_jp", ep1_hooks,
            MASTERS_DIR / "DEAD_CHANNEL_13_EP01_FULL_PILOT_JP_SUB.mp4",
            ep1_cred, PUBLISH_DIR / "DEAD_CHANNEL_13_EP01_YOUTUBE_JP_SUB.mp4",
        )
        ep1_en = render_publish_episode(
            tmp_dir, "ep1_en", ep1_hooks,
            MASTERS_DIR / "DEAD_CHANNEL_13_EP01_FULL_PILOT_EN_DUB.mp4",
            ep1_cred, PUBLISH_DIR / "DEAD_CHANNEL_13_EP01_YOUTUBE_EN_DUB.mp4",
        )
        ep2_jp = render_publish_episode(
            tmp_dir, "ep2_jp", ep2_hooks,
            MASTERS_DIR / "DEAD_CHANNEL_13_EP02_FULL_EPISODE_JP_SUB.mp4",
            ep2_cred, PUBLISH_DIR / "DEAD_CHANNEL_13_EP02_YOUTUBE_JP_SUB.mp4",
        )

        short01 = render_vertical_short(
            tmp_dir=tmp_dir,
            slug="short01",
            beats=[
                {
                    "src": PROJECT_ROOT / "videos_ep1" / "ep1_16_nixie_overclock_dial.mp4",
                    "src_start": 1.2,
                    "dur": 4.8,
                    "top_text": "TIME BREAKS",
                    "sub_text": "PAST 13.001 SECONDS",
                    "accent": (227, 184, 87, 255),
                },
                {
                    "src": PROJECT_ROOT / "videos_ep1" / "ep1_17_time_tear_counter.mp4",
                    "src_start": 0.6,
                    "dur": 5.2,
                    "top_text": "ERASED FUTURE",
                    "sub_text": "DRAGGED INTO PRESENT COMBAT",
                    "accent": (56, 189, 248, 255),
                },
                {
                    "src": PROJECT_ROOT / "videos_ep1" / "ep1_12_sakuga_slash_flurry.mp4",
                    "src_start": 0.8,
                    "dur": 4.6,
                    "top_text": "OBSIDIAN FLAME",
                    "sub_text": "ZERO 3D CGI // PURE 90s CEL",
                    "accent": (192, 132, 252, 255),
                },
                {
                    "src": PROJECT_ROOT / "videos_ep1" / "ep1_19_yuki_signal_twist.mp4",
                    "src_start": 0.2,
                    "dur": 5.6,
                    "top_text": "WAIT FOR THIS",
                    "sub_text": "CHECK EVERY BROKEN CRT",
                    "accent": (239, 68, 68, 255),
                },
            ],
            cta_bg_img=PROJECT_ROOT / "frames_ep1" / "ep1_kf19_yuki_fresh.png",
            cta_title="EP 01 LIVE NOW",
            cta_sub="FULL PILOT // JP SUB + EN DUB",
            cta_dur=3.8,
            shorts_music_path=args.shorts_music,
            music_start_sec=0.0,
            duck_silence_window=(14.4, 15.0),
            out_mp4=SHORTS_DIR / "DC13_SHORT01_13_SECOND_RULE_9x16.mp4",
        )

        short02 = render_vertical_short(
            tmp_dir=tmp_dir,
            slug="short02",
            beats=[
                {
                    "src": PROJECT_ROOT / "videos_ep2" / "ep2_01_jammer_drop.mp4",
                    "src_start": 0.6,
                    "dur": 4.6,
                    "top_text": "THE Y2K PURGE",
                    "sub_text": "6 DAYS UNTIL TOTAL WIPE",
                    "accent": (239, 68, 68, 255),
                },
                {
                    "src": PROJECT_ROOT / "videos_ep2" / "ep2_04_sweeper_alley_raid.mp4",
                    "src_start": 0.6,
                    "dur": 4.6,
                    "top_text": "WATCH STOPPED",
                    "sub_text": "ONE ESCAPE UNDERGROUND",
                    "accent": (227, 184, 87, 255),
                },
                {
                    "src": PROJECT_ROOT / "videos_ep2" / "ep2_08_cobalt_ricochet.mp4",
                    "src_start": 0.8,
                    "dur": 4.6,
                    "top_text": "RAIL RICOCHET",
                    "sub_text": "COBALT PULSE-SHOT OVERLOAD",
                    "accent": (56, 189, 248, 255),
                },
                {
                    "src": PROJECT_ROOT / "videos_ep2" / "ep2_14_sora_confession.mp4",
                    "src_start": 0.2,
                    "dur": 5.0,
                    "top_text": "THE CONFESSION",
                    "sub_text": "WHO LOGGED 1998 ERASURE?",
                    "accent": (239, 68, 68, 255),
                },
            ],
            cta_bg_img=PROJECT_ROOT / "frames_ep2" / "ep2_kf15_ep02_cliffhanger.webp",
            cta_title="EP 02 LIVE NOW",
            cta_sub="EP 03 GHOST #07 IN PRODUCTION",
            cta_dur=3.2,
            shorts_music_path=args.shorts_music,
            music_start_sec=9.6,
            duck_silence_window=(13.6, 14.2),
            out_mp4=SHORTS_DIR / "DC13_SHORT02_Y2K_PURGE_9x16.mp4",
        )

    print(json.dumps({
        "status": "success",
        "thumbnails": thumbs,
        "youtube_masters": {
            "ep01_jp_sub": ep1_jp,
            "ep01_en_dub": ep1_en,
            "ep02_jp_sub": ep2_jp,
        },
        "shorts": {
            "short01_13_second_rule": short01,
            "short02_y2k_purge": short02,
        },
    }, indent=2))


if __name__ == "__main__":
    main()
