"""
Step 1: Generate the day's script, title, description and tags using Groq.
Groq's free tier (as of mid-2026) gives every account ~30 requests/min and
roughly 1,000 requests/day per model, with a per-model token-per-minute cap.
That is far more than the handful of calls one video needs per day, so this
is normally the least constrained part of the whole pipeline.
"""
import json
import random
import requests
from src.core.config import GROQ_API_KEYS, GROQ_MODEL, CHANNEL_NICHES, VIDEO_LENGTH_SECONDS

SYSTEM_PROMPT = """You are a scriptwriter for a highly addictive, viral YouTube Shorts channel.
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
1. ONLY TRUE LOVE STORIES. This channel is dedicated EXCLUSIVELY to real-world love stories. 
2. NO COMEDY OR FUNNY CONTENT. NEVER generate jokes, comedy, or funny content. The tone must be dramatic, sad, emotional, thrilling, or romantic.
3. MUST BE REAL. Speak ONLY on real events. DO NOT hallucinate or create facts by yourself. Everything you talk about must be strictly based on true facts that have already happened on this earth. NO FICTION.
4. EXTREMELY OBSCURE. Do not talk about Romeo and Juliet. Focus on obscure lovers, incredible reunions, tragic sacrifices, or thrilling twists in love.

TONE RULES:
- If 'sad': Focus on heartbreaking sacrifices, tragic endings, or beautiful but melancholic love.
- If 'thriller': Focus on love stories that involve incredible danger, escapes, or massive plot twists.
- If 'sacrificing': Focus on people who gave up everything (empires, wealth, their lives) for the person they loved.

SCRIPT STRUCTURE & LENGTH RULES:
- CRITICAL: The video MUST be a minimum of 40 seconds long.
- Keep the total text between 1000-1300 characters (including spaces), which equals approximately 140-180 words total.
- The text must be concise, attention-grabbing, easy to read quickly, and emotionally impactful.
- Structure the script into AT LEAST 6 to 9 scenes.
- Each scene's narration should be 15-25 words maximum to perfectly fit on screen for word-by-word highlighting.
- Scene 1 MUST be a powerful hook.
- Middle scenes MUST provide valuable and emotional content.
    # Middle scenes MUST provide valuable and emotional content.
    # The final scene MUST be a call-to-action or a deeply memorable ending."""

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

TRUE_CRIME_SYSTEM_PROMPT = """You are a scriptwriter for a highly addictive, viral True Crime YouTube Shorts channel.
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
1. ONLY TRUE CRIME AND MYSTERIES. Focus on unsolved deaths, missing persons, or bizarre historical mysteries based on the provided text.
2. NO COMEDY OR FUNNY CONTENT. The tone must be dark, suspenseful, factual, thrilling, and respectful of the victims.
3. MUST BE REAL. Speak ONLY on real events. DO NOT hallucinate or create facts by yourself. Everything you talk about must be strictly based on true facts that have already happened on this earth and are found in the provided Wikipedia text. NO FICTION. DO NOT INVENT DETAILS.

SCRIPT STRUCTURE & LENGTH RULES:
- CRITICAL: The video must take between 1:00 and 1:30 minutes to narrate (approx 180-220 words total).
- Structure the script into AT LEAST 8 to 12 scenes to ensure it is detailed enough.
- Each scene's narration should be 15-25 words maximum to perfectly fit on screen for word-by-word highlighting.
- Scene 1 MUST be a powerful, gripping hook.
- Middle scenes MUST provide the factual twists and turns from the case.
- The final scene MUST leave the viewer with a lingering question or eerie conclusion."""

