#!/usr/bin/env python3
"""
Build-MushroomGaidenPublishSuite.py

Completes YouTube & Shorts publishing assets for MUSHROOM GAIDEN:
  1. English Action Dub master (masters/MUSHROOM_GAIDEN_ACTION_SHORT_EN_DUB.mp4)
     reusing the 1080p24 CLEAN video stream, with en-US edge-tts dialogue
     (Toad/Toadette/Lord Kuro-Kame), smart native-speech ducking, and two-pass
     EBU R128 mastering (-14.0 LUFS, -1.0 dBTP).
  2. Zero-black-bar 9:16 vertical YouTube Short (publish/shorts/MUSHROOM_GAIDEN_SHORT_9x16.mp4)
     at 1080x1920 @ 24fps combining atmospheric full-bleed motion backdrop,
     1080x740 gold-framed action window, safe-zone typography, CTA card,
     native SFX, and 142 BPM score with pre-climax vacuum dip.
  3. publish/PUBLISH_MANIFEST.json summarizing ffprobe & loudnorm verification.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

SCRIPT_DIR = Path(__file__).resolve().parent


def load_assembler_module():
    """Import Assemble-MushroomGaiden.py helpers to avoid duplicating pipeline logic."""
    mod_path = SCRIPT_DIR / "Assemble-MushroomGaiden.py"
    spec = importlib.util.spec_from_file_location("assemble_mg", str(mod_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ASM = load_assembler_module()

SHORTS_DIR = ASM.PUBLISH_DIR / "shorts"

EN_VOICES = {
    "Toad (Ryu)": [("en-US-AndrewNeural", "+8%", "+8Hz", 0.0)],
    "Toadette (Ayane)": [("en-US-AriaNeural", "+10%", "+12Hz", 0.0)],
    "Lord Kuro-Kame": [("en-US-ChristopherNeural", "-10%", "-24Hz", 0.0)],
    "Toad & Toadette": [
        ("en-US-AndrewNeural", "+10%", "+8Hz", -0.25),
        ("en-US-AriaNeural", "+10%", "+12Hz", 0.25),
    ],
}


def read_wav_f32(path: Path) -> np.ndarray:
    """Read 16-bit PCM WAV into float32 stereo array in [-1.0, 1.0]."""
    with wave.open(str(path), "rb") as wf:
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32767.0
        ch = wf.getnchannels()
        if ch == 1:
            return np.repeat(raw[:, None], 2, axis=1)
        return raw.reshape(-1, ch)[:, :2]


def write_wav_f32(path: Path, stereo: np.ndarray) -> None:
    """Write float32 stereo array to 48kHz 16-bit PCM WAV."""
    pcm = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(ASM.SR)
        wf.writeframes(pcm.tobytes())


def compute_exact_timeline(manifest: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    """Reproduce exact frame-level timeline offsets matching Assemble-MushroomGaiden.py."""
    cur_frames = int(round(2.8 * ASM.FPS))
    timeline: List[Dict[str, Any]] = []

    for shot in manifest["shots"]:
        sid = shot["id"]
        mp4_path = ASM.VIDEOS_DIR / f"{sid}.mp4"
        cap = cv2.VideoCapture(str(mp4_path))
        n_raw = 0
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            n_raw += 1
        cap.release()
        if n_raw == 0:
            raise RuntimeError(f"Zero frames in {mp4_path}")

        speed = float(shot.get("playback_speed", 1.0))
        if shot.get("dialogue_jp") and sid in ("shot_02", "shot_06", "shot_09"):
            speed = 1.0

        sampled_count = 0
        acc = 0.0
        while int(round(acc)) < n_raw:
            sampled_count += 1
            acc += speed

        hs_frames = int(shot.get("hit_stop_frames", 0) or 0)
        if not (hs_frames > 0 and sampled_count > 8):
            hs_frames = 0

        shot_len = sampled_count + hs_frames
        shot_dur = shot_len / float(ASM.FPS)

        if sid == "shot_09" and cur_frames >= 10 and shot_len >= 10:
            start_frame = cur_frames - 10
            cur_frames = start_frame + shot_len
        else:
            start_frame = cur_frames
            cur_frames += shot_len

        timeline.append({
            "shot": shot,
            "mp4": mp4_path,
            "speed": speed,
            "start_sec": start_frame / float(ASM.FPS),
            "duration_sec": shot_dur,
        })

    end_frames = int(round(3.8 * ASM.FPS))
    total_sec = (cur_frames + end_frames) / float(ASM.FPS)
    return total_sec, timeline


async def synthesize_en_dub_lines(
    timeline: List[Dict[str, Any]],
    tmp_dir: Path,
) -> List[Tuple[float, float, Path, float]]:
    """Generate English voice lines via edge-tts, returning (abs_start, end_rel_pad, wav, pan)."""
    results: List[Tuple[float, float, Path, float]] = []
    for entry in timeline:
        shot = entry["shot"]
        sid = shot["id"]
        subs = [s for s in shot.get("subtitles", []) if s.get("speaker") != "SFX / Impact"]
        for idx, sub in enumerate(subs):
            speaker = sub.get("speaker", "Toad (Ryu)")
            spoken_text = sub["text"].replace("&", "and")
            voices = EN_VOICES.get(speaker, EN_VOICES["Toad (Ryu)"])
            for v_idx, (voice, rate, pitch, pan) in enumerate(voices):
                mp3_p = tmp_dir / f"{sid}_en_{idx}_{v_idx}.mp3"
                wav_p = tmp_dir / f"{sid}_en_{idx}_{v_idx}.wav"
                comm = edge_tts.Communicate(spoken_text, voice=voice, rate=rate, pitch=pitch)
                await comm.save(str(mp3_p))
                ASM.run_cmd(
                    ["ffmpeg", "-y", "-v", "error", "-i", str(mp3_p), "-ar", str(ASM.SR), "-ac", "2", str(wav_p)],
                    f"decode en tts {wav_p.name}",
                )
                abs_start = entry["start_sec"] + float(sub["start_rel"])
                abs_end = entry["start_sec"] + float(sub["end_rel"])
                results.append((abs_start, abs_end, wav_p, pan))
    return results


def build_english_dub_master(manifest: Dict[str, Any], tmp_dir: Path) -> Dict[str, Any]:
    """Build MUSHROOM_GAIDEN_ACTION_SHORT_EN_DUB.mp4 copying CLEAN video stream."""
    clean_mp4 = ASM.MASTERS_DIR / "MUSHROOM_GAIDEN_ACTION_SHORT_CLEAN.mp4"
    score_wav = ASM.AUDIO_DIR / "mushroom_gaiden_score.wav"
    if not clean_mp4.is_file():
        raise FileNotFoundError(f"Clean master missing: {clean_mp4}")
    if not score_wav.is_file():
        raise FileNotFoundError(f"Score WAV missing: {score_wav}")

    total_sec, timeline = compute_exact_timeline(manifest)
    score_arr = read_wav_f32(score_wav)
    n_tot = len(score_arr)
    mix = score_arr * 0.82

    # Synthesize English TTS stems
    tts_events = asyncio.run(synthesize_en_dub_lines(timeline, tmp_dir))

    # Build native SFX bed ducked cleanly under English spoken windows
    native_env = np.ones(n_tot, dtype=np.float32) * 0.90
    fade_len = int(0.08 * ASM.SR)
    for abs_start, abs_end, wav_p, _ in tts_events:
        arr = read_wav_f32(wav_p)
        spoken_dur = len(arr) / float(ASM.SR)
        win_end = max(abs_end, abs_start + spoken_dur)
        i0 = max(0, int(round((abs_start - 0.06) * ASM.SR)))
        i1 = min(n_tot, int(round((win_end + 0.08) * ASM.SR)))
        if i1 > i0:
            native_env[i0:i1] = np.minimum(native_env[i0:i1], 0.16)
            # Smooth edges
            if i0 >= fade_len:
                native_env[i0 - fade_len:i0] = np.minimum(
                    native_env[i0 - fade_len:i0],
                    np.linspace(0.90, 0.16, fade_len, dtype=np.float32),
                )
            if i1 + fade_len <= n_tot:
                native_env[i1:i1 + fade_len] = np.minimum(
                    native_env[i1:i1 + fade_len],
                    np.linspace(0.16, 0.90, fade_len, dtype=np.float32),
                )

    native_bed = np.zeros_like(mix)
    for entry in timeline:
        sid = entry["shot"]["id"]
        speed = entry["speed"]
        shot_dur = entry["duration_sec"]
        n_wav = tmp_dir / f"{sid}_en_native.wav"
        atempo = f"atempo={speed:.3f}," if abs(speed - 1.0) > 0.01 else ""
        ASM.run_cmd(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(entry["mp4"]),
                "-af", f"{atempo}aresample={ASM.SR}", "-ac", "2", "-t", f"{shot_dur:.3f}",
                str(n_wav),
            ],
            f"extract native sfx {sid}",
        )
        arr = read_wav_f32(n_wav)
        i0 = max(0, int(round(entry["start_sec"] * ASM.SR)))
        cnt = min(len(arr), n_tot - i0)
        if cnt > 0:
            seg = arr[:cnt].copy()
            f_edge = min(cnt // 2, int(0.025 * ASM.SR))
            if f_edge > 0:
                ramp = np.linspace(0.0, 1.0, f_edge, dtype=np.float32)[:, None]
                seg[:f_edge] *= ramp
                seg[-f_edge:] *= ramp[::-1]
            native_bed[i0:i0 + cnt] += seg

    mix += native_bed * native_env[:, None]

    # Overlay crisp English dub dialogue
    for abs_start, _, wav_p, pan in tts_events:
        arr = read_wav_f32(wav_p)
        i0 = max(0, int(round(abs_start * ASM.SR)))
        cnt = min(len(arr), n_tot - i0)
        if cnt > 0:
            seg = arr[:cnt].copy()
            f_edge = min(cnt // 4, int(0.015 * ASM.SR))
            if f_edge > 0:
                ramp = np.linspace(0.0, 1.0, f_edge, dtype=np.float32)[:, None]
                seg[:f_edge] *= ramp
                seg[-f_edge:] *= ramp[::-1]
            lg = 1.08 * float(np.sqrt(max(0.0, (1.0 - pan))))
            rg = 1.08 * float(np.sqrt(max(0.0, (1.0 + pan))))
            mix[i0:i0 + cnt, 0] += seg[:, 0] * lg
            mix[i0:i0 + cnt, 1] += seg[:, 1] * rg

    pk = float(np.max(np.abs(mix))) if len(mix) else 1.0
    if pk > 0.94:
        mix *= 0.94 / pk
    en_mix_wav = tmp_dir / "en_dub_mix.wav"
    write_wav_f32(en_mix_wav, mix)

    out_en = ASM.MASTERS_DIR / "MUSHROOM_GAIDEN_ACTION_SHORT_EN_DUB.mp4"
    ASM.two_pass_loudnorm_mux(clean_mp4, en_mix_wav, out_en)
    return ASM.probe_media(out_en)


def draw_outlined(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: Any,
    fill: Tuple[int, int, int, int],
    stroke_w: int = 5,
) -> None:
    """Draw outlined high-contrast typography with subtle drop shadow."""
    x, y = xy
    draw.text((x + 4, y + 5), text, font=font, fill=(6, 4, 10, 210))
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=(8, 6, 12, 255))


def make_short_overlay(tmp_dir: Path, idx: int, top_text: str, sub_text: str, accent: Tuple[int, int, int, int]) -> Path:
    """Render 1080x1920 transparent safe-zone title & framing overlay for a Shorts beat."""
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_tag = ASM.load_font(ASM.FONT_JP_BOLD, 28)
    f_top = ASM.load_font(ASM.FONT_IMPACT, 88)
    f_sub = ASM.load_font(ASM.FONT_DISPLAY, 42)
    f_bot = ASM.load_font(ASM.FONT_JP_BOLD, 30)

    d.text((64, 210), "MUSHROOM GAIDEN // キノコ伝", font=f_tag, fill=(240, 192, 82, 240), stroke_width=3, stroke_fill=(8, 6, 12, 255))
    draw_outlined(d, (60, 256), top_text, f_top, (252, 248, 238, 255), stroke_w=7)
    draw_outlined(d, (62, 366), sub_text, f_sub, accent, stroke_w=4)

    # Clean gold bottom hairline and tagline safely above YouTube Shorts UI chrome
    d.line([(64, 1368), (1016, 1368)], fill=(240, 192, 82, 180), width=2)
    draw_outlined(d, (64, 1390), "TOAD AS RYU HAYABUSA  •  TOADETTE AS AYANE", f_bot, (220, 212, 248, 240), stroke_w=3)

    out = tmp_dir / f"short_ov_{idx}.png"
    img.save(str(out), format="PNG")
    return out


def build_vertical_short(tmp_dir: Path) -> Dict[str, Any]:
    """Build zero-black-bar 1080x1920@24fps vertical YouTube Short teaser."""
    SHORTS_DIR.mkdir(parents=True, exist_ok=True)
    score_wav = ASM.AUDIO_DIR / "mushroom_gaiden_score.wav"
    out_mp4 = SHORTS_DIR / "MUSHROOM_GAIDEN_SHORT_9x16.mp4"

    beats = [
        {"src": ASM.VIDEOS_DIR / "shot_01.mp4", "src_start": 0.5, "dur": 3.8, "top": "TOAD × RYU", "sub": "MOONLIT PAGODA DROP", "accent": (120, 220, 255, 255)},
        {"src": ASM.VIDEOS_DIR / "shot_04.mp4", "src_start": 1.2, "dur": 4.2, "top": "IZUNA DROP!!", "sub": "DRAGON CLAN AERIAL SLAM", "accent": (240, 192, 82, 255)},
        {"src": ASM.VIDEOS_DIR / "shot_05.mp4", "src_start": 0.8, "dur": 4.2, "top": "TOADETTE × AYANE", "sub": "PHANTOM BLOSSOM CYCLONE", "accent": (225, 145, 255, 255)},
        {"src": ASM.VIDEOS_DIR / "shot_06.mp4", "src_start": 1.2, "dur": 3.8, "top": "BOSS BREACH", "sub": "LORD KURO-KAME AWAKENS", "accent": (255, 115, 100, 255)},
        {"src": ASM.VIDEOS_DIR / "shot_08.mp4", "src_start": 0.6, "dur": 4.2, "top": "TWIN NINPO", "sub": "DRAGON & BLOSSOM CLIMAX", "accent": (90, 230, 255, 255)},
    ]

    beat_mkvs: List[Path] = []
    tot_dur = 0.0
    for idx, bt in enumerate(beats):
        ov_png = make_short_overlay(tmp_dir, idx, bt["top"], bt["sub"], bt["accent"])
        b_out = tmp_dir / f"short_beat_{idx}.mkv"
        vf = (
            "[0:v]fps=24,setsar=1,split=2[bg_src][fg_src];"
            "[bg_src]scale=1080:1920:force_original_aspect_ratio=increase:flags=bilinear,crop=1080:1920,"
            "boxblur=26:2,eq=brightness=-0.38:saturation=1.22[bg];"
            "[fg_src]crop=iw*0.86:ih,scale=1080:740:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:740,"
            "eq=contrast=1.08:saturation=1.08,drawbox=x=0:y=0:w=1080:h=3:color=0xf0c052@0.90:t=fill,"
            "drawbox=x=0:y=737:w=1080:h=3:color=0xf0c052@0.90:t=fill[fg];"
            "[bg][fg]overlay=x=0:y=560[comp];"
            "[1:v]format=rgba[ov];"
            "[comp][ov]overlay=x=0:y=0,format=yuv420p[vout]"
        )
        ASM.run_cmd(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{bt['src_start']:.3f}", "-t", f"{bt['dur']:.3f}", "-i", str(bt["src"]),
                "-loop", "1", "-t", f"{bt['dur']:.3f}", "-i", str(ov_png),
                "-filter_complex", vf,
                "-map", "[vout]", "-map", "0:a",
                "-af", f"aresample={ASM.SR},aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.05,afade=t=out:st={max(0.05, bt['dur'] - 0.06):.3f}:d=0.06",
                "-c:v", "libx264", "-preset", "fast", "-crf", "16",
                "-c:a", "pcm_s16le", str(b_out),
            ],
            f"short beat {idx}",
        )
        beat_mkvs.append(b_out)
        tot_dur += float(bt["dur"])

    # Vertical CTA End Card (3.2s)
    cta_dur = 3.2
    cta_src = ASM.FRAMES_DIR / "shot_08_canon.webp"
    bg_cta = ASM.fit_cover_pil(Image.open(cta_src), 1080, 1920).filter(ImageFilter.GaussianBlur(radius=12))
    bg_cta = ImageEnhance.Brightness(bg_cta).enhance(0.32).convert("RGBA")
    hero_inset = ASM.fit_cover_pil(Image.open(cta_src), 960, 540)
    bg_cta.paste(hero_inset, (60, 560))
    cd = ImageDraw.Draw(bg_cta)
    cd.rectangle([58, 558, 1022, 1102], outline=(240, 192, 82, 240), width=4)
    draw_outlined(cd, (64, 240), "MUSHROOM GAIDEN", ASM.load_font(ASM.FONT_IMPACT, 94), (240, 192, 82, 255), stroke_w=7)
    draw_outlined(cd, (64, 360), "FULL SHORT LIVE  •  JP SUB + EN DUB", ASM.load_font(ASM.FONT_DISPLAY, 44), (252, 248, 238, 255), stroke_w=4)
    draw_outlined(cd, (64, 1170), "WATCH FULL MOVIE ON CHANNEL", ASM.load_font(ASM.FONT_MONO, 36), (120, 220, 255, 255), stroke_w=4)

    cta_png = tmp_dir / "short_cta.png"
    bg_cta.convert("RGB").save(str(cta_png), format="PNG")
    cta_mkv = tmp_dir / "short_cta.mkv"
    ASM.run_cmd(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", f"{cta_dur:.2f}", "-i", str(cta_png),
            "-f", "lavfi", "-t", f"{cta_dur:.2f}", "-i", f"anullsrc=r={ASM.SR}:cl=stereo",
            "-vf", "fps=24,setsar=1,fade=t=in:st=0:d=0.18,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16",
            "-c:a", "pcm_s16le", str(cta_mkv),
        ],
        "short cta mkv",
    )
    beat_mkvs.append(cta_mkv)
    tot_dur += cta_dur

    # Concat video + native SFX track
    concat_mkv = tmp_dir / "short_concat.mkv"
    in_args: List[str] = []
    c_str = ""
    for i, p in enumerate(beat_mkvs):
        in_args.extend(["-i", str(p)])
        c_str += f"[{i}:v][{i}:a]"
    ASM.run_cmd(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *in_args,
            "-filter_complex", f"{c_str}concat=n={len(beat_mkvs)}:v=1:a=1[vo][ao]",
            "-map", "[vo]", "-map", "[ao]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le", str(concat_mkv),
        ],
        "concat short beats",
    )

    # Mix 142 BPM action score (starting at 2.4s where drums/shamisen drop) with pre-climax vacuum dip
    pre_short = tmp_dir / "short_pre_master.mkv"
    ASM.run_cmd(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(concat_mkv),
            "-ss", "2.40", "-t", f"{tot_dur:.3f}", "-i", str(score_wav),
            "-filter_complex",
            f"[1:a]aresample={ASM.SR},aformat=channel_layouts=stereo,volume=-8dB,"
            f"volume=enable='between(t,15.75,16.00)':volume=0.06,"
            f"afade=t=out:st={max(0.5, tot_dur - 1.2):.2f}:d=1.2[mus];"
            f"[0:a][mus]amix=inputs=2:normalize=0:duration=first[amix_out]",
            "-map", "0:v", "-map", "[amix_out]",
            "-c:v", "copy", "-c:a", "pcm_s16le", "-t", f"{tot_dur:.3f}", str(pre_short),
        ],
        "short score mix",
    )

    # Extract pre-master audio for two-pass loudnorm and mux cleanly
    short_wav = tmp_dir / "short_pre_norm.wav"
    ASM.run_cmd(["ffmpeg", "-y", "-v", "error", "-i", str(pre_short), "-vn", "-c:a", "pcm_s16le", str(short_wav)], "extract short wav")
    ASM.two_pass_loudnorm_mux(pre_short, short_wav, out_mp4)
    return ASM.probe_media(out_mp4)


def main() -> None:
    manifest = json.loads(ASM.SHOTS_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="mg_pub_") as tmp_str:
        tmp_dir = Path(tmp_str)
        en_dub = build_english_dub_master(manifest, tmp_dir)
        short_9x16 = build_vertical_short(tmp_dir)

    pub_manifest = {
        "title": manifest["title"],
        "subtitle_jp": manifest["subtitle_jp"],
        "masters": {
            "jp_sub": ASM.probe_media(ASM.MASTERS_DIR / "MUSHROOM_GAIDEN_ACTION_SHORT_JP_SUB.mp4"),
            "en_dub": en_dub,
            "clean": ASM.probe_media(ASM.MASTERS_DIR / "MUSHROOM_GAIDEN_ACTION_SHORT_CLEAN.mp4"),
        },
        "shorts": {
            "short_9x16": short_9x16,
        },
        "assets": {
            "thumbnail": str(ASM.PUBLISH_DIR / "MUSHROOM_GAIDEN_THUMBNAIL.png"),
            "storyboard": str(ASM.PROJECT_ROOT / "storyboard_sheet.png"),
            "score": str(ASM.AUDIO_DIR / "mushroom_gaiden_score.wav"),
        },
    }
    manifest_out = ASM.PUBLISH_DIR / "PUBLISH_MANIFEST.json"
    manifest_out.write_text(json.dumps(pub_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(pub_manifest, indent=2))


if __name__ == "__main__":
    main()
