"""
High-Quality Viral Subtitle Generator for Shorts / TikTok / Reels.
Creates modern, bold animated captions with word-level highlights
and overlays them onto 9:16 videos via FFmpeg.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Find best bold font on macOS
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

def get_font(size=64):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    return ImageFont.load_default()

def clean_word(w):
    return re.sub(r'[\r\n\t]+', '', w).strip()

def build_caption_groups(all_segments, clip_start, clip_end, words_per_group=4):
    """
    Filters words belonging to the clip time window and clusters them into short,
    punchy phrases (3-5 words) suitable for mobile retention.
    """
    clip_words = []
    for seg in all_segments:
        # Check if segment overlaps with clip
        if seg["end"] < clip_start or seg["start"] > clip_end:
            continue
        
        words = seg.get("words", [])
        if words:
            for w in words:
                w_start = w["start"]
                w_end = w["end"]
                w_text = clean_word(w["word"])
                if not w_text:
                    continue
                # Keep word if within clip boundary
                if w_end >= clip_start and w_start <= clip_end:
                    rel_start = max(0.0, w_start - clip_start)
                    rel_end = max(rel_start + 0.1, w_end - clip_start)
                    clip_words.append({
                        "word": w_text.upper(),
                        "start": rel_start,
                        "end": rel_end
                    })
        else:
            # Fallback if no word timestamps: estimate from segment
            seg_words = clean_word(seg["text"]).split()
            if not seg_words:
                continue
            seg_start = max(0.0, seg["start"] - clip_start)
            seg_end = max(seg_start + 0.5, seg["end"] - clip_start)
            dur = (seg_end - seg_start) / len(seg_words)
            for i, sw in enumerate(seg_words):
                clip_words.append({
                    "word": sw.upper(),
                    "start": seg_start + i * dur,
                    "end": seg_start + (i + 1) * dur
                })

    if not clip_words:
        return []

    # Group into punchy clusters
    groups = []
    for i in range(0, len(clip_words), words_per_group):
        chunk = clip_words[i:i + words_per_group]
        g_start = chunk[0]["start"]
        g_end = chunk[-1]["end"]
        groups.append({
            "start": g_start,
            "end": g_end,
            "words": chunk
        })
    return groups

def render_caption_frame(words, active_idx, width=1080, height=1920, font_size=62):
    """
    Renders a single subtitle frame (transparent PNG) with:
    - Bold font
    - Heavy black outline / stroke
    - Active word highlighted in bright yellow (#FFE600)
    - Inactive words in crisp white (#FFFFFF)
    - Automatic wrapping onto multiple lines so captions never exceed screen width
    - Vertically centered around ~72% height (eye-level for vertical shorts)
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(font_size)
    stroke_w = 6

    # Safe subtitle width: max 86% of screen width (keeps 7% margin on each side)
    max_line_width = int(width * 0.86)
    space_w = draw.textlength(" ", font=font)

    # Precalculate each word width
    word_metrics = []
    for idx, w in enumerate(words):
        w_text = w["word"]
        w_w = draw.textlength(w_text, font=font)
        word_metrics.append((idx, w, w_w))

    # Flow words into lines
    lines = []
    curr_line = []
    curr_w = 0.0

    for item in word_metrics:
        w_w = item[2]
        added = w_w if not curr_line else (space_w + w_w)
        if curr_line and (curr_w + added > max_line_width):
            lines.append(curr_line)
            curr_line = [item]
            curr_w = w_w
        else:
            curr_line.append(item)
            curr_w += added

    if curr_line:
        lines.append(curr_line)

    if not lines:
        return img

    bbox = font.getbbox("AYgjy")
    line_h = bbox[3] - bbox[1]
    line_gap = 10
    total_block_h = (line_h * len(lines)) + (line_gap * (len(lines) - 1))

    # Center the entire subtitle block vertically around 72% height
    base_y = int(height * 0.72) - int(total_block_h / 2)

    for line_idx, line in enumerate(lines):
        line_w = sum(it[2] for it in line) + space_w * (len(line) - 1)
        line_x = int((width - line_w) / 2)
        line_y = base_y + line_idx * (line_h + line_gap)

        curr_x = line_x
        for (idx, w, w_w) in line:
            is_active = (idx == active_idx)
            fill_color = (255, 230, 0, 255) if is_active else (255, 255, 255, 255)
            stroke_color = (0, 0, 0, 255)

            draw.text(
                (curr_x, line_y),
                w["word"],
                font=font,
                fill=fill_color,
                stroke_width=stroke_w,
                stroke_fill=stroke_color
            )
            curr_x += w_w + space_w

    return img

def burn_subtitles(video_path, groups, output_path, fps=25):
    """
    Creates image overlays and uses FFmpeg to burn high-retention captions into the video.
    """
    if not groups:
        shutil.copy(video_path, output_path)
        return

    # Temporary directory for overlay frames
    temp_dir = Path(video_path).parent / f"overlay_{Path(video_path).stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Build ASS subtitle file with inline styling for maximum quality and speed
        ass_path = temp_dir / "captions.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,76,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,3,2,40,40,480,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            for g in groups:
                words = g["words"]
                for active_i, w in enumerate(words):
                    w_start = w["start"]
                    w_end = w["end"]
                    if w_end <= w_start:
                        continue

                    def fmt_time(seconds):
                        h = int(seconds // 3600)
                        m = int((seconds % 3600) // 60)
                        s = int(seconds % 60)
                        cs = int(round((seconds - int(seconds)) * 100))
                        if cs >= 100:
                            cs = 99
                        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

                    t_start = fmt_time(w_start)
                    t_end = fmt_time(w_end)

                    # Highlight active word in neon yellow (&H0000E6FF in ASS BGR format)
                    formatted_words = []
                    for i, item in enumerate(words):
                        if i == active_i:
                            formatted_words.append(r"{\c&H0000E6FF\b1}" + item["word"] + r"{\c&H00FFFFFF\b1}")
                        else:
                            formatted_words.append(item["word"])

                    dialogue_text = " ".join(formatted_words)
                    f.write(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{dialogue_text}\n")

        # Test if libass/subtitles filter works in ffmpeg or fallback to image sequence
        test_sub_cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"subtitles={ass_path}", "-t", "0.1", "-f", "null", "-"]
        sub_test = subprocess.run(test_sub_cmd, capture_output=True, text=True)

        if sub_test.returncode == 0:
            print("[*] Burning subtitles using FFmpeg ASS subtitle filter...")
            burn_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={ass_path}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-c:a", "copy",
                output_path
            ]
            subprocess.run(burn_cmd, check=True)
        else:
            # High-compatibility fallback: Render key transparent PNG frames and overlay
            print("[*] Rendering animated caption overlays via PIL...")
            render_and_overlay_pil(video_path, groups, output_path, temp_dir)

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

def render_and_overlay_pil(video_path, groups, output_path, temp_dir):
    """
    Renders high-res PNG caption overlays and uses FFmpeg complex filter
    with enable='between(t, ...)' for precision frame overlay.
    """
    filter_complex_parts = []
    input_args = ["-i", video_path]
    current_stream = "[0:v]"

    # Prepare individual unique subtitle state images
    frame_idx = 0
    overlay_entries = []

    for g in groups:
        words = g["words"]
        for active_i, w in enumerate(words):
            img = render_caption_frame(words, active_i)
            img_file = temp_dir / f"caption_{frame_idx:04d}.png"
            img.save(img_file, "PNG")
            overlay_entries.append({
                "file": str(img_file),
                "start": w["start"],
                "end": w["end"]
            })
            frame_idx += 1

    # Chunk overlays into batches to keep FFmpeg command clean and fast
    # Write overlay inputs
    filter_graph = ""
    for idx, item in enumerate(overlay_entries):
        input_args.extend(["-i", item["file"]])
        in_tag = f"[{idx + 1}:v]"
        out_tag = f"[v{idx + 1}]"
        enable_str = f"between(t,{item['start']:.2f},{item['end']:.2f})"
        filter_graph += f"{current_stream}{in_tag}overlay=0:0:enable='{enable_str}'{out_tag};"
        current_stream = out_tag

    # Remove trailing semicolon
    filter_graph = filter_graph.rstrip(";")

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_graph,
        "-map", current_stream,
        "-map", "0:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "copy",
        output_path
    ]
    subprocess.run(cmd, check=True)
