import os
import json
import spacy
from transformers import pipeline

# --- CONFIGURATION ---
INPUT_DIR = "data/cleaned"
# Dedicated folder for standard WikiNeural results
OUTPUT_DIR = "data/processed/processed_wikineural"
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

print("Loading models (SpaCy + WikiNeural NER)...")
# Loading large Portuguese model for morphology
nlp = spacy.load("pt_core_news_lg") 
# Loading transformer-based NER model[cite: 15, 27]
ner_model = pipeline("ner", model="Babelscape/wikineural-multilingual-ner", aggregation_strategy="simple")

def analyze_wikineural(text):
    """
    Performs standard NER and counts grammatical gender occurrences using SpaCy[cite: 19, 27].
    Does not apply weights or Wikidata validation.
    """
    doc = nlp(text)
    pos_data = {
        "feminine": {"pronouns": [], "nouns": []}, 
        "masculine": {"pronouns": [], "nouns": []}
    }
    
    # Extracting grammatical gender from morphology[cite: 19, 27]
    for t in doc:
        gender = t.morph.get("Gender")
        if t.pos_ in ["PRON", "DET"]:
            if "Fem" in gender: 
                pos_data["feminine"]["pronouns"].append(t.text.lower())
            elif "Masc" in gender: 
                pos_data["masculine"]["pronouns"].append(t.text.lower())
        
        if t.pos_ == "NOUN":
            if "Fem" in gender: 
                pos_data["feminine"]["nouns"].append(t.text.lower())
            elif "Masc" in gender: 
                pos_data["masculine"]["nouns"].append(t.text.lower())

    # Raw statistical majority count[cite: 27]
    f_count = len(pos_data["feminine"]["pronouns"]) + len(pos_data["feminine"]["nouns"])
    m_count = len(pos_data["masculine"]["pronouns"]) + len(pos_data["masculine"]["nouns"])
    
    verdict = "Feminino" if f_count > m_count else "Masculino" if m_count > f_count else "Ambos/Neutro"

    # Named Entity Recognition for person names[cite: 15, 27]
    entities = ner_model(text[:512])
    return {
        "veredito_wikineural": verdict,
        "pos_analysis": pos_data,
        "detected_names": [
            {"name": e['word'], "score": round(float(e['score']), 3)} 
            for e in entities if e['entity_group'] == 'PER'
        ]
    }

# --- EXECUTION LOOP ---
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Processing WikiNeural Standard: {filename}")
    input_path = os.path.join(INPUT_DIR, filename)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for art in data:
        # Title and body combined for full context[cite: 19, 27]
        full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
        art['analise_wikineural'] = analyze_wikineural(full_text)
        
    # Save output to dedicated tool folder[cite: 6]
    output_path = os.path.join(OUTPUT_DIR, f"wikineural_{filename}")
    with open(output_path, 'w', encoding='utf-8') as wf:
        json.dump(data, wf, indent=4, ensure_ascii=False)

print("\nWikiNeural Standard Processing Completed!")