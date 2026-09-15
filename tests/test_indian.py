import subprocess
import os
import sys

def test_indian_voice():
    voices = [
        "hi-IN-MadhurNeural",           # Hindi Male (very thick accent when reading English)
        "hi-IN-SwaraNeural",            # Hindi Female (thick accent)
        "en-IN-NeerjaExpressiveNeural"  # Indian English Female (more expressive)
    ]
    
    text = "Hello there. I am testing the new Indian AI voice for your videos. I hope this sounds exactly like what you are looking for. Let me know if you prefer the male or female voice!"
    
    print("\nGenerating new Indian voice samples...")
    for voice in voices:
        out_path = f"test_{voice.split('-')[-1]}.mp3"
        try:
            subprocess.run([
                sys.executable, "-m", "edge_tts", 
                "--voice", voice, 
                "--text", text, 
                "--write-media", out_path
            ], check=True)
            print(f"Success! Audio saved to: {os.path.abspath(out_path)}")
        except Exception as e:
            print(f"Error generating audio: {e}")
            
    print("\nPlease double click the new MP3 files in your folder to listen!")

if __name__ == "__main__":
    test_indian_voice()
