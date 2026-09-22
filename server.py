import os
import sys
import json
import shutil
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import cv2
from dotenv import load_dotenv

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from subtitles import build_caption_groups, burn_subtitles
from video_enhancer import enhance_video_audio
from viral_finder import find_viral_candidates
from clip import download_video, extract_audio, transcribe_audio, detect_viral_clips, cut_and_format_clip, get_video_cache_id

load_dotenv()

# Setup paths
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / ".cache_clips"
STATIC_DIR = BASE_DIR / "static"

OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI Shorts Clipper Web UI")

# Ensure static and output are mounted
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# Job tracking state
JOB_STATE = {
    "status": "idle",       # idle, downloading, transcribing, analyzing, rendering, done, error
    "progress": 0,          # 0 - 100
    "step_message": "",
    "clips": [],
    "error": None
}

class ClipRequest(BaseModel):
    url: str
    num_clips: int = 3
    model_size: str = "base"
    burn_captions: bool = True
    crop_9_16: bool = True
    add_music: bool = True
    music_track: str = "tension_bed"
    add_whoosh: bool = True
    add_banner: bool = True
    smart_face_tracking: bool = True
    target_duration: str = "short"  # 'short' (20-60s) or 'tiktok_long' (60-120s) or 'custom'
    min_sec: int = 25
    max_sec: int = 60
    cookies_browser: Optional[str] = None

def update_state(status: str, progress: int, message: str, error: Optional[str] = None):
    JOB_STATE["status"] = status
    JOB_STATE["progress"] = progress
    JOB_STATE["step_message"] = message
    if error:
        JOB_STATE["error"] = error

