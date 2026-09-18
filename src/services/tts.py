import os
import re
import json
import asyncio
import threading
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

# Deep, authoritative male voice — closest Edge TTS equivalent to Kokoro's am_michael
EDGE_VOICE = "en-US-GuyNeural"


def _run_async_in_thread(coro):
    """
    Safely run an async coroutine from a synchronous context,
    even when called from inside a running asyncio event loop (FastAPI/uvicorn).
    """
    result = []
    exc = []

    def target():
        try:
            result.append(asyncio.run(coro))
        except Exception as e:
            exc.append(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join()
    if exc:
        raise exc[0]
    return result[0] if result else None


async def _edge_generate(text: str, voice: str, rate: str, volume: str, out_path: str):
    """Async Edge TTS generation — always outputs MP3."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
    await communicate.save(out_path)


def text_to_speech(text: str, out_path: str, topic: str = "facts") -> str:
    """
    Generate speech using Edge TTS with Dynamic Emotion Engine.
    Adjusts speaking rate and volume based on VADER sentiment analysis.
    Produces the same output format (audio file + .json timestamps) as the
    previous Kokoro implementation so all callers remain unchanged.
    """

    # Edge TTS outputs MP3 natively — normalise the output path
    if out_path.endswith('.wav'):
        out_path = out_path.replace('.wav', '.mp3')
    elif not out_path.endswith('.mp3'):
        out_path = out_path + '.mp3'

    print(f"\n--- Generating Dynamic Emotion TTS with Edge TTS ({EDGE_VOICE}) ---")

    # ------------------------------------------------------------------ #
    # Sentence-level emotion analysis (same logic as Kokoro version)      #
    # ------------------------------------------------------------------ #
    sentences = re.split(r'(?<=[.!?]) +', text)

    # Collect per-sentence rate/volume decisions, then pick the dominant mood
    # Edge TTS processes the whole text at once, so we derive a single setting
    # from the weighted average of sentence-level sentiments.
    high_count = 0
    low_count = 0
    neutral_count = 0

    for sentence in sentences:
        if not sentence.strip():
            continue
        scores = analyzer.polarity_scores(sentence)
        compound = scores['compound']

        if "!" in sentence or compound >= 0.4:
            high_count += 1
            print(f"[Emotion: High/Loud]    {sentence}")
        elif compound <= -0.2 or "..." in sentence:
            low_count += 1
            print(f"[Emotion: Low/Suspense] {sentence}")
        else:
            neutral_count += 1
            print(f"[Emotion: Neutral]      {sentence}")

    # Map dominant emotion → Edge TTS rate / volume strings
    if high_count >= low_count and high_count >= neutral_count:
        rate, volume = "+15%", "+50%"
    elif low_count > high_count:
        rate, volume = "-15%", "-40%"
    else:
        rate, volume = "+0%", "+0%"

    print(f"🎙️  Edge TTS → voice={EDGE_VOICE}, rate={rate}, volume={volume}")

    # ------------------------------------------------------------------ #
    # Generate audio                                                       #
    # ------------------------------------------------------------------ #
    _run_async_in_thread(_edge_generate(text, EDGE_VOICE, rate, volume, out_path))

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError("Edge TTS failed to generate any audio.")

    # ------------------------------------------------------------------ #
    # Generate fake word timestamps for karaoke subtitles                  #
    # ------------------------------------------------------------------ #
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

        json_path = out_path.replace(".mp3", ".json").replace(".wav", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(clean_timings, f, indent=2)

    except Exception as e:
        print(f"Failed to generate fake timestamps: {e}")

    return out_path


if __name__ == "__main__":
    test_text = (
        "It had been three long years... The house was completely empty, "
        "and the silence was deafening. I sat on the cold floor, staring at the "
        "faded photograph of us, knowing I would never see her again... "
        "But then! The front door violently smashed open! She was standing right there! "
        "I couldn't believe my eyes!"
    )
    out = text_to_speech(test_text, "test_cinematic.mp3", topic="thriller")
    print(f"Saved to {out}")