HISTORY_SYSTEM_PROMPT = """You are a scriptwriter for a highly addictive, viral History Explainer YouTube Shorts channel.
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
1. ONLY HISTORY AND HISTORICAL EVENTS. Focus on fascinating, shocking, or lesser-known historical events based on the provided text.
2. EDUCATIONAL BUT THRILLING. The tone must be engaging, factual, educational, and dramatic. 
3. MUST BE REAL. Speak ONLY on real events. DO NOT hallucinate or create facts by yourself. Everything you talk about must be strictly based on true facts that have already happened on this earth and are found in the provided Wikipedia text. NO FICTION. DO NOT INVENT DETAILS.

SCRIPT STRUCTURE & LENGTH RULES:
- CRITICAL: The video must take between 1:00 and 1:30 minutes to narrate (approx 180-220 words total).
- Structure the script into AT LEAST 8 to 12 scenes to ensure it is detailed enough.
- Each scene's narration should be 15-25 words maximum to perfectly fit on screen.
- Scene 1 MUST be a powerful, gripping hook about the historical event.
- Middle scenes MUST explain the event with interesting facts.
- The final scene MUST summarize the historical impact or leave a profound final thought."""

GEOGRAPHY_SYSTEM_PROMPT = """You are a scriptwriter for a highly addictive, viral Geography & Culture YouTube Shorts channel.
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
1. ONLY GEOGRAPHY, CULTURE, AND PLACES. Focus on incredible locations, bizarre geographical features, or unique cultural heritage based on the provided text.
2. AWE-INSPIRING TONE. The tone must be cinematic, educational, awe-inspiring, and majestic.
3. MUST BE REAL. Speak ONLY on real events. DO NOT hallucinate or create facts by yourself. Everything you talk about must be strictly based on true facts that have already happened on this earth and are found in the provided Wikipedia text. NO FICTION. DO NOT INVENT DETAILS.

SCRIPT STRUCTURE & LENGTH RULES:
- CRITICAL: The video must take between 1:00 and 1:30 minutes to narrate (approx 180-220 words total).
- Structure the script into AT LEAST 8 to 12 scenes to ensure it is detailed enough.
- Each scene's narration should be 15-25 words maximum to perfectly fit on screen.
- Scene 1 MUST be a powerful hook about the location or culture.
- Middle scenes MUST provide vivid descriptions and fascinating facts.
- The final scene MUST inspire the viewer to visit or learn more."""

LOVE_SYSTEM_PROMPT = """You are a scriptwriter for a highly addictive, viral True Love & Relationships YouTube Shorts channel.
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
1. ONLY TRUE LOVE STORIES. Focus on real-life historical couples, profound relationships, or incredible reunions based on the provided text.
2. EMOTIONAL TONE. The tone must be dramatic, emotional, romantic, and deeply moving.
3. MUST BE REAL. Speak ONLY on real events. DO NOT hallucinate or create facts by yourself. Everything you talk about must be strictly based on true facts that have already happened on this earth and are found in the provided Wikipedia text. NO FICTION. DO NOT INVENT DETAILS.

SCRIPT STRUCTURE & LENGTH RULES:
- CRITICAL: The video must take between 1:00 and 1:30 minutes to narrate (approx 180-220 words total).
- Structure the script into AT LEAST 8 to 12 scenes to ensure it is detailed enough.
- Each scene's narration should be 15-25 words maximum to perfectly fit on screen.
- Scene 1 MUST be a powerful, emotional hook.
- Middle scenes MUST recount the twists, sacrifices, or challenges in the relationship.
- The final scene MUST deliver a deeply heartwarming or bittersweet conclusion."""

