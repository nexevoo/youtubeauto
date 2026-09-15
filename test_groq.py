import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

MANUAL_SYSTEM_PROMPT = """You are a scriptwriter for a highly addictive, viral YouTube Shorts channel.
Return ONLY valid json (JSON format), no markdown fences, no commentary, matching this schema:
{{
  "title": "string, under 100 chars, extremely click-worthy but not misleading",
  "description": "string, 2-3 sentences plus 3 relevant hashtags",
  "tags": ["array", "of", "8-12", "keywords"],
  "scenes": [
    {{"narration": "one sentence spoken by the narrator", "visual_keywords": "2-4 words to search stock footage for"}}
  ]
}}

CONTENT RULES - strictly follow these:
1. ADAPT THE USER'S STORY. Match the tone (dramatic, educational, scary, etc.) of the story provided.
2. MUST BE REAL. Speak ONLY on real events based on the user's input.

SCRIPT STRUCTURE & LENGTH RULES:
- CRITICAL: The video MUST be a minimum of 40 seconds long.
- Keep the total text between 1000-1300 characters (approx 140-180 words total).
- Structure the script into AT LEAST 6 to 9 scenes.
- Each scene's narration should be 15-25 words maximum.
- Scene 1 MUST be a powerful hook.
- The final scene MUST be deeply memorable."""

story = "The Dancing Plague of 1518 in Strasbourg. Frau Troffea starts dancing, doesn't stop. 30+ join within a week, 400 by August. No music, no rest, feet bleed. Officials hire musicians/build stage (makes it worse). People collapse/die from exhaustion/stroke/heart attack. Theories: mass psychogenic illness, ergot poisoning, religious hysteria. Unexplained start and stop."

payload = {
    "model": "mixtral-8x7b-32768",
    "messages": [
        {"role": "system", "content": MANUAL_SYSTEM_PROMPT},
        {
            "role": "user", 
            "content": f"Here is a manual story/script provided by the user. Adapt this story into the required JSON format (title, description, tags, scenes with visual keywords).\n\nCRITICAL LENGTH REQUIREMENT: The final script MUST be at least 140 words long to ensure a minimum video length of 40+ seconds. If the user's story is too short, you MUST creatively expand on the details, add dramatic pauses, emotional depth, and flesh out the narrative to meet this length. Do not just repeat things, add rich storytelling.\n\nUSER STORY:\n{story}"
        }
    ],
    "temperature": 0.5,
    "max_tokens": 4000
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

res = requests.post('https://api.groq.com/openai/v1/chat/completions', headers=headers, json=payload)
print("STATUS CODE:", res.status_code)
if res.status_code != 200:
    print(res.text)
else:
    raw = res.json()["choices"][0]["message"]["content"]
    print("RAW OUTPUT:", repr(raw))
    import re
    raw_clean = re.sub(r'<think>.*?(?:</think>|$)', '', raw, flags=re.DOTALL).strip()
    
    if raw_clean.startswith("```json"):
        raw_clean = raw_clean[7:]
    elif raw_clean.startswith("```"):
        raw_clean = raw_clean[3:]
    if raw_clean.endswith("```"):
        raw_clean = raw_clean[:-3]
    raw_clean = raw_clean.strip()
    
    print("CLEAN OUTPUT:")
    print(raw_clean)
    try:
        json.loads(raw_clean)
        print("JSON IS VALID!")
    except Exception as e:
        print("JSON ERROR:", e)
