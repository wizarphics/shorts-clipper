"""
AI Viral Video Finder
Combines Gemini AI trending search ideas with YouTube search scraping
to find high-potential viral long-form videos ready to be clipped.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Ensure PATH has yt-dlp
venv_bin = str(Path(sys.executable).parent.resolve())
extra_paths = [venv_bin, "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]
current_path = os.environ.get("PATH", "")
os.environ["PATH"] = ":".join(p for p in extra_paths if p not in current_path.split(":")) + (f":{current_path}" if current_path else "")

def ask_gemini_viral_topics(niche: str = "podcasts & controversial debates") -> List[str]:
    """Asks Gemini for high-performing, high-curiosity search queries."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return [f"{niche} popular interview", f"{niche} viral moments", f"{niche} debate"]

    client = genai.Client(api_key=api_key)
    prompt = f"""
You are a viral social media scout. What are 5 high-converting YouTube search terms to find long-form videos (podcasts, interviews, confrontations, debates) that yield the most viral TikTok and YouTube Shorts clips in the niche: '{niche}'?

Focus on search phrases likely to uncover videos with huge drama, controversial arguments, hot takes, or gripping personal stories.

Respond ONLY with a JSON array of 5 search strings:
["query 1", "query 2", "query 3", "query 4", "query 5"]
"""

    models_to_try = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
    for model_name in models_to_try:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            if res and res.text:
                queries = json.loads(res.text)
                if isinstance(queries, list) and len(queries) > 0:
                    return queries[:5]
        except Exception:
            continue

    return [f"{niche} heated debate", f"{niche} podcast shock moments", f"{niche} interview confrontation"]

def search_youtube_videos(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches YouTube using yt-dlp flat-playlist extraction."""
    search_term = f"ytsearch{limit}:{query}"
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        "--playlist-end", str(limit),
        search_term
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return []

    videos = []
    for line in res.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            data = json.loads(line)
            duration_sec = data.get("duration") or 0
            # Prefer videos longer than 3 minutes so there is substance to clip
            videos.append({
                "id": data.get("id"),
                "title": data.get("title"),
                "url": f"https://www.youtube.com/watch?v={data.get('id')}",
                "uploader": data.get("uploader") or data.get("channel"),
                "view_count": data.get("view_count") or 0,
                "duration_min": round(duration_sec / 60, 1) if duration_sec else "N/A",
                "thumbnail": data.get("thumbnail") or f"https://i.ytimg.com/vi/{data.get('id')}/hqdefault.jpg"
            })
        except Exception:
            continue

    return videos

def find_viral_candidates(niche: str = "podcasts & interviews", total: int = 6) -> List[Dict[str, Any]]:
    """Discovers viral video candidates across top AI search queries."""
    queries = ask_gemini_viral_topics(niche)
    all_videos = []
    seen_ids = set()

    # Search each suggested topic for top 2-3 videos
    for q in queries:
        vids = search_youtube_videos(q, limit=3)
        for v in vids:
            if v["id"] and v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
            if len(all_videos) >= total:
                break
        if len(all_videos) >= total:
            break

    return all_videos

if __name__ == "__main__":
    results = find_viral_candidates("dating debate and relationship podcast", total=4)
    for r in results:
        print(f"[{r['view_count']} views] {r['title']} -> {r['url']}")