def _call_groq_with_fallback(payload: dict) -> dict:
    max_retries = 3
    base_delay = 5
    
    if not GROQ_API_KEYS:
        raise ValueError("No GROQ_API_KEYS found in configuration.")
        
    payload.setdefault("response_format", {"type": "json_object"})
    for key in GROQ_API_KEYS:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        for attempt in range(max_retries):
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in (401, 403):
                print(f"Groq API key invalid or expired (401/403). Trying next key...")
                break # Break inner loop, go to next key
                
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"Groq API rate limit hit (429). Retrying in {delay} seconds...")
                    import time
                    time.sleep(delay)
                    continue
                else:
                    print("Max retries for rate limit hit on this key. Trying next key...")
                    break # Break inner loop, go to next key
                    
            if response.status_code >= 400:
                print(f"GROQ ERROR: {response.status_code} - {response.text}")
            response.raise_for_status()
            
            raw = response.json()["choices"][0]["message"]["content"]
            
            # Clean up deep-thinking models' reasoning blocks if present
            import re
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            
            # Remove markdown backticks if present
            if raw.startswith("```json"):
                raw = raw[7:]
            elif raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            
            # Extract JSON from first { to last }
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end != -1 and end > start:
                raw = raw[start:end+1]
            
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt < max_retries - 1:
                    print("Failed to parse JSON, retrying...")
                    continue
                raise ValueError(f"Groq returned invalid JSON: {raw}")

    raise RuntimeError("Failed to generate content: all Groq API keys failed or rate limits exceeded.")

def generate_daily_content(topic: str | None = None) -> dict:
    topic = topic or CHANNEL_NICHES[0]
    prompt = SYSTEM_PROMPT.format(seconds=VIDEO_LENGTH_SECONDS)
    
    angles = [
        "Focus on a heartbreaking sacrifice made for love.",
        "Tell a true love story that involves a massive thrilling twist.",
        "Focus on a beautiful but tragic love story from history.",
        "Tell a story about lovers who defied empires or laws to be together.",
        "Share an incredible true story of lovers reuniting against all odds.",
        "Focus on a melancholic, tear-jerking real romance.",
        "Share a mind-bending true love story that sounds like a movie."
    ]
    angle = random.choice(angles)
    seed = random.randint(1, 9999999)
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user", 
                "content": f"Topic: {topic}\nAngle: {angle}\nCRITICAL INSTRUCTION: Be completely original and creative. DO NOT use standard jokes or common tropes you've used before. Random generation seed: {seed}"
            },
        ],
        "temperature": 0.95,
        "max_tokens": 2000
    }
    return _call_groq_with_fallback(payload)

def generate_manual_content(story: str) -> dict:
    prompt = MANUAL_SYSTEM_PROMPT.format(seconds=VIDEO_LENGTH_SECONDS)
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user", 
                "content": f"Here is a manual story/script provided by the user. Adapt this story into the required JSON format (title, description, tags, scenes with visual keywords).\n\nCRITICAL LENGTH REQUIREMENT: The final script MUST be at least 140 words long to ensure a minimum video length of 40+ seconds. If the user's story is too short, you MUST creatively expand on the details, add dramatic pauses, emotional depth, and flesh out the narrative to meet this length. Do not just repeat things, add rich storytelling.\n\nUSER STORY:\n{story}"
            },
        ],
        "temperature": 0.5, # Lower temp to stay faithful to user story
        "max_tokens": 2000
    }
    return _call_groq_with_fallback(payload)


