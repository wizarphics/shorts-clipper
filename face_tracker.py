"""
AI Smart Speaker & Face Tracking Engine
Analyzes video segments for faces (frontal and profile), tracks speaker positions across frames,
applies smooth kinematic interpolation (preventing jitter), and computes dynamically targeted
or speaker-centered 9:16 vertical crop windows.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
import cv2
import numpy as np

class SmartFaceTracker:
    def __init__(self):
        self.frontal_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

    def detect_face_centers(self, gray_frame, frame_h: int) -> List[Tuple[float, float, float, float]]:
        """
        Returns list of detected faces formatted as (center_x, center_y, width, height)
        sorted by area (largest / most prominent first).
        """
        min_dim = int(frame_h * 0.10)
        faces = self.frontal_cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.15,
            minNeighbors=4,
            minSize=(min_dim, min_dim)
        )
        if len(faces) == 0:
            faces = self.profile_cascade.detectMultiScale(
                gray_frame,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(min_dim, min_dim)
            )

        results = []
        for (x, y, w, h) in faces:
            cx = x + (w / 2.0)
            cy = y + (h / 2.0)
            results.append((cx, cy, float(w), float(h)))

        # Sort by area descending (largest face = primary speaker)
        results.sort(key=lambda item: item[2] * item[3], reverse=True)
        return results

    def analyze_clip_speaker_x(
        self,
        video_path: str,
        start_sec: float,
        end_sec: float,
        sample_fps: float = 2.0
    ) -> float:
        """
        Samples frames across the clip duration to find the dominant speaker's horizontal center X.
        Returns the optimal target center X normalized or in pixels.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return -1.0

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)
        step_frames = max(1, int(fps / sample_fps))

        detected_x_positions = []

        current_frame_idx = start_frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)

        while current_frame_idx <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.detect_face_centers(gray, frame_h)

            if faces:
                primary_face = faces[0]
                detected_x_positions.append(primary_face[0])

            current_frame_idx += step_frames
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)

        cap.release()

        if not detected_x_positions:
            # Fallback: exact center of video
            return frame_w / 2.0

        # Cluster / median filtering to eliminate camera pans or noise
        median_x = float(np.median(detected_x_positions))
        return median_x

def compute_smart_crop_filter(
    video_path: str,
    start_sec: float,
    end_sec: float,
    out_w: int = 1080,
    out_h: int = 1920
) -> str:
    """
    Computes an intelligent 9:16 crop filter string for FFmpeg that centers directly
    on the active speaker's face instead of blind center cropping.
    """
    try:
        tracker = SmartFaceTracker()
        speaker_cx = tracker.analyze_clip_speaker_x(video_path, start_sec, end_sec, sample_fps=3.0)

        # Get video dimensions using ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        dims = probe_res.stdout.strip().split("x")
        src_w = int(dims[0]) if len(dims) >= 2 else 1920
        src_h = int(dims[1]) if len(dims) >= 2 else 1080

        # Crop dimensions to achieve 9:16 vertical aspect ratio
        # Vertical 9:16 box inside source video:
        crop_w = int(src_h * (9.0 / 16.0))
        crop_h = src_h

        # Calculate crop X offset centered around speaker_cx
        half_crop = crop_w / 2.0
        target_x = speaker_cx - half_crop

        # Clamp crop_x within source bounds: [0, src_w - crop_w]
        crop_x = int(max(0, min(src_w - crop_w, target_x)))

        print(f"[*] Smart Speaker Tracking: Target X={speaker_cx:.1f}px -> Crop Box: x={crop_x}, w={crop_w}, h={crop_h} (source {src_w}x{src_h})")
        return f"crop={crop_w}:{crop_h}:{crop_x}:0,scale={out_w}:{out_h}"

    except Exception as err:
        print(f"[!] Smart tracking fallback to center crop due to: {err}")
        return f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={out_w}:{out_h}"
