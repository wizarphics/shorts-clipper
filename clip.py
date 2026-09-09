#!/usr/bin/env python3
"""
AI Shorts Clipper
Automatically extracts viral shorts (9:16 vertical video) from YouTube videos or local MP4 files.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from subtitles import build_caption_groups, burn_subtitles

# Load environment variables
load_dotenv()

# Ensure virtualenv bin directory and Homebrew / standard tool paths are in PATH
venv_bin = str(Path(sys.executable).parent.resolve())
extra_paths = [venv_bin, "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]
current_path = os.environ.get("PATH", "")
os.environ["PATH"] = ":".join(p for p in extra_paths if p not in current_path.split(":")) + (f":{current_path}" if current_path else "")

def run_command(cmd, desc=""):
    if desc:
        print(f"[*] {desc}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] Error: {res.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(cmd) if isinstance(cmd, list) else cmd}\n{res.stderr}")
    return res.stdout

def get_video_cache_id(url_or_path: str) -> str:
    """Generates a stable, unique directory ID for a video source."""
    import re
    import hashlib
    cleaned = url_or_path.replace(r"\?", "?").replace(r"\=", "=").replace(r"\&", "&").strip()
    m = re.search(r'(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})', cleaned)
    if m:
        return f"yt_{m.group(1)}"
    if os.path.exists(cleaned):
        return f"local_{Path(cleaned).stem}"
    h = hashlib.md5(cleaned.encode("utf-8")).hexdigest()[:10]
    return f"vid_{h}"

def download_video(url_or_path, work_dir, cookies_browser=None):
    """Downloads video using yt-dlp if URL, or copies/links if local file."""
    # Clean any accidental shell-escaped characters (like \? or \=)
    url_or_path = url_or_path.replace(r"\?", "?").replace(r"\=", "=").replace(r"\&", "&").strip()
    if os.path.exists(url_or_path):
        print(f"[*] Using local video: {url_or_path}")
        return os.path.abspath(url_or_path)

    # Isolated cache directory per video ID
    cache_id = get_video_cache_id(url_or_path)
    vid_work_dir = Path(work_dir) / cache_id
    vid_work_dir.mkdir(parents=True, exist_ok=True)

    # Check if already downloaded in this specific video cache
    cached_candidates = list(vid_work_dir.glob("input_video.*"))
    if cached_candidates:
        print(f"[*] Reusing existing cached video for {cache_id}: {cached_candidates[0]}")
        return str(cached_candidates[0])

    print(f"[*] Downloading video from: {url_or_path}")
    output_template = str(vid_work_dir / "input_video.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template
    ]
    if cookies_browser:
        cmd.extend(["--cookies-from-browser", cookies_browser])
    cmd.append(url_or_path)
    run_command(cmd, desc=f"Downloading with yt-dlp ({cache_id})")
    video_path = vid_work_dir / "input_video.mp4"
    if not video_path.exists():
        candidates = list(vid_work_dir.glob("input_video.*"))
        if candidates:
            return str(candidates[0])
        raise FileNotFoundError("Downloaded video file not found.")
    return str(video_path)

def extract_audio(video_path, work_dir):
    """Extracts 16kHz mono WAV for Whisper."""
    parent_dir = Path(video_path).parent if Path(video_path).is_file() else Path(work_dir)
    audio_path = parent_dir / "audio.wav"
    if audio_path.exists():
        print(f"[*] Reusing existing audio track: {audio_path}")
        return str(audio_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path)
    ]
    run_command(cmd, desc="Extracting audio track for transcription")
    return str(audio_path)

def transcribe_audio(audio_path, model_size="base"):
    """Transcribes audio using faster-whisper with word timestamps."""
    from faster_whisper import WhisperModel
    print(f"[*] Loading Faster-Whisper model ({model_size}) on CPU...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    print("[*] Transcribing audio with exact timestamps...")
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
    
    transcript_segments = []
    full_text_list = []
    
    for segment in segments:
        words = []
        if segment.words:
            for w in segment.words:
                words.append({
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "word": w.word.strip()
                })
        
        transcript_segments.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": words
        })
        full_text_list.append(f"[{segment.start:.1f}s - {segment.end:.1f}s]: {segment.text.strip()}")
    
    return transcript_segments, "\n".join(full_text_list)

def detect_viral_clips(transcript_summary, api_key, num_clips=3, min_sec=20, max_sec=60):
    """Uses Gemini to identify the most viral, hook-driven clips."""
    from google import genai
    from google.genai import types

    print("[*] Asking Gemini to identify viral hooks and moments...")
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are a viral social media content editor (specialized in YouTube Shorts, TikTok, and Instagram Reels).
Review the video transcript below with timestamps and identify the top {num_clips} most engaging, high-retention segments.

Selection Criteria:
1. Strong immediate Hook (first 3-5 seconds grab attention or spark curiosity).
2. Emotional peak, contrarian insight, compelling story, or punchline.
3. Standalone completeness (makes sense without needing the rest of the video).
4. Duration: Between {min_sec} and {max_sec} seconds long.

Video Transcript:
{transcript_summary}

Respond ONLY with valid JSON in the following format:
{{
  "clips": [
    {{
      "title": "Short catchy title",
      "start_time": 12.5,
      "end_time": 45.0,
      "hook_reason": "Why this hook grabs the viewer immediately",
      "virality_score": 9.5
    }}
  ]
}}
"""

    models_to_try = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest", "gemini-3-flash-preview"]
    response = None
    for model_name in models_to_try:
        try:
            print(f"[*] Analyzing with {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            if response and response.text:
                break
        except Exception as e:
            print(f"[!] {model_name} unavailable ({str(e)[:80]}), trying next model...")
            continue

    if not response or not response.text:
        print("[!] All Gemini models were unavailable or failed to respond.")
        return []

    try:
        data = json.loads(response.text)
        return data.get("clips", [])
    except Exception as e:
        print(f"[!] Warning: failed to parse Gemini response as JSON: {e}")
        print(response.text)
        return []

def cut_and_format_clip(video_path, start_time, end_time, output_path, crop_9_16=True, smart_tracking=True):
    """Cuts segment and optionally crops to vertical 9:16 (1080x1920) with AI face tracking."""
    duration = end_time - start_time
    if crop_9_16:
        if smart_tracking:
            try:
                from face_tracker import compute_smart_crop_filter
                vf_filter = compute_smart_crop_filter(video_path, start_time, end_time, out_w=1080, out_h=1920)
            except Exception as e:
                print(f"[!] Face tracking error fallback: {e}")
                vf_filter = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
        else:
            # Standard center crop
            vf_filter = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
    else:
        vf_filter = "scale=1080:-2"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]
    run_command(cmd, desc=f"Rendering clip: {os.path.basename(output_path)}")

