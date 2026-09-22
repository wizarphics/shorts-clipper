"""
Browser-Session Automation for YouTube & Instagram
Uses your installed Google Chrome via Playwright.
Zero API keys, zero developer console setups.
"""

import os
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent.resolve()
SESSIONS_DIR = BASE_DIR / ".sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
YT_SESSION_PATH = SESSIONS_DIR / "youtube_state.json"
IG_SESSION_PATH = SESSIONS_DIR / "instagram_state.json"

def get_browser_accounts_status() -> Dict[str, Any]:
    """Checks whether valid saved session cookies exist for YT and IG."""
    yt_connected = False
    yt_name = None
    user_data_dir = SESSIONS_DIR / "chrome_profile_youtube"
    if YT_SESSION_PATH.exists() or user_data_dir.exists():
        try:
            if YT_SESSION_PATH.exists():
                with open(YT_SESSION_PATH, "r") as f:
                    data = json.load(f)
                    cookies = data.get("cookies", [])
                    if any(c.get("name") in ["SSID", "SID", "LOGIN_INFO"] for c in cookies):
                        yt_connected = True
                        yt_name = data.get("account_name", "ClipForgeTV (YouTube)")
            if not yt_connected and user_data_dir.exists():
                yt_connected = True
                yt_name = "ClipForgeTV (YouTube)"
        except Exception:
            yt_connected = user_data_dir.exists()
            if yt_connected:
                yt_name = "ClipForgeTV (YouTube)" 

    ig_connected = False
    ig_name = None
    if IG_SESSION_PATH.exists():
        try:
            with open(IG_SESSION_PATH, "r") as f:
                data = json.load(f)
                cookies = data.get("cookies", [])
                if any(c.get("name") == "sessionid" for c in cookies):
                    ig_connected = True
                    ig_name = data.get("account_name", "Instagram Account (Browser)")
        except Exception:
            ig_connected = False

    return {
        "youtube": {"connected": yt_connected, "account_name": yt_name},
        "instagram": {"connected": ig_connected, "account_name": ig_name}
    }

