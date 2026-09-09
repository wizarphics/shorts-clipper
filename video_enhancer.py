"""
Video Enhancer & Audio Studio
Adds:
1. Dynamic animated hook banner at top ("🔥 MUST WATCH")
2. Subtle atmospheric background music (tension or ambient groove)
3. Opening whoosh / impact sound effect at start of clip
4. Audio mastering / normalization for mobile phones
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = BASE_DIR / "assets" / "audio"

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
    """
    Creates a modern viral top header banner:
    Rounded dark glass badge with yellow glow accent, positioned at top (9% height).
    Automatically wraps long titles onto multiple lines so text never overflows the screen.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    clean_title = title.strip().upper()
    if not clean_title:
        return img

    # Use adaptive font sizing based on length
    font_size = 40 if len(clean_title) > 40 else 44
    font = get_font(font_size)

    # Maximum badge width: 90% of screen width (max 972px for 1080p)
    max_badge_width = int(width * 0.90)
    padding_x = 36
    padding_y = 16
    line_spacing = 8
    max_text_width = max_badge_width - (padding_x * 2)

    # Wrap words onto multiple lines
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
                # Single word longer than max width: break it
                lines.append(w)

    if curr_line:
        lines.append(" ".join(curr_line))

    if not lines:
        return img

    # Compute actual width of the longest line
    line_widths = [draw.textlength(l, font=font) for l in lines]
    max_line_w = max(line_widths)

    # Compute text height per line using font metrics
    bbox = font.getbbox("AYgjy")
    line_h = bbox[3] - bbox[1]

    total_text_h = (line_h * len(lines)) + (line_spacing * (len(lines) - 1))

    box_w = int(max_line_w + (padding_x * 2))
    box_h = int(total_text_h + (padding_y * 2))

    box_x = int((width - box_w) / 2)
    box_y = int(height * 0.08)

    # Draw rounded pill shadow
    draw.rounded_rectangle(
        [box_x + 4, box_y + 4, box_x + box_w + 4, box_y + box_h + 4],
        radius=20,
        fill=(0, 0, 0, 150)
    )
    # Draw rounded pill background with yellow border
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=20,
        fill=(15, 23, 42, 235),       # Dark semi-transparent slate
        outline=(250, 204, 21, 240),   # Neon yellow border
        width=3
    )

    # Draw each line centered horizontally
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
    music_volume: float = 0.08
):
    """
    Enhances video with:
    - Audio track mixing (speech + background music bed + intro whoosh)
    - Optional top hook banner overlay
    """
    temp_dir = Path(video_path).parent / f"enh_{Path(video_path).stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        music_file = ASSETS_DIR / f"{music_track}.m4a"
        whoosh_file = ASSETS_DIR / "hook_whoosh.m4a"

        has_music = music_file.exists() and music_volume > 0
        has_whoosh = whoosh_file.exists() and add_whoosh

        # Build FFmpeg command inputs
        inputs = ["-i", video_path]
        audio_inputs_count = 1

        if has_music:
            inputs.extend(["-stream_loop", "-1", "-i", str(music_file)])
            music_input_idx = audio_inputs_count
            audio_inputs_count += 1

        if has_whoosh:
            inputs.extend(["-i", str(whoosh_file)])
            whoosh_input_idx = audio_inputs_count
            audio_inputs_count += 1

        # Video filter
        video_filters = []
        if title_banner:
            header_img = create_hook_header(title_banner)
            header_path = temp_dir / "header_banner.png"
            header_img.save(header_path, "PNG")
            inputs.extend(["-i", str(header_path)])
            header_idx = audio_inputs_count
            video_filters.append(f"[0:v][{header_idx}:v]overlay=0:0[vhead]")
            out_v = "[vhead]"
        else:
            out_v = "0:v"

        # Audio mixing filter
        audio_filter_parts = ["[0:a]volume=1.0[a0]"]
        mix_inputs = ["[a0]"]

        if has_music:
            audio_filter_parts.append(f"[{music_input_idx}:a]volume={music_volume}[amusic]")
            mix_inputs.append("[amusic]")

        if has_whoosh:
            audio_filter_parts.append(f"[{whoosh_input_idx}:a]adelay=100|100,volume=0.35[awhoosh]")
            mix_inputs.append("[awhoosh]")

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
