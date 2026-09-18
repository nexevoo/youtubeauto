"""
Step 3: Build the actual video file using true AI Video Generation.
This completely replaces stock footage with generative AI.
"""
import os
import glob

# Auto-detect newly installed ImageMagick on Windows so a terminal restart isn't required
magick_paths = glob.glob(r"C:\Program Files\ImageMagick-*\magick.exe")
if magick_paths:
    os.environ["IMAGEMAGICK_BINARY"] = magick_paths[0]

import time
import requests
import random
import textwrap
import uuid

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, vfx, CompositeAudioClip, ColorClip, VideoClip
)
from moviepy.audio.fx.all import audio_loop
from moviepy.video.io.ffmpeg_writer import ffmpeg_write_video
from src.core.config import PIXVERSE_API_KEY, KLING_API_KEY, QWEN_API_KEY, RUNWAYML_API_KEY, PEXELS_API_KEY, OUTPUT_DIR, COVERR_API_KEY

def _poll_and_download(status_url: str, headers: dict, save_path: str, extract_url_func) -> str:
    """Helper to poll an async video generation task and download the result."""
    print(f"Polling status at {status_url}...")
    max_attempts = 60  # 60 * 5s = 5 minutes max wait
    for attempt in range(max_attempts):
        time.sleep(5)
        try:
            resp = requests.get(status_url, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"Poll attempt {attempt+1} network error: {e}. Retrying...")
            continue

        if resp.status_code != 200:
            print(f"Poll attempt {attempt+1} got HTTP {resp.status_code}. Retrying...")
            continue

        data = resp.json()
        video_url = extract_url_func(data)

        if video_url == "failed":
            raise RuntimeError(f"Video generation failed: {data}")
        elif video_url:
            print(f"Video ready! Downloading from {video_url[:60]}...")
            video_data = requests.get(video_url, timeout=120).content
            with open(save_path, "wb") as fh:
                fh.write(video_data)
            print(f"Saved to {save_path}")
            return save_path
        else:
            print(f"Poll attempt {attempt+1}: still processing...")

    raise RuntimeError("Timed out waiting for video generation after 5 minutes")


def generate_pixverse(prompt: str, save_path: str) -> str:
    """Generate a 9:16 vertical video using the Pixverse v2 API (model v6, 1080p)."""
    if not PIXVERSE_API_KEY:
        raise RuntimeError("PIXVERSE_API_KEY (platform_pixverse) is not set in .env")

    print("Using Pixverse API (model v6, 1080p)...")
    generate_url = "https://app-api.pixverse.ai/openapi/v2/video/text/generate"
    headers = {
        "API-KEY": PIXVERSE_API_KEY,
        "Ai-trace-id": str(uuid.uuid4()),  # Must be unique per request
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt,
        "model": "v6",          # Latest and best model
        "aspect_ratio": "9:16", # Vertical for Shorts / TikTok
        "duration": 5,          # 5 seconds per scene clip
        "quality": "720p",      # Max quality on free plan (1080p requires paid)
        "water_mark": False,    # No watermark on the video
    }

    print(f"Submitting Pixverse job: '{prompt[:80]}...'")
    resp = requests.post(generate_url, json=payload, headers=headers, timeout=30)

    # Surface the full error body if the request fails
    if resp.status_code != 200:
        raise RuntimeError(
            f"Pixverse generation request failed [{resp.status_code}]: {resp.text}"
        )

    resp_body = resp.json()
    err_code = resp_body.get("ErrCode", -1)
    if err_code != 0:
        raise RuntimeError(
            f"Pixverse API error (ErrCode={err_code}): {resp_body.get('ErrMsg')} | {resp_body}"
        )

    video_id = resp_body.get("Resp", {}).get("video_id")
    if not video_id:
        raise RuntimeError(f"Pixverse did not return a video_id. Full response: {resp_body}")

    print(f"Pixverse job submitted. video_id={video_id}. Polling for result...")
    status_url = f"https://app-api.pixverse.ai/openapi/v2/video/result/{video_id}"

    def extract_url(data):
        """
        Pixverse status codes:
          0  = queued / processing  -> keep polling
          1  = succeeded            -> return video_url
         -1  = failed              -> raise
        """
        resp_data = data.get("Resp", {})
        err = data.get("ErrCode", 0)
        if err != 0:
            return "failed"  # API-level error on the status poll
        status = resp_data.get("status")
        if status == 1:
            url = resp_data.get("url") or resp_data.get("video_url") or resp_data.get("download_url")
            return url if url else None
        if status == -1:
            return "failed"
        return None  # Still processing (status == 0)

    return _poll_and_download(status_url, headers, save_path, extract_url)


