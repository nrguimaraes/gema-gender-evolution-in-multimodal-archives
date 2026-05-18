import os
import json
import spacy
from transformers import pipeline
from src.utils.wikidata_api import consultar_wikidata_genero 

# --- ENVIRONMENT CONFIGURATION ---
# Using the ENRICHED folder from the previous step as input
INPUT_DIR = "data/enriched" 
OUTPUT_DIR = "data/processed/processed_wikineural_weights"

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

# --- MODEL LOADING ---
print("Loading SpaCy and WikiNeural...")
nlp = spacy.load("pt_core_news_lg") 
ner_model = pipeline("ner", model="Babelscape/wikineural-multilingual-ner", aggregation_strategy="simple")

def analyze_wikineural_weighted(text):
    """
    Using Predominance Logic:
    1. Biographical Winner (80%): The gender with more unique validated names takes the full weight.
    2. Grammatical Context (20%): Pronouns and nouns serve as a tie-breaker or context provider.
    """
    doc = nlp(text)
    
    # 1. GRAMMATICAL EXTRACTION
    pos_data = {
        "feminine": {"pronouns": [], "nouns": []}, 
        "masculine": {"pronouns": [], "nouns": []}
    }
    
    for t in doc:
        gender = t.morph.get("Gender")
        if t.pos_ in ["PRON", "DET"]:
            if "Fem" in gender:
                pos_data["feminine"]["pronouns"].append(t.text.lower())
            elif "Masc" in gender:
                pos_data["masculine"]["pronouns"].append(t.text.lower())
        elif t.pos_ == "NOUN":
            if "Fem" in gender:
                pos_data["feminine"]["nouns"].append(t.text.lower())
            elif "Masc" in gender:
                pos_data["masculine"]["nouns"].append(t.text.lower())

    # 2. NER & WIKIDATA VALIDATION
    entities = ner_model(text[:1000]) 
    raw_names = list(set([e['word'] for e in entities if e['entity_group'] == 'PER' and len(e['word']) > 3]))
    
    protagonists = {"feminine": [], "masculine": []}
    for name in raw_names:
        gender_wiki = consultar_wikidata_genero(name)
        if gender_wiki == "Feminino":
            protagonists["feminine"].append(name)
        elif gender_wiki == "Masculino":
            protagonists["masculine"].append(name)

    # 3. BIOGRAPHICAL SCORE (Proportional Logic - 80% Weight)
    f_names_count = len(protagonists["feminine"])
    m_names_count = len(protagonists["masculine"])
    total_names = f_names_count + m_names_count
    
    bio_score_f = 0.0
    bio_score_m = 0.0
    
    # New logic suggested by the professor: Proportionality
    if total_names > 0:
        bio_score_f = (f_names_count / total_names) * 0.80
        bio_score_m = (m_names_count / total_names) * 0.80

    # 4. GRAMMATICAL SCORE (Contextual Tie-breaker - 20% Weight)
    f_signals = len(pos_data["feminine"]["pronouns"]) + len(pos_data["feminine"]["nouns"])
    m_signals = len(pos_data["masculine"]["pronouns"]) + len(pos_data["masculine"]["nouns"])
    total_signals = f_signals + m_signals
    
    gram_score_f = 0.0
    gram_score_m = 0.0
    
    if total_signals > 0:
        gram_score_f = (f_signals / total_signals) * 0.20
        gram_score_m = (m_signals / total_signals) * 0.20

    # 5. FINAL CALCULATION
    total_f = bio_score_f + gram_score_f
    total_m = bio_score_m + gram_score_m

    if total_f > total_m:
        verdict = "Feminino"
    elif total_m > total_f:
        verdict = "Masculino"
    else:
        verdict = "Neutro/Equilibrado"

    return {
        "verdict": verdict,
        "confidence_scores": {
            "F": round(total_f, 4), 
            "M": round(total_m, 4),
            "signals_count": {"bio_f": f_names_count, "bio_m": m_names_count, "gram_total": total_signals}
        },
        "details": {
            "protagonists": protagonists,
            "grammatical_data": pos_data
        }
    }

# --- PROCESSING LOOP ---
# Processing ONLY Abola files for the years 2017 and 2023 from data/enriched
target_years = ['2017', '2023']
target_source = 'abola'

# Filter: must be JSON, must contain 'ENRICHED', must contain 'abola' and one of the target years
files = [
    f for f in os.listdir(INPUT_DIR) 
    if f.endswith('.json') 
    and 'ENRICHED' in f 
    and target_source in f.lower() 
    and any(year in f for year in target_years)
]

if not files:
    print(f"No enriched files found for {target_source} in years {target_years}.")
else:
    for filename in files:
        print(f"\n>>> Applying weights to: {filename}")
        input_path = os.path.join(INPUT_DIR, filename)
        
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for art in data:
            # Combine title and body for full context analysis
            full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
            # Apply the optimized Predominance Logic (80/20)
            art['classification_analysis'] = analyze_wikineural_weighted(full_text)

        # Save to the processed folder with a clear prefix
        output_filename = f"WEIGHTED_{filename}"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        with open(output_path, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=4, ensure_ascii=False)
            
        print(f"Finished: {output_filename} saved to {OUTPUT_DIR}")

print("\nWeighted classification for A Bola (2017/2023) finished!")