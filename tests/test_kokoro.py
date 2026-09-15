import os
import soundfile as sf
import traceback

def test_kokoro():
    print("Initializing Kokoro Pipeline...")
    try:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code='a') # 'a' = American English
        
        # We can also print all available voices!
        print("\n--- Here are all the voices Kokoro supports ---")
        # pipeline.list_voices() is available but might be too long, let's just generate a few best ones:
        
        test_voices = [
            "am_onyx", 
            "am_puck", 
            "am_echo",
            "am_eric",
            "am_liam"
        ]
        
        text = "This is a quick test of a different Kokoro voice. Let me know what you think!"
        
        print("\nGenerating new voice samples...")
        for voice in test_voices:
            generator = pipeline(text, voice=voice, speed=1.0)
            for i, (gs, ps, audio) in enumerate(generator):
                out_path = f"test_kokoro_{voice}.wav"
                sf.write(out_path, audio, 24000)
                print(f"Success! Audio saved to: {os.path.abspath(out_path)}")
                
        print("\nPlease double click the new WAV files in your folder to listen!")
            
    except Exception as e:
        print("Error running Kokoro!")
        print(traceback.format_exc())

if __name__ == "__main__":
    test_kokoro()
