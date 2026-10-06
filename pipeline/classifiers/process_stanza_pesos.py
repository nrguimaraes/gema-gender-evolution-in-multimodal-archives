import os
import json
import stanza

from src.utils.wikidata_api import consultar_wikidata_genero 

# --- CONFIGURATION ---
INPUT_DIR = "data/cleaned"
OUTPUT_DIR = "data/processed/processed_stanza_weights"
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

print("Loading Stanza (Morphology and Syntax Pipeline)...")
# Processors: tokenize, mwt (multi-word tokens), pos (tags), and lemma
nlp = stanza.Pipeline('pt', processors='tokenize,mwt,pos,lemma', download_method=None)

def analyze_stanza_hibrido(text):
    """
    Analyzes text using Stanza for morphological features and validates 
    Proper Nouns against Wikidata using a weighted heuristic system.
    """
    # Focusing on the first 800 characters to capture the lead and protagonist
    doc = nlp(text[:800]) 
    
    pos_data = {
        "feminine": {"pronouns": [], "nouns": []}, 
        "masculine": {"pronouns": [], "nouns": []}
    }
    
    score_f, score_m = 0, 0
    candidate_names = []

    for sentence in doc.sentences:
        for word in sentence.words:
            # 1. CAPTURE PROPER NOUNS (PROPN)
            if word.upos == "PROPN":
                candidate_names.append(word.text)

            # 2. GRAMMATICAL GENDER ANALYSIS (feats)
            feats = word.feats if word.feats else ""
            gender = "F" if "Gender=Fem" in feats else "M" if "Gender=Masc" in feats else None
            
            if gender:
                if gender == "F":
                    if word.upos in ["PRON", "DET"]:
                        pos_data["feminine"]["pronouns"].append(word.text.lower())
                        score_f += 5 # Weight 5 for pronouns/determinants
                    elif word.upos == "NOUN":
                        pos_data["feminine"]["nouns"].append(word.text.lower())
                        score_f += 2 # Weight 2 for nouns
                else:
                    if word.upos in ["PRON", "DET"]:
                        pos_data["masculine"]["pronouns"].append(word.text.lower())
                        score_m += 5
                    elif word.upos == "NOUN":
                        pos_data["masculine"]["nouns"].append(word.text.lower())
                        score_m += 2

    # 3. WIKIDATA VALIDATION (Weight 15)
    # Filter unique names detected by Stanza
    validated_protagonists = []
    for name in list(set(candidate_names)):
        if len(name) > 3: # Avoid acronyms or very short names
            genero_wiki = consultar_wikidata_genero(name)
            if genero_wiki != "Desconhecido":
                validated_protagonists.append({"name": name, "gender": genero_wiki})
                if genero_wiki == "Feminino":
                    score_f += 15 # Biographical tie-breaker weight
                else:
                    score_m += 15

    # 4. FINAL VERDICT
    if score_f > score_m:
        verdict = "Feminino"
    elif score_m > score_f:
        verdict = "Masculino"
    else:
        verdict = "Ambos/Neutro"

    return {
        "veredito_stanza": verdict,
        "scores": {"F": score_f, "M": score_m},
        "pos_analysis": pos_data,
        "protagonists": validated_protagonists
    }

# --- MAIN PROCESSING LOOP ---
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Weighted Stanza + Wikidata (Weight 15): {filename}")
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, f"weighted_stanza_{filename}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for art in data:
        full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
        # Core hybrid analysis
        art['analise_stanza_weighted'] = analyze_stanza_hibrido(full_text)

    # Save to the tool-specific output folder
    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=4, ensure_ascii=False)

print("\nWeighted Stanza processing completed!")