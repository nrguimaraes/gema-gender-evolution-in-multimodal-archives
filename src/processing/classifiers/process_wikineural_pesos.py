import os
import json
import spacy
from transformers import pipeline
# Import the centralized Wikidata utility from the new src/utils folder
from src.utils.wikidata_api import consultar_wikidata_genero 

# --- ENVIRONMENT CONFIGURATION ---
INPUT_DIR = "data/cleaned"
# Dedicated folder for weighted WikiNeural results
OUTPUT_DIR = "data/processed/processed_wikineural_weights"
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

# --- MODEL LOADING ---
print("Loading SpaCy (Linguistics) and WikiNeural (NER)...")
# Large Portuguese model for grammatical features[cite: 14]
nlp = spacy.load("pt_core_news_lg") 
# State-of-the-art multilingual NER for person extraction[cite: 14, 15]
ner_model = pipeline("ner", model="Babelscape/wikineural-multilingual-ner", aggregation_strategy="simple")

def analyze_wikineural_hibrido(text):
    """
    Hybrid analysis using transformer-based NER and grammatical weights, 
    validated by Wikidata's biographical 'ground truth'[cite: 1, 6, 14].
    """
    doc = nlp(text)
    # Morphological structure for JSON transparency[cite: 12]
    pos_data = {
        "feminine": {"pronouns": [], "nouns": []}, 
        "masculine": {"pronouns": [], "nouns": []}
    }
    
    # Score initialization
    s_f, s_m = 0, 0

    # 1. GRAMMATICAL ANALYSIS (SpaCy)[cite: 1, 5, 14]
    for t in doc:
        gender = t.morph.get("Gender")
        if t.pos_ in ["PRON", "DET"]:
            if "Fem" in gender:
                pos_data["feminine"]["pronouns"].append(t.text.lower())
                s_f += 5 # Weight 5 for pronouns indicating the subject[cite: 1]
            elif "Masc" in gender:
                pos_data["masculine"]["pronouns"].append(t.text.lower())
                s_m += 5
        
        if t.pos_ == "NOUN":
            if "Fem" in gender:
                pos_data["feminine"]["nouns"].append(t.text.lower())
                s_f += 2 # Weight 2 for nouns[cite: 5]
            elif "Masc" in gender:
                pos_data["masculine"]["nouns"].append(t.text.lower())
                s_m += 2

    # 2. NER EXTRACTION (WikiNeural)[cite: 14, 15]
    entities = ner_model(text[:512]) # Analyzing lead paragraph
    # Filtering unique names with more than 3 characters
    raw_names = list(set([e['word'] for e in entities if e['entity_group'] == 'PER' and len(e['word']) > 3]))
    
    # 3. WIKIDATA VALIDATION (Weight 15)[cite: 6]
    validated_protagonists = []
    for name in raw_names:
        # Using the centralized API utility
        gender_wiki = consultar_wikidata_genero(name)
        if gender_wiki != "Desconhecido":
            validated_protagonists.append({"name": name, "gender": gender_wiki})
            if gender_wiki == "Feminino":
                s_f += 15 # High priority biographical weight[cite: 6]
            else:
                s_m += 15

    # 4. FINAL VERDICT
    if s_f > s_m:
        verdict = "Feminino"
    elif s_m > s_f:
        verdict = "Masculino"
    else:
        verdict = "Ambos/Neutro"

    return {
        "veredito_wikineural": verdict,
        "scores": {"F": s_f, "M": s_m},
        "pos_analysis": pos_data,
        "protagonists": validated_protagonists
    }

# --- PROCESSING LOOP ---
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Processing with Weighted WikiNeural + Wikidata: {filename}")
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, f"weighted_wikineural_{filename}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for art in data:
        full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
        # Core classification logic[cite: 1, 6, 14]
        art['analise_wikineural_weighted'] = analyze_wikineural_hibrido(full_text)

    # Save to the tool-specific output folder[cite: 6]
    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=4, ensure_ascii=False)

print("\nWeighted WikiNeural processing completed!")