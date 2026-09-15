import subprocess
import os
import sys

def test_voice():
    voices = [
        "en-US-SteffanNeural", # Deep American
        "en-GB-RyanNeural",    # Deep British
        "en-US-GuyNeural"      # Deep Newscaster
    ]
    
    text = "Hello there. I am testing a deep, bass voice for your videos. I hope this sounds less like an AI. Let me know which one you prefer."
    
    for voice in voices:
        out_path = f"test_{voice.split('-')[-1]}.mp3"
        print(f"Generating test audio with {voice}...")
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
            
    print("\nPlease double click the new MP3 files in your folder to listen to them!")

if __name__ == "__main__":
    test_voice()
