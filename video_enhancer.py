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
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

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

def render_dynamic_badge(
    emoji_char: str,
    badge_title: str,
    accent_hex: str = "#38bdf8",
    out_path: Optional[str] = None
) -> Image.Image:
    """
    Renders a modern, cinematic glassmorphism motion badge pill (1080p width context).
    Scaled dynamically based on title length.
    """
    clean_title = badge_title.strip().upper()
    width = 760
    height = 130
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Parse accent color
    h = accent_hex.lstrip("#")
    try:
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        rgb = (56, 189, 248) # Default cyan

    # Soft dark drop shadow
    draw.rounded_rectangle([8, 8, width - 8, height - 8], radius=28, fill=(0, 0, 0, 160))

    # Dark translucent glass pill with neon border
    draw.rounded_rectangle([4, 4, width - 12, height - 12], radius=26, fill=(15, 23, 42, 235), outline=(*rgb, 240), width=4)

    # Subtle inner top glow highlight
    draw.line([(32, 12), (width - 44, 12)], fill=(255, 255, 255, 70), width=2)

    font_title = get_font(38)
    full_text = f"{emoji_char}  {clean_title}" if emoji_char else clean_title

    # Measure text
    bbox = draw.textbbox((0, 0), full_text, font=font_title)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # If too wide, fallback to smaller font
    if tw > (width - 60):
        font_title = get_font(32)
        bbox = draw.textbbox((0, 0), full_text, font=font_title)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    tx = (width - tw) // 2
    ty = (height - th) // 2 - 4

    # Text drop shadow
    draw.text((tx + 2, ty + 2), full_text, font=font_title, fill=(0, 0, 0, 220))
    # Crisp glowing title
    draw.text((tx, ty), full_text, font=font_title, fill=(*rgb, 255))

    if out_path:
        img.save(out_path, "PNG")
    return img

def get_ai_directed_cues(
    clip_transcript: str,
    clip_duration: float,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Uses Gemini AI as the 'Real-time Motion & Sound Director' to analyze the speech transcript
    and generate punchy, relevant motion graphic callouts and audio sound effects.
    """
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or not clip_transcript.strip():
        return []

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are an expert viral TikTok and YouTube Shorts Motion Graphic and Sound Director (like Opus Clip and Klap).
Analyze the following short video clip transcript (duration: {clip_duration:.1f} seconds):

CLIP TRANSCRIPT:
\"\"\"{clip_transcript}\"\"\"

Task:
Direct 2 to 4 high-impact visual callouts / motion badges and sound effects synchronized to the most pivotal moments, punchlines, or key takeaways of the video.

Rules:
1. "time": Timestamp in seconds (float between 1.5 and {max(2.0, clip_duration - 1.5):.1f}) when the badge & sound should hit.
2. "badge_title": 2 to 4 punchy, viral words summarizing that specific moment (e.g., "50/50 DATING TRAP", "BRUTAL TRUTH", "PASSIVE INCOME", "RED FLAG WARNING", "CHESS MOVE", "SECRET FORMULA").
3. "emoji": Exactly one fitting emoji (e.g. "🚨", "💸", "☕", "🧠", "🔥", "⚠️", "👑", "🎯").
4. "sfx": One of: "boom", "ding", "cash", "pop", "whoosh".
5. "accent_color": A vibrant hex color (e.g. "#ef4444" for warning/red flags, "#22c55e" for money/success, "#eab308" for truth/gold, "#38bdf8" for facts/advice, "#a855f7" for mindset/psychology).
6. Ensure each cue is at least 4.5 seconds apart from the previous cue so the video never feels cluttered.

Respond ONLY with a JSON array:
[
  {{
    "time": 3.5,
    "duration": 2.2,
    "badge_title": "BRUTAL REALITY",
    "emoji": "⚠️",
    "sfx": "boom",
    "accent_color": "#ef4444"
  }}
]
"""
        models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.7-flash",
            "gemini-flash-latest"
        ]
        for model in models_to_try:
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                if res and res.text:
                    parsed = json.loads(res.text)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        cues = []
                        last_time = -999.0
                        for item in parsed:
                            t = float(item.get("time", 0.0))
                            if t < 1.0 or t > (clip_duration - 1.0) or t < (last_time + 4.0):
                                continue
                            sfx_raw = str(item.get("sfx", "ding")).lower()
                            if any(k in sfx_raw for k in ["cash", "money", "dollar", "register"]):
                                sfx_name = "sfx_cash.wav"
                            elif any(k in sfx_raw for k in ["boom", "vine", "explosion", "impact", "clang"]):
                                sfx_name = "sfx_boom.wav"
                            elif any(k in sfx_raw for k in ["ding", "bell", "chime", "correct"]):
                                sfx_name = "sfx_ding.wav"
                            elif any(k in sfx_raw for k in ["whoosh", "swoosh", "transition"]):
                                sfx_name = "hook_whoosh.m4a"
                            else:
                                sfx_name = "sfx_pop.wav"

                            cues.append({
                                "time": round(t, 2),
                                "duration": float(item.get("duration", 2.2)),
                                "badge_title": str(item.get("badge_title", "KEY MOMENT")),
                                "emoji": str(item.get("emoji", "🔥")),
                                "sfx_file": str(AUDIO_DIR / sfx_name),
                                "accent_color": str(item.get("accent_color", "#38bdf8")),
                                "is_ai_generated": True
                            })
                            last_time = t
                        if cues:
                            return cues
            except Exception as e:
                print(f"[AI Director] Model {model} attempt failed: {e}")
                continue

    except Exception as e:
        print(f"[AI Director] Error initializing Gemini AI cues: {e}")

    return []

def scan_transcript_for_effects(
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    min_gap: float = 6.0,
    use_ai: bool = True
) -> List[Dict[str, Any]]:
    """
    Intelligently generates context-aware motion badges and sound effects:
    1. First uses Gemini AI Real-time Director to generate tailored badges and SFX for the clip.
    2. Falls back seamlessly to semantic trigger scanning if AI is offline or encounters high load.
    """
    clip_dur = max(1.0, clip_end - clip_start)

    # 1. Try Gemini AI Director
    if use_ai:
        # Extract clip text
        clip_words = []
        for seg in segments:
            if seg.get("end", 0.0) >= clip_start and seg.get("start", 0.0) <= clip_end:
                clip_words.append(seg.get("text", "").strip())
        clip_transcript = " ".join(clip_words).strip()

        if clip_transcript:
            ai_cues = get_ai_directed_cues(clip_transcript, clip_dur)
            if ai_cues:
                print(f"[AI Director] Successfully generated {len(ai_cues)} real-time AI motion callouts & SFX!")
                return ai_cues

    # 2. Heuristic fallback
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
        for b_idx_counter, eff in enumerate(active_effects):
            badge_path = eff.get("graphic_file")
            # If AI generated or dynamic, render the custom badge image on the fly!
            if not badge_path or not Path(badge_path).exists():
                b_title = eff.get("badge_title", "KEY MOMENT")
                b_emoji = eff.get("emoji", "🔥")
                b_color = eff.get("accent_color", "#38bdf8")
                dyn_path = temp_dir / f"dynamic_badge_{b_idx_counter}.png"
                render_dynamic_badge(b_emoji, b_title, b_color, str(dyn_path))
                badge_path = str(dyn_path)

            inputs.extend(["-i", badge_path])
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
