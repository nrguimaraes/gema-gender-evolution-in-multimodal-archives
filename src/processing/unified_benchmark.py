import os
import json
import time
import spacy
import stanza
import nltk
from transformers import pipeline
from src.utils.wikidata_api import consultar_wikidata_genero

# --- CONFIGURATION ---
INPUT_DIR = "data/enriched"
OUTPUT_DIR = "data/processed/unified_comparison"
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

# --- MODEL INITIALIZATION ---
print(">>> Initializing all models for comparison...")

# 1. NLTK Baseline
nltk.download('punkt', quiet=True)
from src.processing.classifiers.process_nltk_baseline import analyze_with_nltk

# 2. Stanza (Morphology only)
# Note: Using download_method=None assuming models are already downloaded
stanza_nlp = stanza.Pipeline('pt', processors='tokenize,mwt,pos,lemma', download_method=None)
from src.processing.classifiers.process_stanza import analyze_stanza

# 3. mDeBERTa (Zero-shot)
mdeberta_classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
from src.processing.classifiers.process_mdeberta import analyze_mdeberta

# 4. WikiNeural + Weights (Your top performer)
spacy_nlp = spacy.load("pt_core_news_lg")
ner_model = pipeline("ner", model="Babelscape/wikineural-multilingual-ner", aggregation_strategy="simple")
from src.processing.classifiers.process_wikineural_pesos import analyze_wikineural_weighted

# --- EXECUTION ---
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Running Unified Benchmark on: {filename}")
    with open(os.path.join(INPUT_DIR, filename), 'r', encoding='utf-8') as f:
        data = json.load(f)

    for i, art in enumerate(data):
        full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
        print(f"  [{i+1}/{len(data)}] Analyzing: {art.get('title', '')[:30]}...")

        # Collect all predictions in a single 'comparativo' dictionary
        art['comparativo'] = {
            "nltk_baseline": analyze_with_nltk(full_text)['veredito_nltk'],
            "stanza_morphology": analyze_stanza(full_text)['veredito_stanza'],
            "mdeberta_zero_shot": analyze_mdeberta(full_text)['veredito_mdeberta'],
            "wikineural_weighted": analyze_wikineural_weighted(full_text)['verdict']
        }

    # Save the unified result
    output_path = os.path.join(OUTPUT_DIR, f"unified_{filename}")
    with open(output_path, 'w', encoding='utf-8') as wf:
        json.dump(data, wf, indent=4, ensure_ascii=False)

print(f"\nUnified comparison completed! Results saved in {OUTPUT_DIR}")