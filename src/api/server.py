"""
AI Video Studio - FastAPI Backend (Headless Automation Mode)
Runs an infinite loop in the background, automatically generating videos.
The frontend is a passive dashboard that tunes into the live SSE broadcast.
"""
import os
import json
import time
import shutil
import asyncio
import random
import traceback
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.core.config import OUTPUT_DIR, CHANNEL_NICHES
from src.services.content import generate_daily_content
from src.services.tts import text_to_speech
from src.services.video import generate_ai_video, assemble_video
from src.services.youtube import upload_video, verify_youtube_connection

# ── Global State & Broadcaster ──────────────────────────────────────────────

clients = set()

# In-memory application state
GLOBAL_STATE = {
    "step": 0,
    "status": "idle",
    "message": "Waiting for pipeline to initialize...",
    "script": None,
    "logs": []
}
IS_PIPELINE_RUNNING = False

app = FastAPI(title="AI Video Studio Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")
app.mount("/static", StaticFiles(directory="static"), name="static")


async def broadcast(event: str, data: dict):
    """Update global state and broadcast to all connected web clients."""
    global GLOBAL_STATE
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    
    # Update global state so new clients instantly know where we are
    if event in ("progress", "complete"):
        GLOBAL_STATE["step"] = data.get("step", 0)
        GLOBAL_STATE["status"] = data.get("status", "running")
        GLOBAL_STATE["message"] = data.get("message", "")
        if "script" in data:
            GLOBAL_STATE["script"] = data["script"]
        
        # Keep a short log history
        GLOBAL_STATE["logs"].append({"event": event, "data": data})
        if len(GLOBAL_STATE["logs"]) > 50:
            GLOBAL_STATE["logs"].pop(0)
            
    # Fan out to all connected clients
    for queue in list(clients):
        try:
            queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def run_pipeline_once(topic: str = None, manual_story: str = None, upload_youtube: bool = True, wiki_mode: bool = False, wiki_topic: str = "true_crime", music_preference: str = "all"):
    """Runs the pipeline once, verifying YouTube connectivity first."""
    global IS_PIPELINE_RUNNING, GLOBAL_STATE
    if IS_PIPELINE_RUNNING:
        return
        
    IS_PIPELINE_RUNNING = True
    try:
        loop = asyncio.get_event_loop()
        
        # Reset state for a new run
        GLOBAL_STATE["logs"] = [] 
        GLOBAL_STATE["script"] = None
        
        run_id = f"{time.strftime('%Y%m%d_%H%M%S')}"

        # ── STEP 1: YouTube Pre-Flight Verification ───────────────────────
        await broadcast("progress", {
            "step": 1, "total": 7, "status": "running",
            "message": "🔍 Step 1/7: Verifying YouTube channel credentials & target..."
        })
        is_connected, yt_msg = await loop.run_in_executor(None, verify_youtube_connection)
        if not is_connected:
            await broadcast("error", {
                "status": "error",
                "message": f"❌ YouTube Verification Failed: {yt_msg}. Video generation stopped."
            })
            await broadcast("progress", {
                "step": 1, "total": 7, "status": "error",
                "message": f"⛔ Halting pipeline: YouTube is not connected ({yt_msg}). Video generation aborted."
            })
            return
            
        await broadcast("progress", {
            "step": 1, "total": 7, "status": "done",
            "message": "✅ Step 1/7: YouTube connection verified! Destination confirmed: YouTube (Private Draft)."
        })
        
        # ── STEP 2: Script Generation ──────────────────────────────────────
        if wiki_mode:
            message = f"✍️ Step 2/7: Fetching Wikipedia {wiki_topic} story..."
        elif manual_story:
            message = "✍️ Step 2/7: Writing custom story..."
        else:
            message = f"✍️ Step 2/7: Writing script for: \"{topic}\"..."
            
        await broadcast("progress", {
            "step": 2, "total": 7, "status": "running",
            "message": message
        })
        
        if wiki_mode:
            from src.services.content import generate_wikipedia_content
            content = await loop.run_in_executor(None, generate_wikipedia_content, wiki_topic)
        elif manual_story:
            from src.services.content import generate_manual_content
            content = await loop.run_in_executor(None, generate_manual_content, manual_story)
        else:
            from src.services.content import generate_daily_content
            content = await loop.run_in_executor(None, generate_daily_content, topic)
            
        scenes = content["scenes"]
        
        await broadcast("progress", {
            "step": 2, "total": 7, "status": "done",
            "message": f"✅ Step 2/7: Script complete! {len(scenes)} scenes written.",
            "script": content
        })

        # ── STEP 3: Voiceover Generation ───────────────────────────────────
        await broadcast("progress", {
            "step": 3, "total": 7, "status": "running",
            "message": f"🎙️ Step 3/7: Generating {len(scenes)} voiceover clips..."
        })
        audio_paths = []
        for i, scene in enumerate(scenes):
            path = f"{OUTPUT_DIR}/audio_{run_id}_{i}.wav"
            await loop.run_in_executor(
                None, text_to_speech, scene["narration"], path, topic or "Custom Story"
            )
            audio_paths.append(path)
            await broadcast("progress", {
                "step": 3, "total": 7, "status": "running",
                "message": f"🎙️ Voiceover {i+1}/{len(scenes)} done..."
            })
        await broadcast("progress", {
            "step": 3, "total": 7, "status": "done",
            "message": f"✅ Step 3/7: All {len(scenes)} voiceovers generated!"
        })

        # ── STEP 4: AI Video Generation ────────────────────────────────────
        await broadcast("progress", {
            "step": 4, "total": 7, "status": "running",
            "message": f"🎬 Step 4/7: Sending {len(scenes)} scenes to AI video engines..."
        })
        video_clip_paths = []
        for i, scene in enumerate(scenes):
            path = f"{OUTPUT_DIR}/clip_{run_id}_{i}.mp4"
            prompt = f"{scene['visual_keywords']}, {scene['narration']}"
            await broadcast("progress", {
                "step": 4, "total": 7, "status": "running",
                "message": f"🎬 Rendering scene {i+1}/{len(scenes)}..."
            })
            await loop.run_in_executor(None, generate_ai_video, prompt, path)
            video_clip_paths.append(path)
            await broadcast("progress", {
                "step": 4, "total": 7, "status": "running",
                "message": f"✅ Scene {i+1}/{len(scenes)} rendered!"
            })

        await broadcast("progress", {
            "step": 4, "total": 7, "status": "done",
            "message": f"✅ Step 4/7: All {len(scenes)} video clips rendered!"
        })

        # ── STEP 5: Assembly & Audio Mixing ────────────────────────────────
        final_path = f"{OUTPUT_DIR}/final_{run_id}.mp4"
        await broadcast("progress", {
            "step": 5, "total": 7, "status": "running",
            "message": "🔧 Step 5/7: Assembling scenes, blending music from 22-track library, syncing audio..."
        })
        await loop.run_in_executor(
            None, assemble_video, scenes, audio_paths, video_clip_paths, final_path, topic, None, music_preference
        )
        await broadcast("progress", {
            "step": 5, "total": 7, "status": "done",
            "message": "✅ Step 5/7: Video assembly & sound mix complete!"
        })

        # ── STEP 6: YouTube Upload (Automatic) ─────────────────────────────
        await broadcast("progress", {
            "step": 6, "total": 6, "status": "running",
            "message": "📤 Step 6/6: Uploading video directly to YouTube as a Private Draft..."
        })
        yt_video_id = None
        try:
            yt_video_id = await loop.run_in_executor(
                None, upload_video, final_path, content["title"], content["description"], content["tags"], "27", "private"
            )
            upload_msg = f"✅ Video uploaded directly to YouTube! (ID: {yt_video_id})"
        except Exception as e:
            print(f"YouTube Upload Error: {e}")
            traceback.print_exc()
            upload_msg = f"⚠️ Video ready locally, but YouTube upload failed: {str(e)}"

        video_filename = f"final_{run_id}.mp4"
        await broadcast("complete", {
            "step": 6, "total": 6, "status": "done",
            "message": upload_msg,
            "video": {
                "filename": video_filename,
                "url": f"/videos/{video_filename}",
                "youtube_id": yt_video_id,
                "youtube_url": f"https://youtube.com/watch?v={yt_video_id}" if yt_video_id else None,
                "title": content["title"],
                "description": content["description"],
                "tags": content["tags"],
                "topic": topic or "Custom Story",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "scenes": len(scenes)
            }
        })

        # Set to idle state
        await broadcast("progress", {
            "step": 8, "total": 7, "status": "idle",
            "message": "💤 Ready for the next task..."
        })
        
    except Exception as e:
        traceback.print_exc()
        await broadcast("error", {
            "status": "error",
            "message": f"❌ Pipeline Error: {str(e)}"
        })
        await broadcast("progress", {
            "step": 7, "total": 6, "status": "idle",
            "message": "💤 Ready for the next task..."
        })
    finally:
        IS_PIPELINE_RUNNING = False


