import os
import json
import stanza

# --- CONFIGURATION ---
INPUT_DIR = "data/cleaned"
# Dedicated output folder for the baseline Stanza results
OUTPUT_DIR = "data/processed/processed_stanza"
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

print("Loading Stanza (Morphology Pipeline)...")
# Processors focus on tokenization, multi-word tokens, and part-of-speech tagging[cite: 25]
nlp = stanza.Pipeline('pt', processors='tokenize,mwt,pos,lemma', download_method=None)

def analyze_stanza(text):
    """
    Analyzes text using Stanza to count occurrences of feminine and masculine 
    morphological features in pronouns and nouns[cite: 25].
    """
    doc = nlp(text[:600]) # Focused on the lead for classification[cite: 25]
    analysis = {
        "feminine": {"pronouns": [], "nouns": []}, 
        "masculine": {"pronouns": [], "nouns": []}, 
        "veredito_stanza": "Neutro"
    }
    f_count = 0
    m_count = 0

    for sentence in doc.sentences:
        for word in sentence.words:
            # Extract gender features from morphological analysis[cite: 25]
            feats = word.feats if word.feats else ""
            gender = "F" if "Gender=Fem" in feats else "M" if "Gender=Masc" in feats else None
            
            if gender:
                if gender == "F":
                    f_count += 1
                    if word.upos in ["PRON", "DET"]:
                        analysis["feminine"]["pronouns"].append(word.text.lower())
                    elif word.upos == "NOUN":
                        analysis["feminine"]["nouns"].append(word.text.lower())
                else:
                    m_count += 1
                    if word.upos in ["PRON", "DET"]:
                        analysis["masculine"]["pronouns"].append(word.text.lower())
                    elif word.upos == "NOUN":
                        analysis["masculine"]["nouns"].append(word.text.lower())

    # Final verdict based on raw statistical majority[cite: 25]
    if f_count > m_count: 
        analysis["veredito_stanza"] = "Feminino"
    elif m_count > f_count: 
        analysis["veredito_stanza"] = "Masculino"

    return analysis

# --- EXECUTION LOOP ---
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Processing Stanza (Morphology Only): {filename}")
    input_path = os.path.join(INPUT_DIR, filename)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for art in data:
        # Full text provides context for the morphological analyzer[cite: 25]
        full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
        art['analise_stanza'] = analyze_stanza(full_text)
        
    # Save to the specific processed folder[cite: 6]
    output_path = os.path.join(OUTPUT_DIR, f"stanza_{filename}")
    with open(output_path, 'w', encoding='utf-8') as wf:
        json.dump(data, wf, indent=4, ensure_ascii=False)

print("\nStanza Morphology Processing Completed!")