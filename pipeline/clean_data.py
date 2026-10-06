import json
import os
import shutil
import re

# Updated paths for the new project organization
input_folder = "data/raw/articles"
output_folder = "data/cleaned"

# Create output folder without deleting existing content (supports resume)
os.makedirs(output_folder, exist_ok=True)

# Boilerplate phrases common in news archives
junk_boilerplate = [
    "últimas 7 edições", "newsletter", "receba os principais destaques",
    "your email", "termos & condições", "política de privacidade",
    "exclusivo a bola 3d", "desconto de tempo", "mais galerias",
    "v v e d", "j pts", "clube j pts", "histórico das classificações",
    "espaço universidade", "símbolos desportivos", "mundo dos guarda-redes"
]

# Title keywords that indicate non-relevant content
junk_titles = [
    "classificação", "sondagem", "direto", "on-line", "vídeo",
    "fotogaleria", "rubricas", "símbolos desportivos"
]


# ============================================================
# SOURCE/PERIOD-SPECIFIC CLEANING
# ============================================================

def clean_abola_title_2000_2003(title):
    """Strips the A Bola 2000-2003 domain prefix and edition suffix from titles."""
    # Remove "(http://)www.abola.pt - " from the start
    title = re.sub(r'^(http://)?(www\.)?abola\.pt\s*-\s*', '', title, flags=re.IGNORECASE)
    # Remove "(edição de ...)" from the end
    title = re.sub(r'\s*\([^)]*edição[^)]*\)\s*$', '', title, flags=re.IGNORECASE)
    return title.strip()


def clean_abola_body_2000_2003(body, original_title):
    """Removes the title repeated at the start of the body (A Bola 2000-2003 quirk)."""
    if body.startswith(original_title):
        cleaned = body[len(original_title):].strip()
        if cleaned and len(cleaned) > 20:
            return cleaned
    return body.strip()


def clean_abola_body_2012_2014(body):
    """Strips everything up to the 'A- A A+' font-size widget (A Bola 2012-2014)."""
    cleaned = re.sub(r'^.*?A-\s*A\s*A\+\s*', '', body, count=1, flags=re.DOTALL)
    return cleaned.strip() if len(cleaned) > 30 else body.strip()


def apply_source_cleaning(art):
    source = art.get('source', '')

    # Guard: ensure year is numeric to avoid comparison errors
    try:
        year = int(art.get('year', 0))
    except (ValueError, TypeError):
        year = 0

    title  = art.get('title', '')
    body   = art.get('body_text', '')

    if 'abola.pt' in source:
        if 2000 <= year <= 2003:
            original_title = title  # keep original to clean body
            art['title']     = clean_abola_title_2000_2003(title)
            art['body_text'] = clean_abola_body_2000_2003(body, original_title)
        elif 2012 <= year <= 2014:
            art['body_text'] = clean_abola_body_2012_2014(body)

    return art


# ============================================================
# GENERIC CLEANING FUNCTIONS
# ============================================================

def truncate_noise(text):
    """
    Cuts the text when it encounters indicators of menus, footers,
    or external advertising.
    """
    if not text:
        return ""

    stoppers = [
        "Últimas Notícias", "Leia também", "Newsletter",
        "Siga-nos no Facebook", "Os comentários estão desactivados",
        "Record no Google News", "Partilhar no Facebook",
        "MOTO GP", "WRC", "Fórmula 1", "Rally", "Motociclismo",
        "ROMA  Deivid no Chelsea", "SPORTING  Chermiti"
    ]

    for phrase in stoppers:
        if phrase in text:
            text = text.split(phrase)[0]

    return text.strip()


# ============================================================
# MAIN PIPELINE
# ============================================================

print(f"{'File':<45} | {'Original':<10} | {'Cleaned':<10}")
print("-" * 70)

total_original = 0
total_unique = 0

if not os.path.exists(input_folder):
    print(f"Error: Folder '{input_folder}' not found.")
else:
    for file in os.listdir(input_folder):
        if not file.endswith(".json"):
            continue
            
        # Only process known sources
        fontes_validas = ("abolapt_", "ojogopt_", "recordpt_", "sapo_", "zapaeiou_",
                          "noticiasaominuto_", "euronews_", "flashscore_")
        if not file.startswith(fontes_validas):
            continue
            
        if "_processed" in file:
            continue

        # Resume: skip files already present in output
        output_path = os.path.join(output_folder, file)
        if os.path.exists(output_path):
            # Count toward totals without reprocessing
            with open(output_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            total_unique += len(existing)
            with open(os.path.join(input_folder, file), 'r', encoding='utf-8') as f:
                orig = json.load(f)
            total_original += len(orig) if isinstance(orig, list) else len(list(orig.values()))
            print(f"{file:<45} | {'(done)':<10} | {len(existing):<10}")
            continue

        with open(os.path.join(input_folder, file), "r", encoding="utf-8") as f:
            data = json.load(f)

        # Guard: convert dict-type files to list
        if isinstance(data, dict):
            data = list(data.values())

        total_original += len(data)
        unique_articles = {}

        for art in data:
            # Skip non-dict entries (malformed data)
            if not isinstance(art, dict):
                continue

            # 1. Source/period-specific cleaning
            art = apply_source_cleaning(art)

            title  = art.get('title', '').strip()
            body   = art.get('body_text', '').strip()
            source = art.get('source', 'unknown')

            # 2. Remove generic noise (menus, footers)
            body = truncate_noise(body)
            
            # 3. If title equals body_text, clear the body (set to null)
            if title and body and title.lower() == body.lower():
                body = None
                art['body_text'] = None
            else:
                art['body_text'] = body

            # Safe variable for filters when body is None
            body_text_for_filter = body if body else ""

            # 4. Quality filters
            is_boilerplate = any(term in body_text_for_filter.lower() for term in junk_boilerplate)
            is_junk_title  = any(term in title.lower() for term in junk_titles)
            digit_ratio    = sum(c.isdigit() for c in body_text_for_filter) / (len(body_text_for_filter) + 1)

            # Only process if body > 200 chars OR body was set to None
            is_body_valid = (body is None) or (len(body) > 200)

            if (len(title) > 20
                    and is_body_valid
                    and not is_boilerplate
                    and not is_junk_title
                    and digit_ratio < 0.30):

                # 5. Deduplicate by source + title
                title_key = f"{source}_{title.lower()}"

                if title_key not in unique_articles:
                    unique_articles[title_key] = art
                else:
                    # Keep the version with the longer body (guarded against null)
                    current_body_len = len(body) if body else 0
                    existing_body = unique_articles[title_key].get('body_text')
                    existing_body_len = len(existing_body) if existing_body else 0
                    
                    if current_body_len > existing_body_len:
                        unique_articles[title_key] = art

        cleaned_list = list(unique_articles.values())
        total_unique += len(cleaned_list)

        print(f"{file:<45} | {len(data):<10} | {len(cleaned_list):<10}")

        if cleaned_list:
            with open(os.path.join(output_folder, file), "w", encoding="utf-8") as out:
                json.dump(cleaned_list, out, indent=4, ensure_ascii=False)

print("-" * 70)
print(f"TOTAL: {total_original} raw -> {total_unique} cleaned and unique items.")