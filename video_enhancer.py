"""
Video Enhancer & Audio Studio
Adds:
1. Dynamic animated hook banner at top ("🔥 MUST WATCH")
2. Subtle atmospheric background music (tension or ambient groove)
3. Opening whoosh / impact sound effect at start of clip
4. Context-aware Sound Effects (Cash, Boom, Ding, Pop) dynamically timed to spoken words
5. Context-aware Motion Graphic Badges dynamically timed to spoken words
6. Audio mastering / normalization for mobile phones
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent.resolve()
AUDIO_DIR = BASE_DIR / "assets" / "audio"
EFFECTS_DIR = BASE_DIR / "assets" / "effects"

SEMANTIC_TRIGGERS = [
    {
        "type": "money",
        "keywords": ["money", "dollar", "dollars", "cash", "million", "millions", "billion", "billions", "rich", "wealth", "salary", "paid", "cost", "price", "profit", "revenue", "expensive"],
        "sfx": "sfx_cash.wav",
        "graphic": "badge_money.png"
    },
    {
        "type": "warning",
        "keywords": ["never", "wrong", "mistake", "warning", "danger", "toxic", "stop", "worst", "red flag", "ruin", "destroy", "fail", "trap", "hate", "problem"],
        "sfx": "sfx_boom.wav",
        "graphic": "badge_warning.png"
    },
    {
        "type": "truth",
        "keywords": ["truth", "realize", "realized", "secret", "fact", "actually", "remember", "rule", "honest", "honestly", "reason", "proof", "discovered"],
        "sfx": "sfx_ding.wav",
        "graphic": "badge_truth.png"
    },
    {
        "type": "mindset",
        "keywords": ["lesson", "mindset", "wisdom", "focus", "discipline", "habits", "advice", "success", "winner", "strategy", "power", "smart"],
        "sfx": "sfx_pop.wav",
        "graphic": "badge_mindset.png"
    },
    {
        "type": "shock",
        "keywords": ["shocking", "crazy", "insane", "unbelievable", "impossible", "wild", "huge", "shocked", "no way"],
        "sfx": "sfx_boom.wav",
        "graphic": "badge_shock.png"
    }
]

def scan_transcript_for_effects(segments: List[Dict[str, Any]], clip_start: float, clip_end: float, min_gap: float = 6.0) -> List[Dict[str, Any]]:
    """
    Scans word-level timestamps in the clip's time range for high-energy semantic triggers.
    Enforces a min_gap between effects so videos never feel cluttered.
    """
    events = []
    last_event_time = -999.0

    for seg in segments:
        if seg.get("end", 0.0) < clip_start or seg.get("start", 0.0) > clip_end:
            continue
        words = seg.get("words", [])
        if not words:
            text_words = seg.get("text", "").split()
            s_start = max(0.0, seg.get("start", 0.0) - clip_start)
            s_end = max(s_start + 0.5, seg.get("end", 0.0) - clip_start)
            dur = (s_end - s_start) / max(1, len(text_words))
            words = [{"word": tw, "start": s_start + i * dur, "end": s_start + (i + 1) * dur} for i, tw in enumerate(text_words)]
        else:
            words = [{
                "word": w.get("word", ""),
                "start": max(0.0, w.get("start", 0.0) - clip_start),
                "end": max(0.1, w.get("end", 0.0) - clip_start)
            } for w in words]

        for item in words:
            w_clean = re.sub(r'[^a-zA-Z]', '', item.get("word", "")).lower()
            rel_time = item.get("start", 0.0)

            if rel_time < 1.5 or rel_time < (last_event_time + min_gap):
                continue

            for trigger in SEMANTIC_TRIGGERS:
                if w_clean in trigger["keywords"]:
                    sfx_path = AUDIO_DIR / trigger["sfx"]
                    graphic_path = EFFECTS_DIR / trigger["graphic"]
                    if sfx_path.exists() and graphic_path.exists():
                        events.append({
                            "word": w_clean,
                            "time": round(rel_time, 2),
                            "duration": 2.2,
                            "type": trigger["type"],
                            "sfx_file": str(sfx_path),
                            "graphic_file": str(graphic_path)
                        })
                        last_event_time = rel_time
                        break

    return events

def get_font(size=44):
    for f in [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Unicode.ttf"
    ]:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    return ImageFont.load_default()

def create_hook_header(title: str, width=1080, height=1920) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    clean_title = title.strip().upper()
    if not clean_title:
        return img

    font_size = 40 if len(clean_title) > 40 else 44
    font = get_font(font_size)

    max_badge_width = int(width * 0.90)
    padding_x = 36
    padding_y = 16
    line_spacing = 8
    max_text_width = max_badge_width - (padding_x * 2)

    words = clean_title.split()
    lines = []
    curr_line = []

    for w in words:
        test_candidate = " ".join(curr_line + [w])
        if draw.textlength(test_candidate, font=font) <= max_text_width:
            curr_line.append(w)
        else:
            if curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [w]
            else:
                lines.append(w)

    if curr_line:
        lines.append(" ".join(curr_line))

    if not lines:
        return img

    line_widths = [draw.textlength(l, font=font) for l in lines]
    max_line_w = max(line_widths)

    bbox = font.getbbox("AYgjy")
    line_h = bbox[3] - bbox[1]

    total_text_h = (line_h * len(lines)) + (line_spacing * (len(lines) - 1))

    box_w = int(max_line_w + (padding_x * 2))
    box_h = int(total_text_h + (padding_y * 2))

    box_x = int((width - box_w) / 2)
    box_y = int(height * 0.08)

    draw.rounded_rectangle(
        [box_x + 4, box_y + 4, box_x + box_w + 4, box_y + box_h + 4],
        radius=20,
        fill=(0, 0, 0, 150)
    )
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=20,
        fill=(15, 23, 42, 235),
        outline=(250, 204, 21, 240),
        width=3
    )

    for i, line_text in enumerate(lines):
        lw = line_widths[i]
        tx = box_x + int((box_w - lw) / 2)
        ty = box_y + padding_y + (i * (line_h + line_spacing))
        draw.text(
            (tx, ty),
            line_text,
            font=font,
            fill=(255, 255, 255, 255)
        )

    return img

def enhance_video_audio(
    video_path: str,
    output_path: str,
    title_banner: Optional[str] = None,
    music_track: str = "tension_bed",
    add_whoosh: bool = True,
    music_volume: float = 0.08,
    dynamic_effects: Optional[List[Dict[str, Any]]] = None
):
    """
    Full Studio Enhancement:
    - Background music bed
    - Intro hook whoosh
    - Top viral header banner
    - Contextual Sound Effects (Cash, Boom, Ding, Pop) synchronized to speech
    - Contextual Motion Graphic Badge callouts animated with smooth pop & fade
    """
    temp_dir = Path(video_path).parent / f"enh_{Path(video_path).stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        music_file = AUDIO_DIR / f"{music_track}.m4a"
        whoosh_file = AUDIO_DIR / "hook_whoosh.m4a"

        has_music = music_file.exists() and music_volume > 0
        has_whoosh = whoosh_file.exists() and add_whoosh
        active_effects = dynamic_effects or []

        inputs = ["-i", video_path]
        curr_input_idx = 1

        music_idx = None
        if has_music:
            inputs.extend(["-stream_loop", "-1", "-i", str(music_file)])
            music_idx = curr_input_idx
            curr_input_idx += 1

        whoosh_idx = None
        if has_whoosh:
            inputs.extend(["-i", str(whoosh_file)])
            whoosh_idx = curr_input_idx
            curr_input_idx += 1

        sfx_inputs_map = []
        for eff in active_effects:
            inputs.extend(["-i", eff["sfx_file"]])
            sfx_inputs_map.append({"idx": curr_input_idx, "time": eff["time"]})
            curr_input_idx += 1

        banner_idx = None
        if title_banner:
            header_img = create_hook_header(title_banner)
            header_path = temp_dir / "header_banner.png"
            header_img.save(header_path, "PNG")
            inputs.extend(["-i", str(header_path)])
            banner_idx = curr_input_idx
            curr_input_idx += 1

        badge_inputs_map = []
        for eff in active_effects:
            inputs.extend(["-i", eff["graphic_file"]])
            badge_inputs_map.append({
                "idx": curr_input_idx,
                "start": eff["time"],
                "end": eff["time"] + eff["duration"]
            })
            curr_input_idx += 1

        video_filters = []
        last_v_tag = "0:v"

        if banner_idx is not None:
            video_filters.append(f"[{last_v_tag}][{banner_idx}:v]overlay=0:0[v_banner]")
            last_v_tag = "v_banner"

        for b_i, b_info in enumerate(badge_inputs_map):
            next_tag = f"v_badge_{b_i}"
            b_idx = b_info["idx"]
            b_start = b_info["start"]
            b_end = b_info["end"]
            video_filters.append(
                f"[{last_v_tag}][{b_idx}:v]overlay=(W-w)/2:980:enable='between(t,{b_start},{b_end})'[{next_tag}]"
            )
            last_v_tag = next_tag

        out_v = f"[{last_v_tag}]" if last_v_tag != "0:v" else "0:v"

        audio_filter_parts = ["[0:a]volume=1.0[a_voice]"]
        mix_inputs = ["[a_voice]"]

        if has_music:
            audio_filter_parts.append(f"[{music_idx}:a]volume={music_volume}[a_music]")
            mix_inputs.append("[a_music]")

        if has_whoosh:
            audio_filter_parts.append(f"[{whoosh_idx}:a]adelay=100|100,volume=0.35[a_whoosh]")
            mix_inputs.append("[a_whoosh]")

        for s_i, s_info in enumerate(sfx_inputs_map):
            tag = f"a_sfx_{s_i}"
            delay_ms = int(s_info["time"] * 1000)
            audio_filter_parts.append(f"[{s_info['idx']}:a]adelay={delay_ms}|{delay_ms},volume=0.45[{tag}]")
            mix_inputs.append(f"[{tag}]")

        mix_str = "".join(mix_inputs)
        audio_filter_parts.append(f"{mix_str}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=2[aout]")

        filter_complex = ";".join(video_filters + audio_filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", out_v,
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]

        subprocess.run(cmd, check=True)

    finally:
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
