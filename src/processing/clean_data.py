import json
import os
import shutil
import re

# Updated paths for the new project organization
input_folder = "data/raw/articles"
output_folder = "data/cleaned"

# Reset the output folder to ensure a fresh cleanup[cite: 16]
if os.path.exists(output_folder):
    shutil.rmtree(output_folder)
os.makedirs(output_folder)

# Boilerplate phrases common in news archives[cite: 16]
junk_boilerplate = [
    "últimas 7 edições", "newsletter", "receba os principais destaques",
    "your email", "termos & condições", "política de privacidade",
    "exclusivo a bola 3d", "desconto de tempo", "mais galerias",
    "v v e d", "j pts", "clube j pts", "histórico das classificações",
    "espaço universidade", "símbolos desportivos", "mundo dos guarda-redes"
]

# Title keywords that indicate non-relevant content[cite: 16]
junk_titles = [
    "classificação", "sondagem", "direto", "on-line", "vídeo", 
    "fotogaleria", "rubricas", "símbolos desportivos"
]

def truncate_noise(text):
    """
    Cuts the text when it encounters indicators of menus, footers, 
    or external advertising[cite: 16].
    """
    if not text: return ""
    
    # Markers indicating the news has ended and "garbage" text starts[cite: 16]
    stoppers = [
        "Últimas Notícias", "Leia também", "Newsletter", 
        "Siga-nos no Facebook", "Os comentários estão desactivados",
        "Record no Google News", "Partilhar no Facebook",
        "MOTO GP", "WRC", "Fórmula 1", "Rally", "Motociclismo",
        "ROMA  Deivid no Chelsea", "SPORTING  Chermiti" 
    ]
    
    for phrase in stoppers:
        if phrase in text:
            # Keeps only the content before the stopping phrase[cite: 16]
            text = text.split(phrase)[0]
            
    return text.strip()

print(f"{'File':<45} | {'Original':<10} | {'Cleaned':<10}")
print("-" * 70)

total_original = 0
total_unique = 0

# Check if input folder exists before processing
if not os.path.exists(input_folder):
    print(f"Error: Folder '{input_folder}' not found.")
else:
    for file in os.listdir(input_folder):
        if file.endswith(".json"):
            with open(os.path.join(input_folder, file), "r", encoding="utf-8") as f:
                data = json.load(f)
            
            total_original += len(data)
            unique_articles = {}

            for art in data:
                title = art.get('title', '').strip()
                body = art.get('body_text', '').strip()
                source = art.get('source', 'unknown')

                # 1. Truncate noise[cite: 16]
                body = truncate_noise(body)
                art['body_text'] = body 

                # 2. Check for boilerplate and junk titles[cite: 16]
                is_boilerplate = any(term in body.lower() for term in junk_boilerplate)
                is_junk_title = any(term in title.lower() for term in junk_titles)
                
                # 3. Calculate digit ratio to filter out tables/results[cite: 16]
                digit_ratio = sum(c.isdigit() for c in body) / (len(body) + 1)
                
                # --- QUALITY FILTERS ---[cite: 16]
                # We keep body > 200 to ensure enough text for NLP models[cite: 16]
                if len(title) > 20 and len(body) > 200 and not is_boilerplate and not is_junk_title and digit_ratio < 0.30:
                    
                    # Deduplication (Source + Title)[cite: 16]
                    title_key = f"{source}_{title.lower()}"
                    
                    if title_key not in unique_articles:
                        unique_articles[title_key] = art
                    else:
                        # If duplicate, keep the version with the longer body text[cite: 16]
                        if len(body) > len(unique_articles[title_key].get('body_text', '')):
                            unique_articles[title_key] = art

            cleaned_list = list(unique_articles.values())
            total_unique += len(cleaned_list)
            
            print(f"{file:<45} | {len(data):<10} | {len(cleaned_list):<10}")
            
            if cleaned_list:
                with open(os.path.join(output_folder, file), "w", encoding="utf-8") as out:
                    json.dump(cleaned_list, out, indent=4, ensure_ascii=False)

print("-" * 70)
print(f"TOTAL: {total_original} raw -> {total_unique} cleaned and unique items.")