def generate_kling(prompt: str, save_path: str) -> str:
    print("Using Kling AI API...")
    url = "https://api.klingai.com/v1/videos/text2video"
    # Assuming the provided key is a Bearer token (common for aggregators)
    headers = {
        "Authorization": f"Bearer {KLING_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model_name": "kling-v1",
        "prompt": prompt,
        "ratio": "9:16",
        "duration": 5
    }
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    task_id = resp.json().get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Kling failed to start: {resp.text}")
        
    status_url = f"https://api.klingai.com/v1/videos/text2video/{task_id}"
    
    def extract_url(data):
        status = data.get("data", {}).get("task_status")
        if status == "succeed": return data["data"]["task_result"]["videos"][0]["url"]
        if status == "failed": return "failed"
        return None
        
    return _poll_and_download(status_url, headers, save_path, extract_url)


def generate_happyhorse(prompt: str, save_path: str) -> str:
    print("Using Alibaba HappyHorse API (DashScope)...")
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    headers = {
        "X-DashScope-Async": "enable",
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "happyhorse-1.1-t2v",
        "input": {"prompt": prompt},
        "parameters": {"resolution": "720P", "duration": 5, "ratio": "9:16"}
    }
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    task_id = resp.json().get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"HappyHorse failed to start: {resp.text}")
        
    status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    
    def extract_url(data):
        status = data.get("output", {}).get("task_status")
        if status == "SUCCEEDED": return data["output"]["video_url"]
        if status == "FAILED": return "failed"
        return None

    return _poll_and_download(status_url, headers, save_path, extract_url)
        
def generate_pollinations_video(prompt: str, save_path: str) -> str:
    import urllib.parse
    from moviepy.editor import ImageClip
    
    print("Using Pollinations.ai (100% Free Image Generator)...")
    # Pollinations expects URL-encoded prompts
    encoded_prompt = urllib.parse.quote(f"A cinematic high quality vertical video frame of {prompt}")
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
    
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    
    temp_img = save_path + ".jpg"
    with open(temp_img, "wb") as f:
        f.write(resp.content)
        
    print("Image generated. Converting to 5-second video clip...")
    clip = ImageClip(temp_img).set_duration(5)
    # Write at a low fps to save encoding time since it's a static image
    clip.write_videofile(save_path, fps=10, codec="libx264", logger=None)
    
    if os.path.exists(temp_img):
        os.remove(temp_img)
        
    return save_path

def generate_pexels_video(prompt: str, save_path: str) -> str:
    print("Using Pexels API for free stock video...")
    # Extract just the visual keywords (before the comma) for a better Pexels search
    search_term = prompt.split(',')[0].strip()
    headers = {"Authorization": PEXELS_API_KEY}

    url = f"https://api.pexels.com/videos/search?query={search_term}&orientation=portrait&per_page=15"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("videos"):
        raise RuntimeError(f"Pexels found no videos for '{search_term}'")

    # pick a random video from the first page of results
    video = random.choice(data["videos"])

    # get the best quality HD link
    hd_files = [f for f in video["video_files"] if f["quality"] == "hd" or f["quality"] == "sd"]
    if not hd_files:
        hd_files = video["video_files"]

    video_url = hd_files[0]["link"]

    print("Downloading Pexels video...")
    video_data = requests.get(video_url, timeout=60).content
    with open(save_path, "wb") as fh:
        fh.write(video_data)

    return save_path


