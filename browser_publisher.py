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
YT_SESSION_PATH = SESSIONS_DIR / "youtube_state.json"
IG_SESSION_PATH = SESSIONS_DIR / "instagram_state.json"

def get_browser_accounts_status() -> Dict[str, Any]:
    """Checks whether valid saved session cookies exist for YT and IG."""
    yt_connected = False
    yt_name = None
    if YT_SESSION_PATH.exists():
        try:
            with open(YT_SESSION_PATH, "r") as f:
                data = json.load(f)
                cookies = data.get("cookies", [])
                # Check for YouTube login auth cookies
                if any(c.get("name") in ["SSID", "SID", "LOGIN_INFO"] for c in cookies):
                    yt_connected = True
                    yt_name = data.get("account_name", "YouTube Channel (Browser)")
        except Exception:
            yt_connected = False

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
    Opens an interactive Google Chrome window for the user to sign in manually.
    Once logged in, it extracts the cookies and saves the session state.
    """
    with sync_playwright() as p:
        # Launch visible browser for interactive sign in
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(viewport=None)
        page = context.new_page()

        if platform == "youtube":
            print("Navigating to YouTube Studio...")
            page.goto("https://studio.youtube.com")
            # Wait until user reaches Studio dashboard or channel switcher
            try:
                # Poll until URL has studio.youtube.com/channel or user finishes login
                for _ in range(120): # up to 4 minutes
                    time.sleep(2)
                    if "studio.youtube.com/channel" in page.url or "studio.youtube.com/video" in page.url:
                        break
                
                # Fetch channel name if visible
                name = "YouTube Channel"
                try:
                    title_el = page.query_selector("#channel-title, #entity-name")
                    if title_el:
                        name = title_el.inner_text().strip()
                except Exception:
                    pass

                state = context.storage_state()
                state["account_name"] = name
                with open(YT_SESSION_PATH, "w") as f:
                    json.dump(state, f, indent=2)
                print(f"YouTube session saved successfully for: {name}")
            finally:
                browser.close()

        elif platform == "instagram":
            print("Navigating to Instagram...")
            page.goto("https://www.instagram.com")
            try:
                for _ in range(120):
                    time.sleep(2)
                    # When logged in, URL is instagram.com and nav icons appear
                    if page.query_selector("svg[aria-label='Home'], svg[aria-label='New post']"):
                        break
                
                name = "Instagram Account"
                state = context.storage_state()
                state["account_name"] = name
                with open(IG_SESSION_PATH, "w") as f:
                    json.dump(state, f, indent=2)
                print("Instagram session saved successfully!")
            finally:
                browser.close()

def upload_youtube_browser(video_path: str, title: str, description: str = "") -> Dict[str, Any]:
    """Uploads vertical Short via YouTube Studio using saved browser session."""
    if not YT_SESSION_PATH.exists():
        raise RuntimeError("No saved YouTube session. Please click 'Login with Browser' in Connected Accounts.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(storage_state=str(YT_SESSION_PATH))
        page = context.new_page()

        print(f"[Browser] Navigating to YouTube Studio for upload...")
        page.goto("https://studio.youtube.com", timeout=45000)
        time.sleep(4)

        # 1. Click CREATE button
        page.wait_for_selector("#create-icon, ytcp-button#create-icon, #upload-button", timeout=15000)
        create_btn = page.query_selector("#create-icon, ytcp-button#create-icon, #upload-button")
        create_btn.click()
        time.sleep(1)

        # 2. Click Upload Videos item if dropdown opened
        upload_item = page.query_selector("tp-yt-paper-item#text-item-0, #text-item-0")
        if upload_item:
            upload_item.click()
            time.sleep(1)

        # 3. File Input
        file_input = page.wait_for_selector("input[type='file']", timeout=15000)
        file_input.set_input_files(str(video_path))
        print("[Browser] Video file selected...")
        time.sleep(6)

        # 4. Set Title
        short_title = title if "#Shorts" in title else f"{title} #Shorts"
        title_box = page.query_selector("#textbox[aria-label*='title'], #textbox[contenteditable='true']")
        if title_box:
            title_box.click()
            page.keyboard.press("Meta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(short_title[:100])

        # 5. Set 'Not Made for Kids'
        page.wait_for_selector("tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS'], [name='VIDEO_MADE_FOR_KIDS_NOT_MFK']", timeout=10000)
        kids_radio = page.query_selector("tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS'], [name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
        if kids_radio:
            kids_radio.click()

        # 6. Click NEXT through steps (Video elements, Checks, Visibility)
        for step in range(3):
            time.sleep(2)
            next_btn = page.query_selector("#next-button")
            if next_btn:
                next_btn.click()

        time.sleep(2)
        # 7. Select Public
        public_radio = page.query_selector("tp-yt-paper-radio-button[name='PUBLIC']")
        if public_radio:
            public_radio.click()

        # 8. Hit Publish / Done
        done_btn = page.wait_for_selector("#done-button", timeout=10000)
        done_btn.click()
        print("[Browser] Clicked Publish/Done button!")
        time.sleep(5)

        # Try to capture the short link
        video_url = "https://youtube.com"
        link_el = page.query_selector("a.ytcp-video-info, a[href*='youtu.be']")
        if link_el:
            video_url = link_el.get_attribute("href")

        browser.close()
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
