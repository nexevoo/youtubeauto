import sys
import os
from moviepy.editor import ColorClip
from src.services.video import build_scene_clip

# Create dummy video
os.makedirs("test_output", exist_ok=True)
video = ColorClip(size=(1080, 1920), color=(0, 0, 0), duration=2)
video.write_videofile("test_output/dummy.mp4", fps=24, codec="libx264")

# Create dummy audio and timings
import json
from moviepy.editor import AudioFileClip
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np

audio = AudioArrayClip(np.zeros((44100 * 2, 2)), fps=44100)
audio.write_audiofile("test_output/dummy.mp3")

timings = [
    {"word": "Deep", "start": 0.0, "end": 0.1},
    {"word": "within", "start": 0.1, "end": 0.2},
    {"word": "the", "start": 0.2, "end": 0.3},
    {"word": "Auschwitz", "start": 0.3, "end": 0.4},
    {"word": "concentration", "start": 0.4, "end": 0.5},
    {"word": "camp", "start": 0.5, "end": 0.6},
    {"word": ",", "start": 0.6, "end": 0.7},
    {"word": "amidst", "start": 0.7, "end": 0.8},
    {"word": "the", "start": 0.8, "end": 0.9},
    {"word": "chaos", "start": 0.9, "end": 1.0},
    {"word": "of", "start": 1.0, "end": 1.1},
    {"word": "war", "start": 1.1, "end": 1.2},
    {"word": "and", "start": 1.2, "end": 1.3},
    {"word": "death", "start": 1.3, "end": 1.4},
    {"word": ",", "start": 1.4, "end": 1.5},
    {"word": "a", "start": 1.5, "end": 1.6},
    {"word": "glimmer", "start": 1.6, "end": 1.7},
    {"word": "of", "start": 1.7, "end": 1.8},
    {"word": "hope", "start": 1.8, "end": 1.9}
]
with open("test_output/dummy.json", "w") as f:
    json.dump(timings, f)

# Build scene clip
clip = build_scene_clip("test_output/dummy.mp4", "test_output/dummy.mp3", "caption")
clip.write_videofile("test_output/final_test.mp4", fps=24, codec="libx264")