@app.on_event("startup")
async def startup_event():
    """Pipeline is now triggered manually via API endpoints."""
    pass


# ── API Routes ─────────────────────────────────────────────────────────────

class AutoGenerateRequest(BaseModel):
    topic: str | None = None
    upload_youtube: bool = True
    music_preference: str = "all"
    
class ManualGenerateRequest(BaseModel):
    story: str
    upload_youtube: bool = True
    music_preference: str = "all"

class GroqKeyRequest(BaseModel):
    key: str

class SelectCredentialRequest(BaseModel):
    filename: str

CREDENTIALS_DIR = "credentials"
_INITIAL_CREDENTIALS_SYNC_DONE = False

def sync_credentials_dir(force: bool = False):
    """Ensure credentials directory exists and perform one-time initial seed from root if needed."""
    global _INITIAL_CREDENTIALS_SYNC_DONE
    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    if _INITIAL_CREDENTIALS_SYNC_DONE and not force:
        return

    # Check existing client_ids in credentials/
    existing_cids = set()
    for f in os.listdir(CREDENTIALS_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(CREDENTIALS_DIR, f), "r", encoding="utf-8") as fh:
                    d = json.load(fh)
                cid = (d.get("installed") or d.get("web") or {}).get("client_id") or d.get("client_id")
                if cid:
                    existing_cids.add(cid)
            except Exception:
                pass

    # One-time initial seeding from root if files exist and cid not already in credentials/
    if os.path.exists("client_secret.json"):
        try:
            with open("client_secret.json", "r", encoding="utf-8") as fh:
                d = json.load(fh)
            cid = (d.get("installed") or d.get("web") or {}).get("client_id")
            if cid and cid not in existing_cids:
                shutil.copy2("client_secret.json", os.path.join(CREDENTIALS_DIR, "client_secret.json"))
                existing_cids.add(cid)
        except Exception:
            pass

    if os.path.exists("token.json"):
        try:
            with open("token.json", "r", encoding="utf-8") as fh:
                d = json.load(fh)
            cid = d.get("client_id")
            if cid and not any(f.startswith(f"token_{cid}") or f == f"token_{cid}.json" for f in os.listdir(CREDENTIALS_DIR)):
                shutil.copy2("token.json", os.path.join(CREDENTIALS_DIR, f"token_{cid}.json"))
        except Exception:
            pass

    _INITIAL_CREDENTIALS_SYNC_DONE = True

