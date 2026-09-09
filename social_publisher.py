"""
Full Social Suite Auto-Poster
Supports:
1. YouTube Shorts (YouTube Data API v3 OAuth)
2. TikTok (TikTok Content Posting API v2)
3. Instagram Reels (Meta Graph API)
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# ==========================================
# 1. YOUTUBE SHORTS UPLOADER
# ==========================================
def get_youtube_service():
    """Authenticates and returns an authorized YouTube Data API service."""
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None

    token_path = Path("youtube_token.json")
    client_secret_path = Path("client_secret.json")

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if not client_secret_path.exists():
            raise FileNotFoundError(
                "Missing 'client_secret.json'. Download OAuth credentials from Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
        creds = flow.run_local_server(port=8080)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)

def upload_youtube_short(video_path: str, title: str, description: str = "", tags: list = None, privacy: str = "public") -> Dict[str, Any]:
    """Uploads vertical video directly as a YouTube Short."""
    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_service()

    # Append #Shorts to title and description for automatic algorithm classification
    short_title = title if "#Shorts" in title else f"{title} #Shorts"
    short_desc = description + "\n\n#Shorts #Viral #Trending"

    body = {
        "snippet": {
            "title": short_title[:100],
            "description": short_desc,
            "tags": (tags or []) + ["Shorts", "Viral", "Reels"],
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=1024 * 1024 * 5, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response.get("id")
    return {
        "platform": "YouTube",
        "video_id": video_id,
        "url": f"https://youtube.com/shorts/{video_id}",
        "status": "success"
    }


# ==========================================
# 2. TIKTOK CONTENT POSTING API
# ==========================================
def upload_tiktok_video(video_path: str, title: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Publishes video to TikTok using the official Content Posting API v2.
    https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
    """
    token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise ValueError("Missing TIKTOK_ACCESS_TOKEN in environment or .env")

    video_size = os.path.getsize(video_path)

    # 1. Initialize upload
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "post_info": {
            "title": title[:150],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1
        }
    }

    init_res = requests.post(init_url, json=payload, headers=headers).json()
    if "error" in init_res and init_res["error"].get("code") != "ok":
        raise RuntimeError(f"TikTok Init Error: {init_res['error']}")

    upload_url = init_res["data"]["upload_url"]
    publish_id = init_res["data"]["publish_id"]

    # 2. Upload video binary
    with open(video_path, "rb") as f:
        video_data = f.read()

    upload_headers = {
        "Content-Type": "video/mp4",
        "Content-Range": f"bytes 0-{video_size - 1}/{video_size}"
    }
    put_res = requests.put(upload_url, data=video_data, headers=upload_headers)
    if put_res.status_code not in (200, 201):
        raise RuntimeError(f"TikTok binary upload failed: HTTP {put_res.status_code}")

    return {
        "platform": "TikTok",
        "publish_id": publish_id,
        "status": "success"
    }


# ==========================================
# 3. INSTAGRAM REELS (META GRAPH API)
# ==========================================
def upload_instagram_reel(video_url: str, caption: str, account_id: Optional[str] = None, access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Publishes Reels using Meta Graph API.
    Note: Instagram requires a public video URL to ingest the media.
    """
    ig_account_id = account_id or os.getenv("INSTAGRAM_ACCOUNT_ID")
    token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN")

    if not ig_account_id or not token:
        raise ValueError("Missing INSTAGRAM_ACCOUNT_ID or INSTAGRAM_ACCESS_TOKEN in environment or .env")

    # 1. Create Media Container
    container_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token
    }
    c_res = requests.post(container_url, data=payload).json()
    if "id" not in c_res:
        raise RuntimeError(f"Instagram Container Error: {c_res}")

    creation_id = c_res["id"]

    # 2. Publish Container
    publish_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": token
    }
    p_res = requests.post(publish_url, data=pub_payload).json()
    if "id" not in p_res:
        raise RuntimeError(f"Instagram Publish Error: {p_res}")

    return {
        "platform": "Instagram",
        "media_id": p_res["id"],
        "status": "success"
    }
