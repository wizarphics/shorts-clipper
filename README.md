# AI Shorts Clipper 🎬

Automatically transforms long-form videos (YouTube URLs or local MP4s) into viral 9:16 vertical shorts optimized for YouTube Shorts, TikTok, and Instagram Reels.

## How It Works
1. **Download / Load**: Fetches video directly via `yt-dlp` or takes a local MP4.
2. **Local Transcription**: High-speed transcription using `faster-whisper` directly on your Mac CPU with word-level timestamps.
3. **Virality & Hook Detection**: Gemini evaluates transcript semantics to detect the strongest hooks, emotional climaxes, and standalone highlights.
4. **Smart 9:16 Vertical Cropping**: Centers and crops the 16:9 widescreen video into a crisp 1080x1920 portrait format.

---

## Setup

1. **Activate Virtual Environment**:
   ```bash
   cd /Applications/XAMPP/xamppfiles/htdocs/shorts-clipper
   source venv/bin/activate
   ```

2. **Configure API Key**:
   Add your Gemini API key in `.env`:
   ```bash
   GEMINI_API_KEY="your-gemini-api-key-here"
   ```
   *(Get a free API key at [Google AI Studio](https://aistudio.google.com/))*

---

## Usage

### Process a YouTube Video:
```bash
./venv/bin/python clip.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Process a Local MP4 File:
```bash
./venv/bin/python clip.py /path/to/video.mp4
```

### Options:
- `--num-clips 5`: Extract 5 viral clips (default: 3)
- `--model small`: Whisper model size (`tiny`, `base`, `small`, `medium`)
- `--no-crop`: Keep original aspect ratio instead of cropping to 9:16 vertical
- `--out-dir my_shorts`: Custom folder for exported clips (default: `output/`)
