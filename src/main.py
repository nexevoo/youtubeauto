"""
Daily orchestrator: content -> audio -> video -> upload.
Run this once a day via cron / Task Scheduler / GitHub Actions (see README).
"""
import os
import time
from src.core.config import OUTPUT_DIR, CHANNEL_NICHES
from src.services.content import generate_daily_content
from src.services.tts import text_to_speech
from src.services.video import generate_ai_video, assemble_video
from src.services.youtube import upload_video
from src.services.thumbnail import generate_thumbnail


def run_daily_job():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_run_id = time.strftime("%Y%m%d")

    for index, topic in enumerate(CHANNEL_NICHES):
        print(f"\n--- Processing topic {index + 1}/{len(CHANNEL_NICHES)}: {topic} ---")
        run_id = f"{base_run_id}_{index + 1}"
        
        try:
            print("1/4 Generating script with Groq...")
            content = generate_daily_content(topic)
            scenes = content["scenes"]

            print("2/4 Generating voiceover for each scene (free TTS)...")
            audio_paths = []
            for i, scene in enumerate(scenes):
                path = f"{OUTPUT_DIR}/audio_{run_id}_{i}.wav"
                final_audio_path = text_to_speech(scene["narration"], path, topic=topic)
                audio_paths.append(final_audio_path)

            print("3/4 Generating real AI Video for each scene (this takes time)...")
            video_clip_paths = []
            for i, scene in enumerate(scenes):
                path = f"{OUTPUT_DIR}/clip_{run_id}_{i}.mp4"
                # Using the full narration as prompt gives these AI models more context
                prompt = f"{scene['visual_keywords']}, {scene['narration']}"
                generate_ai_video(prompt, save_path=path)
                video_clip_paths.append(path)

            print("3.5/4 Generating Thumbnail (to flash at start of video)...")
            thumbnail_path = f"{OUTPUT_DIR}/thumb_{run_id}.jpg"
            generate_thumbnail(content["title"], thumbnail_path)

            print("4/4 Assembling Video...")
            final_path = f"{OUTPUT_DIR}/final_{run_id}.mp4"
            assemble_video(scenes, audio_paths, video_clip_paths, final_path, topic=topic, thumbnail_path=thumbnail_path)

            print("5/4 Uploading to YouTube...")
            upload_video(
                video_path=final_path,
                title=content["title"],
                description=content["description"],
                tags=content["tags"],
                privacy_status="private",  # Keeps them in draft/private state
                thumbnail_path=thumbnail_path
            )
            print(f"Successfully finished processing topic: {topic}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error processing topic '{topic}': {e}")
            print("Continuing to next topic...")

    print("\nDone for today. All requested topics processed.")


if __name__ == "__main__":
    run_daily_job()
