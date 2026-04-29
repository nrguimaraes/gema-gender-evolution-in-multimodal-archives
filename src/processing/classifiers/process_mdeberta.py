import os
import json
from transformers import pipeline
from src.utils.wikidata_api import consultar_wikidata_genero # Standardized utility

# --- CONFIGURATION ---
INPUT_DIR = "data/cleaned"
# Each classifier now has its own dedicated output folder
OUTPUT_DIR = "data/processed/processed_mdeberta"  
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

print("Loading mDeBERTa-v3 (Multilingual Zero-Shot Classification)...")
# Using a transformer model to classify text without specific training
classifier = pipeline(
    "zero-shot-classification", 
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
)

def analyze_mdeberta(text):
    """
    Uses mDeBERTa to perform zero-shot classification on sports news 
    gender representation[cite: 15].
    """
    labels = ["Masculino", "Feminino", "Ambos"]
    try:
        # We truncate to 800 chars to fit model constraints and focus on lead info[cite: 15]
        res = classifier(
            text[:800], 
            candidate_labels=labels, 
            hypothesis_template="Esta notícia de desporto é sobre o género {}."
        )
        return {
            "veredito_mdeberta": res['labels'][0],      
            "confidence": round(res['scores'][0], 3),
            "detailed_scores": dict(zip(res['labels'], res['scores']))
        }
    except Exception as e: 
        return {"error": str(e)}

# --- EXECUTION LOOP ---
files = [f for f in os.listdir(INPUT_DIR) 
         if f.endswith('.json') and 'abola' in f.lower() 
         and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Processing with mDeBERTa: {filename}")
    
    with open(os.path.join(INPUT_DIR, filename), 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for art in data:
        # Combine title and body for maximum semantic context[cite: 15]
        full_text = f"{art.get('title', '')} {art.get('body_text', '')}"
        art['analise_mdeberta'] = analyze_mdeberta(full_text)
    
    # Save output in the specific folder defined above[cite: 6]
    output_path = os.path.join(OUTPUT_DIR, f"mdeberta_{filename}")
    with open(output_path, 'w', encoding='utf-8') as wf:
        json.dump(data, wf, indent=4, ensure_ascii=False)

print("\nmDeBERTa-v3 Processing Completed!")