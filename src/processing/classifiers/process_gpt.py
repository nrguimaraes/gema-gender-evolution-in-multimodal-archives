import os
import json
import time
import requests
import uuid
from src.utils.wikidata_api import consultar_wikidata_genero # Centralized API call

# --- CONFIGURATION ---
URL = "https://api.iaedu.pt/agent-chat//api/v1/agent/cmamvd3n40000c801qeacoad2/stream"
API_KEY = "sk-usr-temfvvlzyrmc8vncd7gv1o8hdnmz5zjkmmh"
CHANNEL_ID = "cmo1asg9u2sbkf80101p9ga0z"
BASE_SLEEP = 5 
MAX_RETRIES = 3 # New: Retry logic to handle 'char 0' errors

def ask_gpt(title, body):
    """
    Sends news content to GPT-4o agent for gender analysis.
    Includes retry logic to mitigate connection timeouts.
    """
    prompt = f"""
    Task: Analyze the grammatical and semantic gender of this sports news.
    RULES: 1. Human Priority (Protagonist). 
            2. Ignore club/team gender if the main person is male/female. 
            3. Result lists = standard gender of the sport.
    Title: {title}
    Text: {body[:600]}
    Respond ONLY in JSON: {{"veredito": "Masculino/Feminino/Ambos", "pistas": {{"pronomes": [], "substantivos": []}}, "justificativa": "..."}}
    """
    headers = {'x-api-key': API_KEY}
    payload = {
        "channel_id": CHANNEL_ID,
        "thread_id": str(uuid.uuid4()), 
        "message": prompt
    }

    for attempt in range(MAX_RETRIES):
        try:
            # Increased timeout to 120s to reduce 'char 0' errors[cite: 22]
            response = requests.post(URL, headers=headers, data=payload, timeout=120, stream=True)
            response.raise_for_status()

            full_answer = ""
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8').replace('data: ', '').strip()
                    try:
                        data_json = json.loads(decoded)
                        if data_json.get('type') == 'token': 
                            full_answer += data_json.get('content', '')
                        elif 'answer' in data_json: 
                            full_answer += data_json['answer']
                    except: continue

            # Robust JSON cleaning
            clean_text = full_answer.replace("```json", "").replace("```", "").strip()
            start = clean_text.find('{')
            end = clean_text.rfind('}') + 1
            if start != -1 and end > 0:
                return json.loads(clean_text[start:end])
            return json.loads(clean_text)

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  [Retry {attempt+1}] Connection issue, retrying in 5s...")
                time.sleep(5)
                continue
            return {"veredito": "Error", "error_msg": str(e)}

# --- MAIN PROCESSING LOOP ---
INPUT_DIR = "data/cleaned"
OUTPUT_DIR = "data/processed/processed_gpt" # Saved to general processed folder
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

# Filter for relevant abola files
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, f"gpt_{filename}")

    with open(input_path, "r", encoding="utf-8") as f:
        current_data = json.load(f)

    # Load existing results to support resuming from a crash
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                old_results = {art['link']: art.get('analise_gpt') for art in json.load(f)}
            for art in current_data:
                if art['link'] in old_results: 
                    art['analise_gpt'] = old_results[art['link']]
        except: pass

    print(f"\n>>> Processing with GPT: {filename}")

    for art in current_data:
        # Check if already processed to save tokens/time
        status = (art.get("analise_gpt") or {}).get("veredito")
        if status in ["Masculino", "Feminino", "Ambos"]:
            continue

        print(f"  Analyzing: {art.get('title', '')[:40]}...")
        art["analise_gpt"] = ask_gpt(art.get("title", ""), art.get("body_text", ""))

        # Guard against permission errors (OneDrive/System locking)
        try:
            with open(output_path, "w", encoding="utf-8") as out:
                json.dump(current_data, out, indent=4, ensure_ascii=False)
        except PermissionError:
            print("  [Warning] Output file locked by system. Skipping save for this item.")
        
        time.sleep(BASE_SLEEP)

print("\nGPT Analysis Completed!")