def generate_coverr_video(prompt: str, save_path: str) -> str:
    """Search Coverr's free stock video API and download the best match.

    Free tier: 50 requests/hour. No AI generation — uses high-quality
    pre-made stock footage matched by keyword from the scene prompt.
    API docs: https://api.coverr.co/docs
    """
    if not COVERR_API_KEY:
        raise RuntimeError("COVERR_API_KEY not set in .env")

    # Build a list of search terms to try: 2-word → 1-word
    raw_words = prompt.split(',')[0].strip().split('.')[0].strip().split()
    
    # Filter out common filler words that break stock video searches
    stop_words = {"and", "on", "in", "at", "to", "with", "for", "of", "the", "a", "an", "is", "are"}
    clean_words = [w for w in raw_words if w.lower() not in stop_words]
    
    if not clean_words:
        clean_words = ["interesting"] # Ultimate fallback keyword
        
    search_terms = []
    if len(clean_words) >= 2:
        search_terms.append(' '.join(clean_words[:2]))  # e.g. "laughing audience"
    search_terms.append(clean_words[0])                 # e.g. "laughing"

    headers = {"Authorization": f"Bearer {COVERR_API_KEY}"}
    hits = []
    used_term = search_terms[0]

    for term in search_terms:
        # Silently try the term
        resp = requests.get(
            "https://api.coverr.co/videos",
            params={"query": term, "urls": "true", "per_page": 10},
            headers=headers,
            timeout=30
        )
        if resp.status_code == 401:
            raise RuntimeError("Coverr API: 401 Unauthorized. Check your COVERR_API_KEY in .env.")
        if resp.status_code == 429:
            raise RuntimeError("Coverr API: rate limit hit (50 req/hr). Wait before retrying.")
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if hits:
            used_term = term
            break  # Found results — stop trying shorter terms

    if not hits:
        raise RuntimeError(f"Coverr found no videos for prompt")

    # Pick a random one from the top results for variety
    video = random.choice(hits[:5])
    download_url = (
        video.get("urls", {}).get("mp4_download")
        or video.get("urls", {}).get("mp4")
    )
    if not download_url:
        raise RuntimeError(f"Coverr video has no download URL: {video}")

    print(f"Downloading Coverr video: {video.get('title', 'untitled')} (matched: '{used_term}')...")
    dl = requests.get(download_url, timeout=60)
    with open(save_path, "wb") as fh:
        fh.write(dl.content)
    print(f"Saved to {save_path}")
    return save_path


def generate_ai_video(prompt: str, save_path: str) -> str:
    """
    Uses Pexels stock video API.
    """
    print("Using Pexels API for free stock video...")
    
    # --- Pexels (always free fallback) ---
    if PEXELS_API_KEY:
        try:
            return generate_pexels_video(prompt, save_path)
        except Exception as e:
            print(f"[WARNING] Pexels failed: {e}")
            raise RuntimeError(f"Pexels API failed: {e}")
    else:
        raise RuntimeError("PEXELS_API_KEY not configured in .env.")