def get_credentials_list():
    """
    Returns a unified list of unique YouTube Channel Profiles (one per Google Cloud project).
    Pairs each client_secret with its matching authorized token.
    Exactly ONE channel profile is active at any time.
    """
    sync_credentials_dir()
    
    # Check what is currently active in root
    active_client_id = None
    if os.path.exists("client_secret.json"):
        try:
            with open("client_secret.json", "r", encoding="utf-8") as fh:
                d = json.load(fh)
                inst = d.get("installed") or d.get("web") or {}
                active_client_id = inst.get("client_id")
        except Exception:
            pass

    # Collect all tokens indexed by client_id
    tokens_by_cid = {}
    for fname in os.listdir(CREDENTIALS_DIR):
        if not fname.lower().endswith(".json"):
            continue
        p = os.path.join(CREDENTIALS_DIR, fname)
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "refresh_token" in data and "client_id" in data:
                cid = data["client_id"]
                tokens_by_cid[cid] = {
                    "filename": fname,
                    "account": data.get("account", ""),
                    "scopes_count": len(data.get("scopes", []))
                }
        except Exception:
            pass

    # Also check if root has a valid token.json
    if os.path.exists("token.json"):
        try:
            with open("token.json", "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "client_id" in data:
                cid = data["client_id"]
                if cid not in tokens_by_cid:
                    tokens_by_cid[cid] = {
                        "filename": "token.json",
                        "account": data.get("account", ""),
                        "scopes_count": len(data.get("scopes", []))
                    }
        except Exception:
            pass

    profiles = []
    seen_client_ids = set()

    # Prioritize specific client_secret_xxx.json over generic client_secret.json
    all_files = sorted(os.listdir(CREDENTIALS_DIR), key=lambda x: (x == "client_secret.json", x))

    for fname in all_files:
        if not fname.lower().endswith(".json"):
            continue
        p = os.path.join(CREDENTIALS_DIR, fname)
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and ("installed" in data or "web" in data):
                inst = data.get("installed") or data.get("web") or {}
                cid = inst.get("client_id", "")
                proj = inst.get("project_id", "")
                if not cid or cid in seen_client_ids:
                    continue
                seen_client_ids.add(cid)

                is_active = (active_client_id is not None and cid == active_client_id)
                has_token = (cid in tokens_by_cid)
                token_info = tokens_by_cid.get(cid)
                stat = os.stat(p)

                profiles.append({
                    "filename": fname,
                    "project_id": proj or "YouTube Project",
                    "client_id": cid,
                    "client_id_short": cid[:24] + "..." if len(cid) > 24 else cid,
                    "secret_filename": fname,
                    "has_token": has_token,
                    "token_filename": token_info["filename"] if has_token else None,
                    "account": token_info.get("account", "") if has_token else "",
                    "is_active": is_active,
                    "type": "channel_profile",
                    "type_label": "YouTube Channel Profile",
                    "info": f"Project: {proj} • {'Authorized Token Available' if has_token else 'Sign-In Required'}",
                    "status_label": "Active & Connected" if (is_active and has_token) else ("Active (Needs Sign-In)" if is_active else ("Ready (Authorized)" if has_token else "Standby (Needs Sign-In)")),
                    "size_bytes": stat.st_size,
                    "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                })
        except Exception:
            pass

    return profiles

@app.get("/api/settings/youtube/credentials")
async def api_settings_youtube_list():
    """Returns a list of all unique YouTube Channel profiles."""
    return {"credentials": get_credentials_list()}

@app.post("/api/settings/youtube")
async def api_settings_youtube(file: UploadFile = File(...)):
    """Uploads a YouTube JSON credential, pairs it, and activates this channel."""
    sync_credentials_dir()
    try:
        contents = await file.read()
        try:
            data = json.loads(contents.decode("utf-8"))
        except Exception:
            return {"status": "error", "message": "Uploaded file is not a valid JSON document."}
            
        token_keys = ["token", "refresh_token", "client_id", "client_secret"]
        is_token = isinstance(data, dict) and all(k in data for k in token_keys)
        is_client_secret = isinstance(data, dict) and ("installed" in data or "web" in data)
        
        if not is_token and not is_client_secret:
            return {"status": "error", "message": "Invalid format. Upload a Google OAuth2 client_secret or token JSON."}

        orig_name = os.path.basename(file.filename or "")
        safe_name = "".join(c for c in orig_name if c.isalnum() or c in "._-")
        if not safe_name.lower().endswith(".json"):
            safe_name += ".json"

        stored_path = os.path.join(CREDENTIALS_DIR, safe_name)
        with open(stored_path, "wb") as f:
            f.write(contents)

        # If it's a client secret, activate it and link matching token if available
        if is_client_secret:
            with open("client_secret.json", "wb") as f:
                f.write(contents)
            inst = data.get("installed") or data.get("web") or {}
            cid = inst.get("client_id")
            # Look for existing token for this client_id in credentials/
            matching_token = None
            for f_name in os.listdir(CREDENTIALS_DIR):
                if f_name.endswith(".json") and f_name != safe_name:
                    try:
                        with open(os.path.join(CREDENTIALS_DIR, f_name), "r") as tf:
                            td = json.load(tf)
                        if td.get("client_id") == cid and "refresh_token" in td:
                            matching_token = os.path.join(CREDENTIALS_DIR, f_name)
                            break
                    except Exception:
                        pass
            if matching_token:
                shutil.copy2(matching_token, "token.json")
            elif os.path.exists("token.json"):
                # Mismatched token, remove it so user is prompted to sign in
                try:
                    with open("token.json", "r") as rtf:
                        if json.load(rtf).get("client_id") != cid:
                            os.remove("token.json")
                except Exception:
                    pass
            active_msg = f"Saved '{safe_name}' and activated channel '{inst.get('project_id', 'Google Project')}'!"
        else:
            # Token uploaded: activate it and link to project
            cid = data.get("client_id")
            with open("token.json", "wb") as f:
                f.write(contents)
            if cid:
                shutil.copy2("token.json", os.path.join(CREDENTIALS_DIR, f"token_{cid}.json"))
            active_msg = "Saved and activated YouTube Authorized Token!"

        is_connected, yt_msg = verify_youtube_connection()

        return {
            "status": "success",
            "message": active_msg,
            "connected": is_connected,
            "yt_message": yt_msg,
            "credentials": get_credentials_list()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/settings/youtube/select")
async def api_settings_youtube_select(req: SelectCredentialRequest):
    """Activates the chosen YouTube Channel profile (sets both secret and matching token)."""
    sync_credentials_dir()
    profiles = get_credentials_list()
    
    # Find matching profile by filename or client_id
    matched = None
    for p in profiles:
        if p["filename"] == req.filename or p["client_id"] == req.filename or p["project_id"] == req.filename:
            matched = p
            break
            
    if not matched:
        return {"status": "error", "message": f"Channel profile '{req.filename}' not found."}

    # Activate client secret
    secret_path = os.path.join(CREDENTIALS_DIR, matched["secret_filename"])
    if os.path.exists(secret_path):
        shutil.copy2(secret_path, "client_secret.json")

    # Activate matching token if available, or clear mismatched token
    cid = matched["client_id"]
    token_found = None
    for f_name in os.listdir(CREDENTIALS_DIR):
        if f_name.endswith(".json") and f_name != matched["secret_filename"]:
            try:
                with open(os.path.join(CREDENTIALS_DIR, f_name), "r", encoding="utf-8") as tf:
                    td = json.load(tf)
                if td.get("client_id") == cid and "refresh_token" in td:
                    token_found = os.path.join(CREDENTIALS_DIR, f_name)
                    break
            except Exception:
                pass

    if token_found:
        shutil.copy2(token_found, "token.json")
    elif os.path.exists("token.json"):
        try:
            with open("token.json", "r") as tf:
                if json.load(tf).get("client_id") != cid:
                    os.remove("token.json")
        except Exception:
            pass

    is_connected, yt_msg = verify_youtube_connection()
    return {
        "status": "success",
        "message": f"Activated channel '{matched['project_id']}' as active YouTube configuration!",
        "connected": is_connected,
        "yt_message": yt_msg,
        "credentials": get_credentials_list()
    }

@app.delete("/api/settings/youtube/credentials/{filename}")
async def api_settings_youtube_delete(filename: str):
    """Deletes a channel profile and all its associated files."""
    safe_name = os.path.basename(filename)
    target_path = os.path.join(CREDENTIALS_DIR, safe_name)
    
    # Read to find client_id
    cid_to_remove = None
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            inst = d.get("installed") or d.get("web") or {}
            cid_to_remove = inst.get("client_id") or d.get("client_id")
        except Exception:
            pass
        try:
            os.remove(target_path)
        except Exception:
            pass

    # Also remove any token matching this client_id in credentials/
    if cid_to_remove:
        for f in os.listdir(CREDENTIALS_DIR):
            if f.endswith(".json"):
                fp = os.path.join(CREDENTIALS_DIR, f)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        if json.load(fh).get("client_id") == cid_to_remove:
                            os.remove(fp)
                except Exception:
                    pass

        # If active in root, clean up root files
        if os.path.exists("client_secret.json"):
            try:
                with open("client_secret.json", "r") as fh:
                    if json.load(fh).get("installed", {}).get("client_id") == cid_to_remove:
                        os.remove("client_secret.json")
            except Exception:
                pass
        if os.path.exists("token.json"):
            try:
                with open("token.json", "r") as fh:
                    if json.load(fh).get("client_id") == cid_to_remove:
                        os.remove("token.json")
            except Exception:
                pass

    is_connected, yt_msg = verify_youtube_connection()
    return {
        "status": "success",
        "message": f"Channel '{safe_name}' permanently deleted.",
        "connected": is_connected,
        "yt_message": yt_msg,
        "credentials": get_credentials_list()
    }

@app.post("/api/settings/youtube/authenticate")
async def api_settings_youtube_authenticate():
    """Triggers the one-time interactive OAuth consent flow in the browser using client_secret.json."""
    if not os.path.exists("client_secret.json"):
        # Check if there is any client_secret in credentials/
        found_secret = None
        if os.path.exists(CREDENTIALS_DIR):
            for f in os.listdir(CREDENTIALS_DIR):
                if f.endswith(".json") and "client_secret" in f.lower():
                    found_secret = os.path.join(CREDENTIALS_DIR, f)
                    break
        if found_secret:
            try:
                shutil.copy2(found_secret, "client_secret.json")
            except Exception:
                pass

    if not os.path.exists("client_secret.json"):
        return {"status": "error", "message": "No client_secret.json found. Please upload your OAuth Client Secret JSON first."}
        
    loop = asyncio.get_event_loop()
    try:
        from src.services.youtube import get_authenticated_service
        await loop.run_in_executor(None, lambda: get_authenticated_service(force_interactive=True))
        
        # Save newly created token.json into credentials/ paired with its client_id
        if os.path.exists("token.json"):
            try:
                with open("token.json", "r", encoding="utf-8") as tf:
                    t_data = json.load(tf)
                cid = t_data.get("client_id")
                if cid:
                    dest = os.path.join(CREDENTIALS_DIR, f"token_{cid}.json")
                    shutil.copy2("token.json", dest)
            except Exception:
                pass
            shutil.copy2("token.json", os.path.join(CREDENTIALS_DIR, "token.json"))
            
        is_connected, yt_msg = verify_youtube_connection()
        return {
            "status": "success" if is_connected else "error",
            "message": "YouTube authenticated successfully! Channel is now connected and verified." if is_connected else yt_msg,
            "connected": is_connected,
            "credentials": get_credentials_list()
        }
    except Exception as e:
        return {"status": "error", "message": f"Authentication error: {str(e)}"}

@app.post("/api/settings/groq")
async def api_settings_groq(req: GroqKeyRequest):
    if not req.key or not req.key.strip():
        return {"status": "error", "message": "Key cannot be empty."}
        
    # Append to .env file
    new_env_var = f"GROQ_API_KEY_{int(time.time())}"
    try:
        with open(".env", "a") as f:
            f.write(f"\n{new_env_var}={req.key.strip()}\n")
        
        # Update running memory
        from src.core.config import GROQ_API_KEYS
        if req.key.strip() not in GROQ_API_KEYS:
            GROQ_API_KEYS.append(req.key.strip())
            
        return {"status": "success", "message": "Groq API key added and active!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/settings/youtube/status")
async def api_youtube_status():
    loop = asyncio.get_event_loop()
    is_connected, message = await loop.run_in_executor(None, verify_youtube_connection)
    
    has_client_secret = os.path.exists("client_secret.json")
    if not has_client_secret and os.path.exists(CREDENTIALS_DIR):
        for f in os.listdir(CREDENTIALS_DIR):
            if f.endswith(".json") and "client_secret" in f.lower():
                has_client_secret = True
                break

    return {
        "connected": is_connected,
        "message": message,
        "has_client_secret": has_client_secret,
        "has_token": os.path.exists("token.json")
    }

@app.get("/api/music")
async def get_music_library():
    """Returns all 22 background music tracks along with their mood tags."""
    from src.services.video import get_all_music_files, MOOD_MAP
    files = get_all_music_files()
    library = []
    for f in files:
        fname = os.path.basename(f)
        mood = "Atmospheric"
        for m_name, track_list in MOOD_MAP.items():
            if fname in track_list:
                mood = m_name.capitalize()
                break
        clean_title = os.path.splitext(fname)[0].replace("_", " ")
        library.append({
            "filename": fname,
            "title": clean_title,
            "mood": mood
        })
    return {
        "total": len(library),
        "tracks": library
    }

@app.post("/api/generate/auto")
async def api_generate_auto(req: AutoGenerateRequest):
    global IS_PIPELINE_RUNNING
    if IS_PIPELINE_RUNNING:
        return {"status": "error", "message": "Pipeline is already running another video generation."}
    is_connected, yt_msg = verify_youtube_connection()
    if not is_connected:
        return {
            "status": "error",
            "youtube_connected": False,
            "message": f"⛔ Cannot generate video: YouTube pre-flight check failed ({yt_msg}). All generated videos must automatically upload to YouTube as Private Drafts. Please connect YouTube in Settings first."
        }
    topic = req.topic or random.choice(CHANNEL_NICHES)
    asyncio.create_task(run_pipeline_once(topic=topic, upload_youtube=True, music_preference=req.music_preference))
    return {
        "status": "started",
        "type": "auto",
        "youtube_connected": True,
        "destination": "YouTube (Private Draft)",
        "message": "✅ Pre-flight YouTube check passed! Video will be uploaded to YouTube as a Private Draft."
    }

@app.post("/api/generate/wiki")
async def api_generate_wiki(req: AutoGenerateRequest):
    global IS_PIPELINE_RUNNING
    if IS_PIPELINE_RUNNING:
        return {"status": "error", "message": "Pipeline is already running another video generation."}
    is_connected, yt_msg = verify_youtube_connection()
    if not is_connected:
        return {
            "status": "error",
            "youtube_connected": False,
            "message": f"⛔ Cannot generate video: YouTube pre-flight check failed ({yt_msg}). All generated videos must automatically upload to YouTube as Private Drafts. Please connect YouTube in Settings first."
        }
    asyncio.create_task(run_pipeline_once(upload_youtube=True, wiki_mode=True, wiki_topic=req.topic or "true_crime", music_preference=req.music_preference))
    return {
        "status": "started",
        "type": "wiki",
        "youtube_connected": True,
        "destination": "YouTube (Private Draft)",
        "message": "✅ Pre-flight YouTube check passed! Video will be uploaded to YouTube as a Private Draft."
    }

@app.post("/api/generate/manual")
async def api_generate_manual(req: ManualGenerateRequest):
    global IS_PIPELINE_RUNNING
    if IS_PIPELINE_RUNNING:
        return {"status": "error", "message": "Pipeline is already running another video generation."}
    is_connected, yt_msg = verify_youtube_connection()
    if not is_connected:
        return {
            "status": "error",
            "youtube_connected": False,
            "message": f"⛔ Cannot generate video: YouTube pre-flight check failed ({yt_msg}). All generated videos must automatically upload to YouTube as Private Drafts. Please connect YouTube in Settings first."
        }
    asyncio.create_task(run_pipeline_once(manual_story=req.story, upload_youtube=True, music_preference=req.music_preference))
    return {
        "status": "started",
        "type": "manual",
        "youtube_connected": True,
        "destination": "YouTube (Private Draft)",
        "message": "✅ Pre-flight YouTube check passed! Video will be uploaded to YouTube as a Private Draft."
    }

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

@app.get("/api/gallery")
async def get_gallery():
    output_path = Path(OUTPUT_DIR)
    videos = []
    for f in sorted(output_path.glob("final_*.mp4"), key=os.path.getmtime, reverse=True):
        stat = f.stat()
        run_id = f.stem.replace("final_", "")
        thumb_name = f"thumb_{run_id}.jpg"
        thumb_url = f"/videos/{thumb_name}" if (output_path / thumb_name).exists() else None
        videos.append({
            "filename": f.name,
            "url": f"/videos/{f.name}",
            "thumbnail_url": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            "size_mb": round(stat.st_size / (1024 * 1024), 2)
        })
    return {"videos": videos}


@app.get("/api/stream")
async def stream_progress(request: Request):
    """SSE endpoint for clients to listen to live broadcasts."""
    queue = asyncio.Queue(maxsize=100)
    clients.add(queue)
    
    async def event_generator():
        try:
            # Instantly send the current state to newly connected dashboards
            yield f"event: init_state\ndata: {json.dumps(GLOBAL_STATE)}\n\n"
            
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Use asyncio.wait_for to implement a keep-alive ping every 15 seconds
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    # Send a comment as a keep-alive ping to prevent browser/proxy disconnects
                    yield ": keep-alive\n\n"
        finally:
            clients.remove(queue)
            
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

if __name__ == "__main__":
    import uvicorn
    # DO NOT use reload=True! 
    # Since the pipeline generates files in the output folder, 
    # a reload would instantly kill the server mid-generation.
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=False)
