import os
import json
import re

# --- CONFIGURATION ---
INPUT_DIR = "data/cleaned"
OUTPUT_DIR = "data/enriched"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def extract_date_from_text(text):
    """
    Attempts to find a date within the article text using multiple patterns.
    Returns the date in YYYY-MM-DD format or None.
    """
    months_map = {
        'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
        'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
        'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
    }

    text_lower = text.lower()

    # Pattern 1: Full Portuguese date (e.g., "6 de julho de 2017")
    # This ensures accuracy for all months in a journalistic context
    date_text_pattern = r"(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})"
    text_match = re.search(date_text_pattern, text_lower)
    if text_match:
        day, month_name, year = text_match.groups()
        if month_name in months_map:
            return f"{year}-{months_map[month_name]}-{day.zfill(2)}"

    # Pattern 2: Numeric date (e.g., "06/07/2017" or "2017-07-06")
    numeric_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if numeric_match:
        d, m, y = numeric_match.groups()
        # Basic validation to handle DD/MM vs MM/DD if necessary
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        
    return None

def process_enrichment_dates():
    """
    Processes all cleaned news files to standardize publication dates.
    Uses a hierarchy: Text Content > URL Timestamp (Fallback).
    """
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
    
    for filename in files:
        print(f"Enriching dates for: {filename}")
        with open(os.path.join(INPUT_DIR, filename), "r", encoding="utf-8") as f:
            data = json.load(f)

        for art in data:
            # 1. Try to extract from text first (Highest precision)
            text_content = f"{art.get('title', '')} {art.get('body_text', '')}"
            found_date = extract_date_from_text(text_content)
            
            if found_date:
                art['publication_date'] = found_date
                art['date_extraction_method'] = "text_regex"
            else:
                # 2. Fallback: Extract from Arquivo.pt URL timestamp
                # Links usually contain /replay/YYYYMMDDHHMMSS/
                url = art.get('link', '')
                tstamp_match = re.search(r"/(\d{14})/", url)
                if tstamp_match:
                    ts = tstamp_match.group(1)
                    art['publication_date'] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    art['date_extraction_method'] = "arquivo_pt_proxy"
                else:
                    art['publication_date'] = art.get('year', 'Unknown')
                    art['date_extraction_method'] = "year_only_fallback"

        # Save to the enriched folder
        output_path = os.path.join(OUTPUT_DIR, f"{filename}")
        with open(output_path, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    process_enrichment_dates()
    print("Enrichment complete. Check data/enriched folder.")