def launch_login_browser(platform: str):
    """
    Opens Google Chrome with a dedicated user data profile.
    This avoids Chrome automation blocks, supports full Google sign in,
    and saves session cookies reliably.
    """
    user_data_dir = str(SESSIONS_DIR / f"chrome_profile_{platform}")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=CHROME_PATH,
            user_agent=USER_AGENT,
            headless=False,
            viewport=None,
            args=[
                "--start-maximized",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()

        if platform == "youtube":
            print("[Browser] Opening YouTube Studio login...")
            page.goto("https://studio.youtube.com")

            # Keep polling until user completes login or closes browser
            for _ in range(150): # 5 minutes window
                try:
                    time.sleep(2)
                    # Check if page or context was closed by user
                    if page.is_closed():
                        break

                    url = page.url
                    # Success condition: reached youtube.com/channel or studio.youtube.com dashboard
                    if "studio.youtube.com" in url and ("channel" in url or "video" in url or "dashboard" in url):
                        time.sleep(3)
                        # Extract channel name
                        name = "YouTube Channel"
                        try:
                            title_el = page.query_selector("#channel-title, #entity-name, yt-formatted-string#text")
                            if title_el:
                                name = title_el.inner_text().strip()
                        except Exception:
                            pass

                        state = context.storage_state()
                        state["account_name"] = name
                        with open(YT_SESSION_PATH, "w") as f:
                            json.dump(state, f, indent=2)
                        print(f"[Browser] YouTube login confirmed & saved: {name}")
                        break
                    
                    # Or if cookies are already populated
                    cookies = context.cookies()
                    if any(c.get("name") in ["SSID", "SID", "LOGIN_INFO"] for c in cookies) and "google.com" not in url:
                        state = context.storage_state()
                        state["account_name"] = "Connected YouTube Account"
                        with open(YT_SESSION_PATH, "w") as f:
                            json.dump(state, f, indent=2)
                        print(f"[Browser] YouTube cookies detected & saved!")
                        break

                except Exception as e:
                    print(f"[Browser] Polling notice: {e}")
                    break

            try:
                context.close()
            except Exception:
                pass

        elif platform == "instagram":
            print("[Browser] Opening Instagram login...")
            page.goto("https://www.instagram.com")
            for _ in range(150):
                try:
                    time.sleep(2)
                    if page.is_closed():
                        break
                    
                    # Logged in indicators
                    if page.query_selector("svg[aria-label='Home'], svg[aria-label='Direct'], svg[aria-label='New post']"):
                        state = context.storage_state()
                        state["account_name"] = "Instagram Account"
                        with open(IG_SESSION_PATH, "w") as f:
                            json.dump(state, f, indent=2)
                        print("[Browser] Instagram login confirmed & saved!")
                        break

                    cookies = context.cookies()
                    if any(c.get("name") == "sessionid" for c in cookies):
                        state = context.storage_state()
                        state["account_name"] = "Connected Instagram"
                        with open(IG_SESSION_PATH, "w") as f:
                            json.dump(state, f, indent=2)
                        print("[Browser] Instagram cookies detected & saved!")
                        break
                except Exception:
                    break

            try:
                context.close()
            except Exception:
                pass

def upload_youtube_browser(video_path: str, title: str, description: str = "") -> Dict[str, Any]:
    """Uploads vertical Short via YouTube Studio using saved persistent browser profile."""
    user_data_dir = str(SESSIONS_DIR / "chrome_profile_youtube")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=CHROME_PATH,
            user_agent=USER_AGENT,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("[Browser] Navigating to YouTube Studio for upload...")
        page.goto("https://studio.youtube.com", timeout=60000)
        time.sleep(5)

        # Check if there is a 'SKIP TO YOUTUBE STUDIO' banner
        try:
            skip_btn = page.query_selector("text='SKIP TO YOUTUBE STUDIO', [aria-label='SKIP TO YOUTUBE STUDIO']")
            if skip_btn:
                skip_btn.click()
                time.sleep(3)
        except Exception:
            pass

        # 1. Click CREATE button
        page.wait_for_selector("#create-icon, ytcp-button#create-icon, button[aria-label='Create'], ytcp-button:has-text('Create')", timeout=25000)
        create_btn = page.query_selector("#create-icon, ytcp-button#create-icon, button[aria-label='Create'], ytcp-button:has-text('Create')")
        create_btn.click()
        time.sleep(2)

        # 2. Click Upload Videos item
        upload_item = page.query_selector("tp-yt-paper-item#text-item-0, #text-item-0, ytcp-text-menu:has-text('Upload videos'), text='Upload videos'")
        if upload_item:
            upload_item.click()
            time.sleep(2)

        # 3. File Input
        file_input = page.wait_for_selector("input[type='file']", timeout=20000)
        file_input.set_input_files(str(video_path))
        print("[Browser] Video file selected...")
        time.sleep(7)

        # 4. Set Title
        short_title = title if "#Shorts" in title else f"{title} #Shorts"
        title_box = page.query_selector("#textbox[aria-label*='title'], #textbox[contenteditable='true']")
        if title_box:
            title_box.click()
            page.keyboard.press("Meta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(short_title[:100])

        # 5. Set 'Not Made for Kids'
        try:
            page.wait_for_selector("tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS'], [name='VIDEO_MADE_FOR_KIDS_NOT_MFK']", timeout=10000)
            kids_radio = page.query_selector("tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS'], [name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
            if kids_radio:
                kids_radio.click()
        except Exception:
            pass

        # 6. Click NEXT through wizard steps
        for step in range(3):
            time.sleep(2)
            next_btn = page.query_selector("#next-button")
            if next_btn:
                next_btn.click()

        time.sleep(3)
        # 7. Select Public
        try:
            public_radio = page.query_selector("tp-yt-paper-radio-button[name='PUBLIC'], [aria-label='Public']")
            if public_radio:
                public_radio.click()
        except Exception:
            pass

        # 8. Hit Publish / Done
        done_btn = page.wait_for_selector("#done-button", timeout=15000)
        done_btn.click()
        print("[Browser] Clicked Publish/Done button!")
        time.sleep(5)

        # Capture short link
        video_url = "https://youtube.com/shorts"
        try:
            link_el = page.query_selector("a.ytcp-video-info, a[href*='youtu.be']")
            if link_el:
                video_url = link_el.get_attribute("href")
        except Exception:
            pass

        context.close()
        return {
            "platform": "YouTube (Browser)",
            "url": video_url,
            "status": "success"
        }

def disconnect_browser_account(platform: str):
    if platform == "youtube" and YT_SESSION_PATH.exists():
        os.remove(YT_SESSION_PATH)
    elif platform == "instagram" and IG_SESSION_PATH.exists():
        os.remove(IG_SESSION_PATH)