def main():
    parser = argparse.ArgumentParser(description="AI Shorts Clipper: Turn long videos into viral 9:16 vertical clips.")
    parser.add_argument("source", help="YouTube URL or local video path (.mp4)")
    parser.add_argument("--num-clips", type=int, default=3, help="Number of clips to generate (default: 3)")
    parser.add_argument("--model", type=str, default="base", help="Whisper model size: tiny, base, small, medium (default: base)")
    parser.add_argument("--out-dir", type=str, default="output", help="Directory to save output clips")
    parser.add_argument("--no-crop", action="store_true", help="Do not crop to 9:16 vertical (keep original aspect ratio)")
    parser.add_argument("--no-captions", action="store_true", help="Disable burning dynamic animated subtitles")
    parser.add_argument("--min-sec", type=int, default=25, help="Minimum clip duration in seconds (use 60 for TikTok Creator Rewards)")
    parser.add_argument("--max-sec", type=int, default=60, help="Maximum clip duration in seconds (e.g. 90 or 120)")
    parser.add_argument("--cookies-browser", type=str, default=None, help="Browser to load cookies from for YouTube (e.g. chrome, safari, firefox)")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[!] GEMINI_API_KEY is not set.")
        print("    Please set it in .env or export GEMINI_API_KEY='your-key'")
        sys.exit(1)

    work_dir = Path(".cache_clips")
    work_dir.mkdir(exist_ok=True)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    # 1. Download or locate video
    video_file = download_video(args.source, str(work_dir), cookies_browser=args.cookies_browser)
    
    # 2. Extract Audio & 3. Transcribe with Whisper (or load cache)
    vid_cache_dir = Path(video_file).parent
    audio_file = extract_audio(video_file, str(vid_cache_dir))
    
    transcript_file = vid_cache_dir / "transcript.json"
    if transcript_file.exists():
        print(f"[*] Reusing cached transcript for this video from {transcript_file}...")
        with open(transcript_file, "r") as f:
            segments = json.load(f)
        full_text_list = [f"[{s['start']:.1f}s - {s['end']:.1f}s]: {s['text']}" for s in segments]
        transcript_text = "\n".join(full_text_list)
    else:
        segments, transcript_text = transcribe_audio(audio_file, model_size=args.model)
        with open(transcript_file, "w") as f:
            json.dump(segments, f, indent=2)
        
    # 4. Detect Viral Clips with Gemini
    clips = detect_viral_clips(
        transcript_text,
        api_key,
        num_clips=args.num_clips,
        min_sec=args.min_sec,
        max_sec=args.max_sec
    )
    
    if not clips:
        print("[!] No clips detected or JSON parsing failed.")
        return

    print(f"\n[+] Gemini selected {len(clips)} viral candidate clips:")
    for idx, clip in enumerate(clips, 1):
        print(f"  [{idx}] {clip.get('title')} ({clip.get('start_time')}s - {clip.get('end_time')}s) - Score: {clip.get('virality_score')}/10")
        print(f"      Hook: {clip.get('hook_reason')}")

    # 5. Render Clips
    for idx, clip in enumerate(clips, 1):
        safe_title = "".join(c for c in clip.get('title', f'clip_{idx}') if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        out_filename = out_dir / f"{idx:02d}_{safe_title}.mp4"
        raw_cut_path = str(out_filename) if args.no_captions else str(work_dir / f"raw_cut_{idx}.mp4")

        cut_and_format_clip(
            video_file,
            start_time=clip["start_time"],
            end_time=clip["end_time"],
            output_path=raw_cut_path,
            crop_9_16=not args.no_crop
        )

        if not args.no_captions:
            print(f"[*] Generating animated captions for clip {idx}...")
            groups = build_caption_groups(segments, clip["start_time"], clip["end_time"], words_per_group=3)
            burn_subtitles(raw_cut_path, groups, str(out_filename))
            if os.path.exists(raw_cut_path):
                os.remove(raw_cut_path)

        print(f"[✓] Successfully exported: {out_filename}")

    print(f"\n🎉 Done! All clips saved in: {out_dir.resolve()}")

if __name__ == "__main__":
    main()