def build_scene_clip(video_path: str, audio_path: str, caption: str) -> CompositeVideoClip:
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # We remove the Ken Burns effect because real AI video has organic motion
    clip = (
        VideoFileClip(video_path)
        .without_audio()
        .resize(height=1920)
        .set_duration(duration)
        .fx(vfx.crop, width=1080, height=1920, x_center=None, y_center=None)
    )

    # --- Premium subtitle: Karaoke-style dynamic highlighting ---
    import json
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    json_path = os.path.splitext(audio_path)[0] + ".json"
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            timings = json.load(f)
    except FileNotFoundError:
        print(f"Warning: Timestamps not found for {audio_path}, skipping subtitles.")
        return clip.set_audio(audio)

    words = [t['word'] for t in timings]
    
    font_size = 70
    stroke_width = 12
    font_path = r"C:\Windows\Fonts\impact.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

    max_width = 850
    lines = []
    current_line = []
    current_width = 0
    
    word_boxes = []
    for w in words:
        bbox = font.getbbox(w + " ")
        w_width = bbox[2] - bbox[0]
        word_boxes.append((w, w_width))
        
    for i, (w, w_width) in enumerate(word_boxes):
        if current_line and current_width + w_width > max_width:
            lines.append(current_line)
            current_line = []
            current_width = 0
        current_line.append(i)
        current_width += w_width
        
    if current_line:
        lines.append(current_line)
        
    # Paginate into chunks of 4 lines max so it never overflows the screen
    max_lines_per_page = 4
    pages = [lines[i:i+max_lines_per_page] for i in range(0, len(lines), max_lines_per_page)]
        
    line_height = int(font_size * 1.2)
    # Fixed height based on max lines to prevent text jumping vertically
    total_height = int(max_lines_per_page * line_height)

    # Frame caching to prevent drawing the same frame twice (once for RGB, once for mask)
    frame_cache = {"t": -1, "img": None}

    def render_pil_frame(t):
        if frame_cache["t"] == t:
            return frame_cache["img"]
            
        active_index = -1
        for i, timing in enumerate(timings):
            if timing['start'] <= t <= timing['end']:
                active_index = i
                break
            if t > timing['end'] and (i == len(timings)-1 or t < timings[i+1]['start']):
                active_index = i
                
        # Find which page contains the active word
        active_page = pages[0] if pages else []
        for page in pages:
            if any(active_index in line for line in page):
                active_page = page
                break
                
        # Transparent background RGBA
        img = Image.new('RGBA', (max_width + 60, total_height + 60), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Center the page vertically if it has fewer than 4 lines
        actual_page_height = len(active_page) * line_height
        y_offset = 30 + (total_height - actual_page_height) // 2
        
        for line in active_page:
            line_w = sum(word_boxes[idx][1] for idx in line)
            x_offset = (max_width + 60 - line_w) // 2
            
            for idx in line:
                word_text = word_boxes[idx][0]
                # Karaoke effect: Active word is bright green, others are white
                fill_color = "#39FF14" if idx == active_index else "white"
                
                draw.text((x_offset, y_offset), word_text + " ", font=font, 
                          fill=fill_color, stroke_width=stroke_width, stroke_fill="black")
                
                x_offset += word_boxes[idx][1]
                
            y_offset += line_height
            
        img_array = np.array(img)
        frame_cache["t"] = t
        frame_cache["img"] = img_array
        return img_array

    def make_rgb_frame(t):
        # Return only R, G, B channels
        return render_pil_frame(t)[:, :, :3]
        
    def make_mask_frame(t):
        # Return Alpha channel normalized to 0.0-1.0
        return render_pil_frame(t)[:, :, 3] / 255.0

    # MoviePy expects the color clip and mask clip to be separated
    subtitle = VideoClip(make_rgb_frame, duration=duration)
    mask = VideoClip(make_mask_frame, duration=duration, ismask=True)
    subtitle = subtitle.set_mask(mask)
    
    # Position lower on the screen (0.80) to be closer to the bottom edge as requested
    subtitle = subtitle.set_position(("center", 0.80), relative=True)

    return CompositeVideoClip([clip, subtitle]).set_audio(audio)



PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES_DIR = os.path.dirname(os.path.abspath(__file__))

# Global rotation index so every generated video pulls the next music tracks from all 22 tracks
_GLOBAL_MUSIC_ROTATION_INDEX = 0

MOOD_MAP = {
    "crime": [
        "Beneath_Cold_Branches.mp3",
        "Stone_Garden.mp3",
        "Before_the_Monsoon_Breaks.mp3",
        "The_Ghats_at_Twilight.mp3",
    ],
    "love": [
        "Entre_Lágrimas_y_Sol.mp3",
        "The_Bridge_of_Sighs.mp3",
        "A_Winter_s_Dawn (1).mp3",
        "Conversations_in_Cedar.mp3",
    ],
    "history": [
        "Ascending_the_Ridge.mp3",
        "The_Summit_at_Dawn.mp3",
        "The_Arching_Rise.mp3",
        "First_Light_in_the_Orchard.mp3",
    ],
    "geography": [
        "Kaveri_Morning.mp3",
        "Morning_at_the_Ghats.mp3",
        "Saffron_Hour.mp3",
        "Scent_Of_Wet_Earth.mp3",
        "Under_the_Banyan_Canopy.mp3",
        "The_Monsoon_s_First_Bloom.mp3",
    ],
    "fun": [
        "Oops_Wrong_Fret.mp3",
        "Pratfall_Promenade.mp3",
        "The_Banana_Peel_Incident.mp3",
        "The_Great_Tumble.mp3",
    ],
}


def get_all_music_files() -> list[str]:
    """Finds and returns all available background music tracks in the workspace."""
    tracks = []
    for f in sorted(os.listdir(PROJECT_ROOT)):
        if f.lower().endswith((".mp3", ".wav")) and not f.startswith(("test_", "audio_", "dummy", "final_", "TEMP_")):
            full_p = os.path.join(PROJECT_ROOT, f)
            if os.path.isfile(full_p):
                tracks.append(full_p)
    return tracks


def pick_music_tracks(final_duration: float, topic: str = "", music_preference: str = "all") -> list[str]:
    """
    Selects one or more music tracks from the complete library of all 22 tracks.
    - If video duration > 28s, selects multiple tracks to blend rather than repeating one.
    - Rotates across all 22 tracks continuously so every track gets played.
    """
    global _GLOBAL_MUSIC_ROTATION_INDEX
    all_tracks = get_all_music_files()
    if not all_tracks:
        return []

    # If a specific track was requested and exists
    if music_preference and music_preference not in ("all", "mood", "auto", ""):
        matched = [
            t for t in all_tracks
            if os.path.basename(t) == music_preference or os.path.splitext(os.path.basename(t))[0] == music_preference
        ]
        if matched:
            return matched

    # Calculate how many tracks are needed to cover the duration without looping just one track
    num_tracks_needed = max(1, int((final_duration + 20) // 25))

    chosen = []
    topic_lower = (topic or "").lower()

    # Mood-based matching if specified or evident in topic
    if music_preference == "mood" or any(k in topic_lower for k in ["crime", "murder", "love", "history", "geography"]):
        mood_keys = []
        if any(w in topic_lower for w in ["crime", "mystery", "murder", "unsolved", "kill", "dark"]):
            mood_keys = ["crime"]
        elif any(w in topic_lower for w in ["love", "romance", "couple", "heart", "passion", "tear"]):
            mood_keys = ["love"]
        elif any(w in topic_lower for w in ["history", "ancient", "war", "empire", "king", "summit"]):
            mood_keys = ["history"]
        elif any(w in topic_lower for w in ["geography", "travel", "culture", "india", "place", "river", "mountain"]):
            mood_keys = ["geography"]
        
        candidates = []
        for mk in mood_keys:
            for fname in MOOD_MAP.get(mk, []):
                p = os.path.join(PROJECT_ROOT, fname)
                if os.path.exists(p) and p not in candidates:
                    candidates.append(p)
        
        if candidates:
            for _ in range(num_tracks_needed):
                idx = _GLOBAL_MUSIC_ROTATION_INDEX % len(candidates)
                _GLOBAL_MUSIC_ROTATION_INDEX = (_GLOBAL_MUSIC_ROTATION_INDEX + 1) % len(all_tracks)
                cand = candidates[idx]
                if cand not in chosen:
                    chosen.append(cand)

    # Fill remaining from complete 22-track rotation queue
    while len(chosen) < num_tracks_needed:
        next_track = all_tracks[_GLOBAL_MUSIC_ROTATION_INDEX % len(all_tracks)]
        _GLOBAL_MUSIC_ROTATION_INDEX = (_GLOBAL_MUSIC_ROTATION_INDEX + 1) % len(all_tracks)
        if next_track not in chosen:
            chosen.append(next_track)

    return chosen


def build_composite_background_music(final_duration: float, topic: str = "", music_preference: str = "all"):
    """
    Builds a composite background music audio clip blending one or more tracks
    with smooth crossfading, pulling dynamically from the library of 22 tracks.
    """
    tracks = pick_music_tracks(final_duration, topic, music_preference)
    if not tracks:
        print("No background music found, skipping.")
        return None

    track_names = [os.path.basename(t) for t in tracks]
    print(f"🎵 Background Music Selection ({len(tracks)} track{'s' if len(tracks)>1 else ''}): {', '.join(track_names)}")

    if len(tracks) == 1:
        bg = AudioFileClip(tracks[0]).volumex(0.08)
        if bg.duration < final_duration:
            from moviepy.audio.fx.all import audio_loop
            bg = audio_loop(bg, duration=final_duration)
        else:
            bg = bg.subclip(0, final_duration)
        return bg

    # Multiple tracks: blend across duration with smooth crossfade
    clips = []
    seg_duration = final_duration / len(tracks)
    crossfade_time = 2.0

    current_start = 0.0
    for idx, t_path in enumerate(tracks):
        raw = AudioFileClip(t_path).volumex(0.08)
        clip_dur = seg_duration + (crossfade_time if idx < len(tracks) - 1 else 0.0)
        clip_dur = min(clip_dur, raw.duration)
        
        seg = raw.subclip(0, clip_dur).set_start(current_start)
        
        try:
            from moviepy.audio.fx.all import audio_fadein, audio_fadeout
            if idx > 0:
                seg = audio_fadein(seg, crossfade_time)
            if idx < len(tracks) - 1:
                seg = audio_fadeout(seg, crossfade_time)
        except Exception:
            pass
            
        clips.append(seg)
        current_start += seg_duration

    comp = CompositeAudioClip(clips)
    return comp.subclip(0, final_duration)


def assemble_video(scenes: list[dict], audio_paths: list[str], video_clip_paths: list[str], out_path: str, topic: str = "", music_preference: str = "all") -> str:
    scene_clips = [
        build_scene_clip(v, a, s["narration"])
        for s, a, v in zip(scenes, audio_paths, video_clip_paths)
    ]
    
    final = concatenate_videoclips(scene_clips, method="compose")

    # Dynamically blend background music from the full 22-track library
    bg_music = build_composite_background_music(final.duration, topic, music_preference)
    if bg_music is not None:
        final_audio = CompositeAudioClip([final.audio, bg_music])
        final = final.set_audio(final_audio)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Bypass write_videofile's broken decorator chain entirely.
    # MoviePy's write_videofile internally writes the audio to a temp file, then calls ffmpeg_write_video.
    # We will just do exactly that manually.
    audiofile = None
    if final.audio is not None:
        audiofile = out_path + "TEMP_MPY_wvf_snd.mp3"
        final.audio.write_audiofile(audiofile, fps=44100, nbytes=2, buffersize=2000,
                                    codec="libmp3lame", bitrate="160k", verbose=True, logger="bar")

    from moviepy.video.io.ffmpeg_writer import ffmpeg_write_video
    ffmpeg_write_video(final, out_path, 30, codec="libx264",
                       preset="medium", write_logfile=False,
                       audiofile=audiofile, verbose=True, threads=None, logger="bar")
    
    # Cleanup temp audio
    if audiofile and os.path.exists(audiofile):
        try:
            os.remove(audiofile)
        except Exception:
            pass

    print(f"Moviepy - video ready {out_path}")
    return out_path
