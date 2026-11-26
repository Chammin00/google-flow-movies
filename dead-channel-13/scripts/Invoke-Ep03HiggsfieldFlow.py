#!/usr/bin/env python3
"""
Invoke-Ep03HiggsfieldFlow.py

Validates DEAD CHANNEL 13 Episode 03 ("Ghost Number Seven") hybrid pipeline
routing between Google Flow (Nano Banana 2 + Omni 1.2 Flash) and Higgsfield AI
(Seedream + Kling v2.1 Pro / Seedance v1 Pro), checks credentials, and emits
ready-to-execute MCP / Flow generation manifests in --dry-run mode.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PIPELINE = PROJECT_ROOT / "ep03" / "ep03_higgsfield_flow_pipeline.json"


def validate_pipeline(doc: Dict[str, Any]) -> Dict[str, Any]:
    required_top = ("schema", "episode", "target_resolution", "fps", "style_lock", "output_dirs", "shots")
    for key in required_top:
        if key not in doc:
            raise ValueError(f"Missing top-level field '{key}' in pipeline manifest.")

    shots: List[Dict[str, Any]] = doc["shots"]
    if not shots:
        raise ValueError("Pipeline shots list cannot be empty.")

    seen_ids = set()
    flow_shots: List[str] = []
    hf_shots: List[str] = []

    for s in shots:
        sid = s.get("id")
        if not sid or sid in seen_ids:
            raise ValueError(f"Invalid or duplicate shot id: {sid}")
        seen_ids.add(sid)

        route = s.get("route")
        if route == "google_flow":
            if not s.get("prompt"):
                raise ValueError(f"Google Flow shot '{sid}' missing prompt.")
            if float(s.get("playback_speed", 1.0)) != 1.0 and s.get("dialogue_jp"):
                raise ValueError(f"Spoken lip-sync shot '{sid}' must keep playback_speed=1.0.")
            flow_shots.append(sid)
        elif route == "higgsfield":
            for req in ("higgsfield_image_tool", "higgsfield_video_tool", "image_prompt", "video_prompt"):
                if not s.get(req):
                    raise ValueError(f"Higgsfield shot '{sid}' missing '{req}'.")
            if s["higgsfield_video_tool"] not in ("generate_video_kling", "generate_video_seedance"):
                raise ValueError(f"Unsupported Higgsfield video model on '{sid}': {s['higgsfield_video_tool']}")
            hf_shots.append(sid)
        else:
            raise ValueError(f"Unknown route '{route}' on shot '{sid}'.")

    return {
        "episode": doc["episode"],
        "total_shots": len(shots),
        "google_flow_shots": flow_shots,
        "higgsfield_sakuga_shots": hf_shots,
        "target_resolution": doc["target_resolution"],
        "fps": doc["fps"],
    }


def build_mcp_payload_preview(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    frames_dir = PROJECT_ROOT / doc["output_dirs"]["frames"]

    for s in doc["shots"]:
        if s["route"] == "higgsfield":
            local_ref = frames_dir / f"{s['id']}.png"
            image_payload = {
                "server": "higgsfield",
                "tool": s["higgsfield_image_tool"],
                "arguments": {
                    "prompt": f"{s['image_prompt']} Style: {doc['style_lock']}",
                    "aspect_ratio": s.get("aspect_ratio", "16:9"),
                    "resolution": s.get("resolution", "1080p"),
                    "camera_fixed": False,
                },
            }
            video_payload = {
                "server": "higgsfield",
                "tool": s["higgsfield_video_tool"],
                "arguments": {
                    "image_url": f"<upload_image(local={local_ref}) -> public_url>",
                    "prompt": s["video_prompt"],
                },
                "post_fx": {
                    "playback_speed": s.get("playback_speed", 1.8),
                    "on_twos": bool(s.get("on_twos", True)),
                    "hit_stop_frames": int(s.get("hit_stop_frames", 3)),
                    "color_script": s.get("color_script", "none"),
                    "vacuum_cut_sec": float(s.get("vacuum_cut_sec", 0.0)),
                },
            }
            payloads.append({
                "shot_id": s["id"],
                "act": s.get("act"),
                "route": "higgsfield",
                "step1_image": image_payload,
                "step2_video": video_payload,
            })
        else:
            payloads.append({
                "shot_id": s["id"],
                "act": s.get("act"),
                "route": "google_flow",
                "image_model": s["image_model"],
                "video_model": s["video_model"],
                "playback_speed": s.get("playback_speed", 1.0),
                "prompt": s["prompt"],
                "dialogue_jp": s.get("dialogue_jp"),
                "dialogue_en": s.get("dialogue_en"),
            })
    return payloads


def check_higgsfield_env() -> Dict[str, Any]:
    api_key = bool(os.environ.get("HIGGSFIELD_API_KEY", "").strip())
    api_secret = bool(os.environ.get("HIGGSFIELD_API_SECRET", "").strip())
    return {
        "HIGGSFIELD_API_KEY_set": api_key,
        "HIGGSFIELD_API_SECRET_set": api_secret,
        "live_mcp_ready": api_key and api_secret,
    }


def helper_encode_base64_for_upload(img_path: Path) -> str:
    """Utility showing exact raw base64 format expected by higgsfield.upload_image."""
    return base64.b64encode(img_path.read_bytes()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and dispatch Episode 03 hybrid Google Flow + Higgsfield pipeline.")
    parser.add_argument("--pipeline", type=Path, default=DEFAULT_PIPELINE, help="Path to ep03_higgsfield_flow_pipeline.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate schema, check credentials, and print routed payload plan.")
    args = parser.parse_args()

    if not args.pipeline.is_file():
        raise FileNotFoundError(f"Pipeline file not found: {args.pipeline}")

    doc = json.loads(args.pipeline.read_text(encoding="utf-8"))
    summary = validate_pipeline(doc)
    creds = check_higgsfield_env()

    for rel_dir in doc["output_dirs"].values():
        (PROJECT_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)

    previews = build_mcp_payload_preview(doc)
    result = {
        "status": "dry_run_validated" if args.dry_run else ("ready" if creds["live_mcp_ready"] else "blocked_missing_higgsfield_credentials"),
        "summary": summary,
        "credentials": creds,
        "routed_shots": previews,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not args.dry_run and not creds["live_mcp_ready"]:
        print(
            "\nERROR: HIGGSFIELD_API_KEY and HIGGSFIELD_API_SECRET must be set before live execution (or use --dry-run).",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
