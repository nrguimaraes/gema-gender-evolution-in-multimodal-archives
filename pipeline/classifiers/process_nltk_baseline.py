import os
import json
import nltk
from nltk.tokenize import word_tokenize

# NLTK is a classic NLP tool based on rules and dictionaries.
# Logic:
# 1. Tokenize text into a list of words.
# 2. Compare each word against a predefined list of gendered terms.
# 3. Sum the occurrences.
# 4. Determine gender based on raw statistical majority.

# Download required NLTK resources
nltk.download('punkt')
nltk.download('punkt_tab')

# --- CONFIGURATION ---
INPUT_DIR = "data/cleaned"
# Dedicated output folder for this classifier
OUTPUT_DIR = "data/processed/processed_nltk"
TARGET_YEARS = ['2017', '2023']

if not os.path.exists(OUTPUT_DIR): 
    os.makedirs(OUTPUT_DIR)

# Lexical comparison patterns[cite: 16]
LEXICO = {
    "feminino": ["ela", "elas", "esta", "estas", "aquela", "a", "as", "jogadora", "atleta", "treinadora", "campeã", "seleção", "equipa"],
    "masculino": ["ele", "eles", "este", "estes", "aquele", "o", "os", "jogador", "atleta", "treinador", "campeão", "selecionador", "clube"]
}

def analyze_with_nltk(text):
    """
    Performs a simple lexical count to determine the dominant gender[cite: 16].
    """
    tokens = [t.lower() for t in word_tokenize(text)]

    counts = {"feminino": 0, "masculino": 0}
    pistas = {"feminino": [], "masculino": []}

    for token in tokens:
        if token in LEXICO["feminino"]:
            counts["feminino"] += 1
            pistas["feminino"].append(token)
        if token in LEXICO["masculino"]:
            counts["masculino"] += 1
            pistas["masculino"].append(token)

    if counts["feminino"] > counts["masculino"]: 
        veredito = "Feminino"
    elif counts["masculino"] > counts["feminino"]: 
        veredito = "Masculino"
    else: 
        veredito = "Ambos/Neutro"

    return {"veredito_nltk": veredito, "counts": counts, "clues": pistas}

# --- EXECUTION LOOP ---
files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and 'abola' in f.lower() and any(y in f for y in TARGET_YEARS)]

for filename in files:
    print(f"\n>>> Processing NLTK Baseline: {filename}")
    input_path = os.path.join(INPUT_DIR, filename)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for art in data:
        # Combine title and body text for analysis[cite: 16]
        full_text = f"{art.get('title', '')} {art.get('body_text', '')}"
        art['analise_nltk'] = analyze_with_nltk(full_text)
        
    # Save output to the dedicated folder[cite: 6]
    output_path = os.path.join(OUTPUT_DIR, f"nltk_{filename}")
    with open(output_path, 'w', encoding='utf-8') as wf:
        json.dump(data, wf, indent=4, ensure_ascii=False)

print("\nNLTK Baseline Processing Completed!")