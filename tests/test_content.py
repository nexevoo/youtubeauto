import json
import requests
import traceback
from src.services.content import generate_daily_content

try:
    content = generate_daily_content("interesting space facts")
    print("Type of content:", type(content))
    print(json.dumps(content, indent=2))
    scenes = content["scenes"]
    print("Success!")
except requests.exceptions.HTTPError as e:
    print(e.response.text)
except Exception as e:
    traceback.print_exc()