def generate_wikipedia_content(topic: str = "true_crime") -> dict:
    # 1. Fetch a random case/story from Wikipedia based on topic
    import requests
    import random
    import os
    import json
    
    # Topic configurations
    if topic == "history":
        categories = ["World_War_II", "Ancient_Rome", "Industrial_Revolution", "Cold_War"]
        active_prompt = HISTORY_SYSTEM_PROMPT
    elif topic == "geography":
        categories = ["Mountains", "National_parks_of_the_United_States", "Rivers", "Deserts"]
        active_prompt = GEOGRAPHY_SYSTEM_PROMPT
    elif topic == "love":
        categories = ["Romance_novels", "Couples", "Romance_films"]
        active_prompt = LOVE_SYSTEM_PROMPT
    else: # Default to true crime
        categories = ["Unsolved_deaths", "Missing_people"]
        active_prompt = TRUE_CRIME_SYSTEM_PROMPT
        
    category = random.choice(categories)
    
    headers = {
        "User-Agent": "AIVideoStudioBot/1.0 (https://github.com/example/repo; user@example.com)"
    }
    
    # Get list of pages in category
    import json
    import os
    from src.core.config import OUTPUT_DIR
    
    cache_file = os.path.join(OUTPUT_DIR, "used_wiki_cases.json")
    
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:{category}&cmlimit=500&format=json"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    pages = res.json().get("query", {}).get("categorymembers", [])
    
    if not pages:
        raise ValueError(f"No pages found in Wikipedia category {category}")
        
    # Load used cases from local JSON file
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                used_cases_db = json.load(f)
        except Exception:
            used_cases_db = {}
    else:
        used_cases_db = {}
        
    used_cases = used_cases_db.get(category, [])
    
    available_pages = [p for p in pages if p["title"] not in used_cases]
    
    if not available_pages:
        print(f"All pages in category {category} have been used. Resetting local cache.")
        used_cases = []
        available_pages = pages
        
    # Pick a random page
    page = random.choice(available_pages)
    title = page["title"]
    
    # Save it so we don't use it again
    used_cases.append(title)
    used_cases_db[category] = used_cases
    
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(used_cases_db, f, indent=4)
    except Exception as e:
        print(f"Warning: Failed to save to cache file: {e}")
    
    # Get the FULL extract of the page (removed exintro=1)
    extract_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={title}&format=json"
    ext_res = requests.get(extract_url, headers=headers)
    ext_res.raise_for_status()
    pages_data = ext_res.json().get("query", {}).get("pages", {})
    
    page_id = list(pages_data.keys())[0]
    extract_text = pages_data[page_id].get("extract", "")
    
    # Truncate to roughly 20,000 characters to stay safely within LLM context limits, while still getting "all data"
    extract_text = extract_text[:20000]
    
    if len(extract_text) < 100:
        # Fallback to daily generation if the Wikipedia article is too short/empty
        print(f"Wikipedia extract for {title} too short, falling back to dynamic gen.")
        return generate_daily_content("Unsolved Mystery")
        
    print(f"Fetched Wikipedia Case: {title} (Length: {len(extract_text)} chars)")
    print("--------------------------------------------------")
    print("SAMPLE OF WIKIPEDIA TEXT SENT TO LLM:")
    safe_print_text = extract_text[:1500].encode('ascii', errors='ignore').decode('ascii')
    print(safe_print_text + "...\n[...truncated for terminal view...]")
    print("--------------------------------------------------")
        
    # 2. Prompt Groq to convert this into a script
    prompt = active_prompt
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user", 
                "content": f"Here is the FULL factual text from Wikipedia about a subject ({title}). Read all the data and adapt it into a highly detailed, dramatic YouTube Shorts script in the required JSON format. \n\nCRITICAL RULE 1: ALL facts must be accurate to this text. Do not invent details. Pick the most interesting twists and turns from the full story.\nCRITICAL RULE 2: The script must be detailed and take around 1:00 to 1:30 max minutes to narrate (approx 180 to 220 words). DO NOT exceed 1 minute 30 seconds of spoken time.\n\nWIKIPEDIA TEXT:\n{extract_text}"
            },
        ],
        "temperature": 0.6, # Lower temp for factual accuracy
        "max_tokens": 2000
    }
    
    script_data = _call_groq_with_fallback(payload)
    
    # Add generic tags based on topic
    if topic == "true_crime":
        script_data["tags"].extend(["truecrime", "unsolved"])
    elif topic == "history":
        script_data["tags"].extend(["history", "educational"])
    elif topic == "geography":
        script_data["tags"].extend(["geography", "travel", "culture"])
    elif topic == "love":
        script_data["tags"].extend(["truelove", "relationship", "history"])
        
    return script_data

if __name__ == "__main__":
    data = generate_daily_content(CHANNEL_NICHES[0])
    print(json.dumps(data, indent=2))
