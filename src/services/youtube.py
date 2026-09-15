"""
Step 4: Upload to YouTube automatically, with no manual click each day.

How the "no permission needed each time" part actually works:
Google's OAuth requires you, the channel owner, to approve access ONCE in a
browser (run get_authenticated_service() interactively the first time). That
approval issues a refresh token, which this script saves to token.json.
Every day after that, the script uses the refresh token to get a new access
token silently - no browser, no click, no human in the loop. That's the
standard and *legitimate* way "YouTube automation" tools work; there's no
way (or reason) to skip Google's one-time consent screen entirely, since
that consent is what proves you actually own the channel.

Quota note: uploading a video costs a big chunk of your daily 10,000-unit
YouTube Data API quota (historically 1,600 units/upload; Google changed this
in Dec 2025 to a smaller, separately-bucketed cost of roughly 100 units per
upload with its own ~100/day sub-limit). Either way, ONE upload per day - the
brief in this pipeline - uses only a small fraction of the daily allowance.
"""
import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from src.core.config import YT_CLIENT_SECRETS_FILE, YT_TOKEN_FILE, YT_SCOPES


def get_secret_client_id() -> str | None:
    """Reads the client_id from client_secret.json if it exists."""
    if not os.path.exists(YT_CLIENT_SECRETS_FILE):
        return None
    try:
        import json
        with open(YT_CLIENT_SECRETS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        inst = d.get("installed") or d.get("web") or {}
        return inst.get("client_id")
    except Exception:
        return None


def get_token_client_id() -> str | None:
    """Reads the client_id from token.json if it exists."""
    if not os.path.exists(YT_TOKEN_FILE):
        return None
    try:
        import json
        with open(YT_TOKEN_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("client_id")
    except Exception:
        return None


def verify_youtube_connection() -> tuple[bool, str]:
    """
    Checks if YouTube credentials exist, are valid (or refreshable), and match the active client_secret.
    Does NOT trigger interactive login.
    Returns (True, "YouTube connection active") or (False, "Error message").
    """
    if not os.path.exists(YT_TOKEN_FILE):
        return False, "YouTube token.json not found. Please authenticate YouTube in Settings first."

    secret_cid = get_secret_client_id()
    token_cid = get_token_client_id()

    # Reject mismatched tokens from other Google projects
    if secret_cid and token_cid and secret_cid != token_cid:
        return False, "Active token belongs to a different project. Please click 'Sign In with Google (SSO)' to authorize this channel."

    try:
        creds = Credentials.from_authorized_user_file(YT_TOKEN_FILE, YT_SCOPES)
        if not creds:
            return False, "Unable to load YouTube credentials from token.json."

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(YT_TOKEN_FILE, "w") as token_file:
                    token_file.write(creds.to_json())
            else:
                return False, "YouTube credentials are expired and cannot be refreshed. Please re-authenticate in Settings."

        return True, "YouTube connection active and verified."
    except Exception as e:
        return False, f"YouTube verification failed: {str(e)}"


def get_authenticated_service(force_interactive: bool = False):
    """
    Returns an authenticated YouTube API client.
    Guarantees the token matches the active client_secret.json.
    If force_interactive is True, always runs the interactive OAuth consent flow in the browser.
    """
    creds = None
    secret_cid = get_secret_client_id()

    if os.path.exists(YT_TOKEN_FILE) and not force_interactive:
        token_cid = get_token_client_id()
        # Only use existing token.json if it belongs to the current client_secret.json!
        if not secret_cid or not token_cid or secret_cid == token_cid:
            try:
                creds = Credentials.from_authorized_user_file(YT_TOKEN_FILE, YT_SCOPES)
            except Exception:
                creds = None

    if not creds or not creds.valid or force_interactive:
        if creds and creds.expired and creds.refresh_token and not force_interactive:
            try:
                creds.refresh(Request())  # silent, no browser - this is the daily-run path
            except Exception:
                creds = None

        if not creds or not creds.valid or force_interactive:
            if not os.path.exists(YT_CLIENT_SECRETS_FILE):
                raise FileNotFoundError(f"Missing '{YT_CLIENT_SECRETS_FILE}'. Please upload your Google OAuth client secret in Settings.")

            # Interactive step - run with the active client_secret.json!
            flow = InstalledAppFlow.from_client_secrets_file(YT_CLIENT_SECRETS_FILE, YT_SCOPES)
            creds = flow.run_local_server(
                host="localhost",
                port=0,
                authorization_prompt_message="AUTH_URL_START: {url} :AUTH_URL_END",
                success_message="Authentication successful! Your YouTube channel is now connected. You can close this tab now.",
                open_browser=True
            )
            with open(YT_TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, title: str, description: str, tags: list[str],
                  category_id: str = "27", privacy_status: str = "public", thumbnail_path: str = None) -> str:
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": category_id,  # 27 = Education, change to fit your niche
        },
        "status": {
            "privacyStatus": privacy_status,  # "private" first if you want to sanity-check uploads
            "selfDeclaredMadeForKids": False,
        },
    }

    # 2MB chunks for reliable transmission over home internet / Wi-Fi
    chunk_size = 2 * 1024 * 1024
    media = MediaFileUpload(video_path, chunksize=chunk_size, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    import time
    import socket
    import http.client
    from googleapiclient.errors import HttpError

    response = None
    retry_count = 0
    max_retries = 10
    retriable_status_codes = [500, 502, 503, 504]

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")
            retry_count = 0  # reset retry counter on successful chunk
        except (ConnectionResetError, socket.error, http.client.RemoteDisconnected, Exception) as e:
            if isinstance(e, HttpError) and e.resp.status not in retriable_status_codes:
                raise e
            
            retry_count += 1
            if retry_count > max_retries:
                print(f"Upload aborted: Exceeded {max_retries} retries due to: {e}")
                raise e

            sleep_seconds = min(2 ** retry_count, 30)
            print(f"⚠️ Network connection dropped ({e}). Resuming upload from current progress in {sleep_seconds}s (attempt {retry_count}/{max_retries})...")
            time.sleep(sleep_seconds)

    video_id = response["id"]
    print(f"Uploaded: https://youtube.com/watch?v={video_id}")
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        print(f"Uploading custom thumbnail from {thumbnail_path}...")
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg", resumable=True)
            ).execute()
            print("✅ Custom thumbnail uploaded successfully to YouTube!")
        except Exception as e:
            print(f"⚠️ YouTube custom thumbnail notice: {e}")

    return video_id


if __name__ == "__main__":
    # Run this file directly ONCE to do the interactive Google consent screen
    # and generate token.json before you ever put main.py on a schedule.
    get_authenticated_service()
    print("Auth complete - token.json saved. Future runs will be fully unattended.")
