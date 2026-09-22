"""
Remotion Video & Motion Graphics Engine Bridge
Provides programmatic video compositing and motion rendering powered by Remotion (React + Headless Chrome).

Features:
- Word-level kinetic subtitles with spring bounce / pop / karaoke animations.
- Dynamic Motion Badges (Glassmorphism, Alert, Cyber, Sticker) with animated emojis and spring physics.
- Hook Header Overlays (Top / Center / Bottom).
- Video camera zooms and aesthetic grading.
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).parent.resolve()
REMOTION_DIR = BASE_DIR / "remotion"
REMOTION_BIN = REMOTION_DIR / "node_modules" / ".bin" / "remotion"

def is_remotion_available() -> bool:
    """Checks whether Remotion CLI is installed and operational."""
    return REMOTION_BIN.exists()

def build_remotion_subtitles(
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    font_family: str = "Arial",
    font_size: int = 56,
    highlight_color: str = "#FFDD00",
    animation: str = "pop"
) -> Optional[Dict[str, Any]]:
    """Converts Faster-Whisper segments into Remotion SubtitleConfig format."""
    captions = []
    
    for seg in segments:
        if seg.get("end", 0.0) < clip_start or seg.get("start", 0.0) > clip_end:
            continue
        
        words = seg.get("words", [])
        if words:
            for w in words:
                w_start = w.get("start", 0.0)
                w_end = w.get("end", 0.0)
                w_text = w.get("word", "").strip()
                if not w_text or w_end < clip_start or w_start > clip_end:
                    continue
                
                rel_start_ms = max(0, int((w_start - clip_start) * 1000))
                rel_end_ms = max(rel_start_ms + 100, int((w_end - clip_start) * 1000))
                captions.append({
                    "text": w_text.upper(),
                    "startMs": rel_start_ms,
                    "endMs": rel_end_ms
                })
        else:
            # Fallback when no word timestamps are provided
            text_words = seg.get("text", "").strip().split()
            s_start = max(0.0, seg.get("start", 0.0) - clip_start)
            s_end = max(s_start + 0.5, seg.get("end", 0.0) - clip_start)
            dur = (s_end - s_start) / max(1, len(text_words))
            for i, tw in enumerate(text_words):
                captions.append({
                    "text": tw.upper(),
                    "startMs": int((s_start + i * dur) * 1000),
                    "endMs": int((s_start + (i + 1) * dur) * 1000)
                })

    if not captions:
        return None

    return {
        "captions": captions,
        "position": "bottom",
        "style": {
            "fontFamily": font_family,
            "fontSize": font_size,
            "fontColor": "#FFFFFF",
            "highlightColor": highlight_color,
            "borderColor": "#000000",
            "borderWidth": 4,
            "bgColor": "#000000",
            "bgOpacity": 0,
            "animation": animation
        }
    }

def build_remotion_motion_badges(
    dynamic_effects: List[Dict[str, Any]],
    clip_duration: float
) -> List[Dict[str, Any]]:
    """Converts AI Director cues into Remotion MotionBadgeConfig format."""
    badges = []
    for eff in dynamic_effects:
        title = eff.get("badge_title") or eff.get("word") or "KEY MOMENT"
        emoji = eff.get("emoji") or "🔥"
        t_start = float(eff.get("time", 2.0))
        t_dur = float(eff.get("duration", 2.4))
        style = eff.get("badge_style", "glass")
        color = eff.get("accent_color", "#38bdf8")

        badges.append({
            "title": title.upper(),
            "emoji": emoji,
            "startSec": round(t_start, 2),
            "durationSec": round(t_dur, 2),
            "style": style,
            "accentColor": color,
            "positionY": 48
        })
    return badges

def render_with_remotion(
    video_path: str,
    output_path: str,
    duration_sec: float,
    subtitles_config: Optional[Dict[str, Any]] = None,
    hook_text: Optional[str] = None,
    motion_badges: Optional[List[Dict[str, Any]]] = None,
    effects_config: Optional[Dict[str, Any]] = None,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920
) -> str:
    """
    Renders video using Remotion's CLI renderer.
    """
    if not is_remotion_available():
        raise RuntimeError("Remotion engine is not installed or available.")

    total_frames = int(round(duration_sec * fps))

    hook_config = None
    if hook_text and hook_text.strip():
        hook_config = {
            "text": hook_text.strip(),
            "position": "top",
            "size": "M",
            "entranceAnimation": "spring",
            "displayDurationSec": min(6.0, duration_sec),
            "style": "classic"
        }

    props = {
        "videoUrl": os.path.abspath(video_path),
        "durationInFrames": total_frames,
        "fps": fps,
        "width": width,
        "height": height,
        "subtitles": subtitles_config,
        "hook": hook_config,
        "motionBadges": motion_badges or [],
        "effects": effects_config or None
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(props, tf, indent=2)
        props_file = tf.name

    try:
        out_abs = os.path.abspath(output_path)
        cmd = [
            str(REMOTION_BIN),
            "render",
            "src/index.ts",
            "ShortVideo",
            out_abs,
            f"--props={props_file}",
            "--codec=h264",
            "--crf=21",
            "--gl=angle",
            "--concurrency=2"
        ]

        print(f"[*] Remotion rendering composition ShortVideo ({total_frames} frames)...")
        res = subprocess.run(cmd, cwd=str(REMOTION_DIR), capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[!] Remotion Error:\n{res.stderr}")
            raise RuntimeError(f"Remotion render failed with code {res.returncode}:\n{res.stderr}")

        print(f"[*] Remotion render successfully finished: {output_path}")
        return out_abs

    finally:
        if os.path.exists(props_file):
            try:
                os.remove(props_file)
            except Exception:
                pass