def process_pipeline(req: ClipRequest):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            update_state("error", 0, "GEMINI_API_KEY is not set in .env", "Missing API key")
            return

        # Determine min_sec / max_sec based on target_duration
        if req.target_duration == "tiktok_long":
            clip_min = 61   # Must be > 60s for TikTok Creator Rewards
            clip_max = 120
        elif req.target_duration == "short":
            clip_min = 25
            clip_max = 59
        else:
            clip_min = req.min_sec
            clip_max = req.max_sec

        # 1. Download
        update_state("downloading", 15, "Downloading video from source...")
        video_path = download_video(req.url, str(CACHE_DIR), cookies_browser=req.cookies_browser)
        vid_cache_dir = Path(video_path).parent

        # 2. Extract Audio
        update_state("processing", 25, "Extracting audio track for transcription...")
        audio_path = extract_audio(video_path, str(vid_cache_dir))

        # 3. Transcribe
        transcript_file = vid_cache_dir / "transcript.json"
        if transcript_file.exists():
            update_state("transcribing", 50, "Reusing cached Whisper transcript for this video...")
            with open(transcript_file, "r") as f:
                segments = json.load(f)
            full_text = "\n".join([f"[{s['start']:.1f}s - {s['end']:.1f}s]: {s['text']}" for s in segments])
        else:
            update_state("transcribing", 40, f"Transcribing audio with Faster-Whisper ({req.model_size})...")
            segments, full_text = transcribe_audio(audio_path, model_size=req.model_size)
            with open(transcript_file, "w") as f:
                json.dump(segments, f, indent=2)

        # 4. Detect Viral Clips with Gemini
        update_state("analyzing", 65, f"Gemini is analyzing viral hooks ({clip_min}s - {clip_max}s)...")
        detected = detect_viral_clips(full_text, api_key, num_clips=req.num_clips, min_sec=clip_min, max_sec=clip_max)
        if not detected:
            update_state("error", 0, "No viral clips were detected or Gemini failed to respond.", "AI Analysis failed")
            return

        # 5. Create Project Directory for this Generation
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_cache_id = get_video_cache_id(req.url)
        proj_name = f"{timestamp_str}_{video_cache_id}"

        project_dir = OUTPUT_DIR / proj_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # 6. Render Clips into Project Directory
        rendered_clips = []
        total_clips = len(detected)

        for idx, clip in enumerate(detected, 1):
            clip_prog = int(65 + (idx / total_clips) * 30)
            update_state("rendering", clip_prog, f"Rendering clip {idx}/{total_clips}: {clip.get('title', 'Clip')}...")

            safe_title = "".join(c for c in clip.get('title', f'clip_{idx}') if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
            final_filename = f"{idx:02d}_{safe_title}.mp4"
            final_path = project_dir / final_filename
            rel_path = f"{proj_name}/{final_filename}"
            raw_cut_path = final_path if not req.burn_captions else vid_cache_dir / f"raw_cut_{idx}.mp4"

            cut_and_format_clip(
                video_path,
                start_time=clip["start_time"],
                end_time=clip["end_time"],
                output_path=str(raw_cut_path),
                crop_9_16=req.crop_9_16,
                smart_tracking=req.smart_face_tracking
            )

            subtitled_path = vid_cache_dir / f"sub_{idx}.mp4" if (req.add_music or req.add_banner) else final_path

            if req.burn_captions:
                update_state("rendering", clip_prog, f"Burning animated dynamic subtitles for clip {idx}/{total_clips}...")
                groups = build_caption_groups(segments, clip["start_time"], clip["end_time"], words_per_group=3)
                burn_subtitles(str(raw_cut_path), groups, str(subtitled_path))
                if raw_cut_path.exists():
                    os.remove(raw_cut_path)
            else:
                subtitled_path = raw_cut_path

            # Video & Audio Enhancement (Music Bed + Whoosh SFX + Hook Header)
            if req.add_music or req.add_banner or req.add_whoosh:
                update_state("rendering", clip_prog, f"Adding background audio and hook styling for clip {idx}/{total_clips}...")
                banner_text = clip.get("title", "MUST WATCH") if req.add_banner else None
                enhance_video_audio(
                    video_path=str(subtitled_path),
                    output_path=str(final_path),
                    title_banner=banner_text,
                    music_track=req.music_track if req.add_music else "none",
                    add_whoosh=req.add_whoosh,
                    music_volume=0.08 if req.add_music else 0.0
                )
                if subtitled_path.exists() and subtitled_path != final_path:
                    os.remove(subtitled_path)

            rendered_clips.append({
                "title": clip.get("title", f"Clip {idx}"),
                "duration": round(clip["end_time"] - clip["start_time"], 1),
                "score": clip.get("virality_score", 9.0),
                "hook": clip.get("hook_reason", ""),
                "project": proj_name,
                "rel_path": rel_path,
                "filename": final_filename,
                "url": f"/output/{rel_path}"
            })

        # Save metadata inside project folder
        with open(project_dir / "meta.json", "w") as f:
            json.dump({
                "source": req.url,
                "created_at": datetime.now().isoformat(),
                "clips": rendered_clips
            }, f, indent=2)

        JOB_STATE["clips"] = rendered_clips
        update_state("done", 100, f"Successfully created {len(rendered_clips)} viral shorts in project '{proj_name}'!")

    except Exception as e:
        update_state("error", 0, f"Pipeline Error: {str(e)}", str(e))

@app.get("/")
def get_index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/status")
def get_status():
    return JSONResponse(JOB_STATE)

@app.get("/api/projects")
def list_projects():
    """Returns all generations grouped by project."""
    projects = []
    
    # 1. Check project subfolders
    for p_dir in sorted(OUTPUT_DIR.glob("*"), reverse=True):
        if p_dir.is_dir():
            meta_file = p_dir / "meta.json"
            meta = {}
            meta_clips_map = {}
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        meta = json.load(f)
                    for mc in meta.get("clips", []):
                        if "filename" in mc:
                            meta_clips_map[mc["filename"]] = mc
                except Exception:
                    pass

            clips = []
            for video_file in sorted(p_dir.glob("*.mp4")):
                mc = meta_clips_map.get(video_file.name, {})
                thumb_file = video_file.with_suffix(".jpg")
                if not thumb_file.exists():
                    try:
                        cap = cv2.VideoCapture(str(video_file))
                        ret, frame = cap.read()
                        if ret:
                            cv2.imwrite(str(thumb_file), frame)
                        cap.release()
                    except Exception:
                        pass

                clips.append({
                    "filename": video_file.name,
                    "title": mc.get("title", video_file.name.replace(".mp4", "").replace("_", " ")),
                    "hook": mc.get("hook", ""),
                    "score": mc.get("score", 9.0),
                    "duration": mc.get("duration", None),
                    "rel_path": f"{p_dir.name}/{video_file.name}",
                    "url": f"/output/{p_dir.name}/{video_file.name}",
                    "thumb_url": f"/output/{p_dir.name}/{thumb_file.name}" if thumb_file.exists() else None,
                    "size_mb": round(video_file.stat().st_size / (1024 * 1024), 1)
                })

            # Generate a cleaner, human-friendly project name if raw timestamp
            proj_title = meta.get("title", "")
            if not proj_title and meta.get("clips") and len(meta["clips"]) > 0:
                first_clip_title = meta["clips"][0].get("title", "")
                if first_clip_title:
                    proj_title = first_clip_title

            if not proj_title:
                proj_title = p_dir.name.replace("_", " ")

            projects.append({
                "id": p_dir.name,
                "name": proj_title,
                "created_at": meta.get("created_at", datetime.fromtimestamp(p_dir.stat().st_mtime).isoformat()),
                "source": meta.get("source", ""),
                "clips": clips
            })

    # 2. Check legacy root output clips (if any)
    root_clips = []
    for f in sorted(OUTPUT_DIR.glob("*.mp4")):
        root_clips.append({
            "filename": f.name,
            "rel_path": f.name,
            "url": f"/output/{f.name}",
            "size_mb": round(f.stat().st_size / (1024 * 1024), 1)
        })
    if root_clips:
        projects.insert(0, {
            "id": "root_clips",
            "name": "General Library",
            "created_at": datetime.now().isoformat(),
            "source": "",
            "clips": root_clips
        })

    return JSONResponse({"projects": projects})

@app.get("/api/discover")
def discover_viral_videos(niche: str = "podcast debate hot take", count: int = 6):
    """Finds high-performing videos on YouTube ready to be clipped."""
    try:
        videos = find_viral_candidates(niche=niche, total=count)
        return JSONResponse({"videos": videos})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/clips")
def list_clips():
    clips = []
    for p in sorted(OUTPUT_DIR.rglob("*.mp4"), reverse=True):
        rel = p.relative_to(OUTPUT_DIR)
        clips.append({
            "filename": p.name,
            "rel_path": str(rel),
            "url": f"/output/{rel}",
            "size_mb": round(p.stat().st_size / (1024 * 1024), 1)
        })
    return JSONResponse({"clips": clips})

@app.delete("/api/clip")
def delete_clip(rel_path: str):
    """Deletes a single clip."""
    clip_file = OUTPUT_DIR / rel_path
    if not clip_file.exists():
        raise HTTPException(status_code=404, detail="Clip not found.")
    
    # Secure check against directory traversal
    if OUTPUT_DIR not in clip_file.resolve().parents:
        raise HTTPException(status_code=403, detail="Invalid file path.")
    
    os.remove(clip_file)
    return JSONResponse({"status": "deleted", "path": rel_path})

@app.delete("/api/project")
def delete_project(project_id: str):
    """Deletes an entire project generation folder."""
    target_dir = OUTPUT_DIR / project_id
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project folder not found.")
    
    if OUTPUT_DIR not in target_dir.resolve().parents:
        raise HTTPException(status_code=403, detail="Invalid directory path.")
    
    shutil.rmtree(target_dir)
    return JSONResponse({"status": "deleted", "project": project_id})

@app.post("/api/generate")
def start_generation(req: ClipRequest, background_tasks: BackgroundTasks):
    if JOB_STATE["status"] in ["downloading", "transcribing", "analyzing", "rendering"]:
        raise HTTPException(status_code=400, detail="A clipping job is already running.")
    
    JOB_STATE["clips"] = []
    JOB_STATE["error"] = None
    update_state("starting", 5, "Initializing video processing pipeline...")
    background_tasks.add_task(process_pipeline, req)
    return JSONResponse({"status": "started"})


# ==========================================
# CONNECTED ACCOUNTS & SOCIAL HUB
# ==========================================
class SaveClientSecretRequest(BaseModel):
    client_secret_json: str

class SaveInstagramRequest(BaseModel):
    account_id: str
    access_token: str

class SaveTikTokRequest(BaseModel):
    access_token: str


@app.get("/api/accounts/browser/status")
def get_browser_status():
    from browser_publisher import get_browser_accounts_status
    return JSONResponse(get_browser_accounts_status())

@app.post("/api/accounts/browser/login/{platform}")
def start_browser_login(platform: str, background_tasks: BackgroundTasks):
    from browser_publisher import launch_login_browser
    background_tasks.add_task(launch_login_browser, platform)
    return JSONResponse({"status": "launched", "message": f"Opened Google Chrome for {platform} login."})

@app.delete("/api/accounts/browser/disconnect/{platform}")
def disconnect_browser_session(platform: str):
    from browser_publisher import disconnect_browser_account
    disconnect_browser_account(platform)
    return JSONResponse({"status": "disconnected"})

@app.get("/api/accounts/status")
def get_accounts_status():
    from social_publisher import get_social_accounts_status
    return JSONResponse(get_social_accounts_status())

@app.post("/api/accounts/youtube/save-secret")
def save_youtube_secret(req: SaveClientSecretRequest):
    try:
        parsed = json.loads(req.client_secret_json)
        # Check standard OAuth client secret keys
        if "installed" not in parsed and "web" not in parsed:
            raise ValueError("Invalid client_secret.json format: Must contain 'installed' or 'web' root key.")
        with open("client_secret.json", "w") as f:
            json.dump(parsed, f, indent=2)
        return JSONResponse({"status": "saved", "message": "client_secret.json saved successfully."})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/accounts/youtube/auth-start")
def start_youtube_auth(background_tasks: BackgroundTasks):
    client_secret_path = Path("client_secret.json")
    if not client_secret_path.exists():
        raise HTTPException(status_code=400, detail="Missing client_secret.json. Please paste your OAuth JSON first.")
    
    def run_flow():
        try:
            from social_publisher import get_youtube_service
            get_youtube_service()
        except Exception as e:
            print(f"Auth error: {e}")

    background_tasks.add_task(run_flow)
    return JSONResponse({"status": "started", "message": "OAuth browser prompt triggered on local machine."})

@app.delete("/api/accounts/youtube/disconnect")
def disconnect_youtube():
    token_path = Path("youtube_token.json")
    if token_path.exists():
        os.remove(token_path)
    return JSONResponse({"status": "disconnected"})

def update_env_variable(key: str, value: str):
    env_path = BASE_DIR / ".env"
    lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()
    
    key_found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            key_found = True
        else:
            new_lines.append(line)
    if not key_found:
        new_lines.append(f"{key}={value}\n")
    
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    os.environ[key] = value

@app.post("/api/accounts/instagram/save")
def save_instagram_credentials(req: SaveInstagramRequest):
    try:
        update_env_variable("INSTAGRAM_ACCOUNT_ID", req.account_id.strip())
        update_env_variable("INSTAGRAM_ACCESS_TOKEN", req.access_token.strip())
        return JSONResponse({"status": "saved", "message": "Instagram credentials saved."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/accounts/instagram/disconnect")
def disconnect_instagram():
    update_env_variable("INSTAGRAM_ACCOUNT_ID", "")
    update_env_variable("INSTAGRAM_ACCESS_TOKEN", "")
    return JSONResponse({"status": "disconnected"})

@app.post("/api/accounts/tiktok/save")
def save_tiktok_credentials(req: SaveTikTokRequest):
    try:
        update_env_variable("TIKTOK_ACCESS_TOKEN", req.access_token.strip())
        return JSONResponse({"status": "saved", "message": "TikTok token saved."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/accounts/tiktok/disconnect")
def disconnect_tiktok():
    update_env_variable("TIKTOK_ACCESS_TOKEN", "")
    return JSONResponse({"status": "disconnected"})

class PostRequest(BaseModel):
    rel_path: str
    title: str
    description: Optional[str] = ""
    platform: str # 'youtube', 'tiktok', 'instagram'

@app.post("/api/post")
def post_clip(req: PostRequest):
    clip_path = OUTPUT_DIR / req.rel_path
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found.")

    try:
        from social_publisher import upload_youtube_short, upload_tiktok_video, upload_instagram_reel

        if req.platform.lower() == "youtube":
            # Check if browser session exists first
            from pathlib import Path
            if (Path(".sessions/youtube_state.json")).exists() and not (Path("client_secret.json")).exists():
                from browser_publisher import upload_youtube_browser
                res = upload_youtube_browser(
                    video_path=str(clip_path),
                    title=req.title,
                    description=req.description or req.title
                )
                return JSONResponse(res)

            res = upload_youtube_short(
                video_path=str(clip_path),
                title=req.title,
                description=req.description or req.title
            )
            return JSONResponse(res)

        elif req.platform.lower() == "tiktok":
            res = upload_tiktok_video(
                video_path=str(clip_path),
                title=req.title
            )
            return JSONResponse(res)

        elif req.platform.lower() == "instagram":
            # Host relative video URL
            res = upload_instagram_reel(
                video_url=f"http://localhost:8000/output/{req.rel_path}",
                caption=f"{req.title}\n\n{req.description or ''}"
            )
            return JSONResponse(res)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported platform: {req.platform}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
