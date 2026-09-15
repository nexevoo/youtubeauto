import os
import json
import re
import traceback
import numpy as np
import soundfile as sf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from kokoro import KPipeline

analyzer = SentimentIntensityAnalyzer()
# Lazy load pipeline
pipeline = None

def text_to_speech(text: str, out_path: str, topic: str = "facts") -> str:
    """
    Generate speech using Kokoro TTS with Dynamic Emotion Engine.
    Adjusts speed and volume based on context (sad, twist, important).
    """
    global pipeline
    if pipeline is None:
        pipeline = KPipeline(lang_code='a')

    # Kokoro uses .wav format easily
    if out_path.endswith('.mp3'):
        out_path = out_path.replace('.mp3', '.wav') 

    print(f"\n--- Generating Dynamic Emotion TTS with Kokoro ---")
    
    # Split text into sentences using simple regex
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    final_audio = []
    
    # Use Michael as the base bass voice
    base_voice = 'am_michael' 
    
    for sentence in sentences:
        if not sentence.strip():
            continue
            
        # Analyze sentiment
        scores = analyzer.polarity_scores(sentence)
        compound = scores['compound']
        
        speed = 1.0
        volume = 1.0
        
        # Determine emotion logic based on sentiment scores and punctuation
        # Priority 1: Shouting, Twists, or Action (exclamation mark overrides negative sentiment)
        if "!" in sentence or compound >= 0.4:
            # Twist, important, excited, shout, anger, action
            speed = 1.15
            volume = 1.5
            print(f"[Emotion: High/Loud] {sentence}")
        # Priority 2: Suspense, Sadness, Quiet
        elif compound <= -0.2 or "..." in sentence:
            # Sad, serious, or suspenseful
            speed = 0.85
            volume = 0.6
            print(f"[Emotion: Low/Suspense] {sentence}")
        else:
            # Neutral
            print(f"[Emotion: Neutral] {sentence}")
            
        # Generate with Kokoro
        try:
            generator = pipeline(sentence, voice=base_voice, speed=speed)
            for i, (gs, ps, audio_chunk) in enumerate(generator):
                # Adjust volume of the numpy array
                audio_chunk = audio_chunk * volume
                final_audio.append(audio_chunk)
        except Exception as e:
            print(f"Failed to generate chunk: {e}")
            print(traceback.format_exc())
            
    # Concatenate all numpy audio chunks
    if final_audio:
        master_audio = np.concatenate(final_audio)
        sf.write(out_path, master_audio, 24000)
    else:
        raise RuntimeError("Kokoro failed to generate any audio.")
        
    # Generate FAKE word timestamps for karaoke subtitles so the video doesn't crash
    try:
        from moviepy.editor import AudioFileClip
        audio = AudioFileClip(out_path)
        duration = audio.duration
        audio.close()
        
        words_list = text.split()
        word_count = len(words_list)
        
        clean_timings = []
        if word_count > 0:
            time_per_word = duration / word_count
            current_time = 0.0
            for w in words_list:
                clean_timings.append({
                    "word": w.strip(),
                    "start": round(current_time, 3),
                    "end": round(current_time + time_per_word, 3)
                })
                current_time += time_per_word
                
        json_path = out_path.replace(".wav", ".json").replace(".mp3", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(clean_timings, f, indent=2)
    except Exception as e:
        print(f"Failed to generate fake timestamps: {e}")
        
    return out_path

if __name__ == "__main__":
    test_text = "It had been three long years... The house was completely empty, and the silence was deafening. I sat on the cold floor, staring at the faded photograph of us, knowing I would never see her again... But then! The front door violently smashed open! She was standing right there! I couldn't believe my eyes!"
    out = text_to_speech(test_text, "test_cinematic.wav", topic="thriller")
    print(f"Saved to {out}")
