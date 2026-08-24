import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No GEMINI_API_KEY found.")
else:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get("models", [])
        print("Available Gemini Models:")
        for m in models:
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(m["name"])
    else:
        print(f"Error fetching models: {response.text}")
