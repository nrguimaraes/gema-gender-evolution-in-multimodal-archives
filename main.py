import logging
import os
import json
import time
import random

from src.crawlers.linkExtractor import get_past_urls, save_links_to_json
from src.crawlers.articleExtractor import getArticle

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

FOLDERS = {
    "links": "data/raw/links",
    "articles": "data/raw/articles"
}

for folder in FOLDERS.values():
    if not os.path.exists(folder): 
        os.makedirs(folder)

# SOURCE LIST
source_links = [
    "abola.pt",
    "record.pt",
    "ojogo.pt",
    "desporto.sapo.pt",
    "zap.aeiou.pt/noticias/desporto",
    "www.noticiasaominuto.com/desporto",
    "https://pt.euronews.com/noticias/desporto",
    "https://www.flashscore.pt/noticias/"
]
years = list(range(1998, 2025))

print("\n--- PHASE 1: LINK RECOVERY ---")
for url in source_links:
    # Sanitize name for filenames
    clean_name = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "")
    for year in years:
        link_file = os.path.join(FOLDERS["links"], f"{clean_name}_{year}.json")
        
        if os.path.exists(link_file): 
            continue
        
        print(f"Searching: {url} ({year})...", end=" ", flush=True)
        links = get_past_urls(year, url)
        if links:
            # Save links to the new raw path
            save_links_to_json(links, url, year, FOLDERS["links"])
            print(f"Success ({len(links)} links found).")
        else:
            print("No links found.")
        time.sleep(1)

print("\n--- PHASE 2: DEDUPLICATED CONTENT EXTRACTION ---")
link_files = [f for f in os.listdir(FOLDERS["links"]) if f.endswith('.json')]

for file in link_files:
    # Output path adjusted to data/raw/articles[cite: 6]
    output_path = os.path.join(FOLDERS["articles"], file)
    processed_data = []
    seen_titles = set() # Per-file title set to prevent internal duplicates

    if os.path.exists(output_path):
        with open(output_path, "r", encoding='utf-8') as f:
            try: 
                processed_data = json.load(f)
                seen_titles = {d['title'] for d in processed_data if 'title' in d}
            except: 
                processed_data = []

    print(f"\n>>> Processing: {file}")
    with open(os.path.join(FOLDERS["links"], file), "r", encoding='utf-8') as js:
        links_data = json.load(js)
        
        for i, entry in enumerate(links_data):
            # Skip if link was already processed
            if any(d['link'] == entry['link'] for d in processed_data): 
                continue

            print(f"    [{i+1}/{len(links_data)}] Fetching content...", end=" ", flush=True)
            time.sleep(random.uniform(1.5, 3.0)) # Throttling for archive stability
            
            try:
                # Core extractor logic remains the same[cite: 22]
                res = getArticle(entry["link"], entry["year"], entry["source"], logger)
                if res:
                    new_entries = 0
                    for r in res:
                        # TITLE DEDUPLICATION: Prevents noise from O Jogo 2020 etc.
                        if r['title'] in seen_titles: 
                            continue
                        
                        item = entry.copy()
                        item.update(r)
                        processed_data.append(item)
                        seen_titles.add(r['title'])
                        new_entries += 1
                    
                    with open(output_path, "w", encoding='utf-8') as out:
                        json.dump(processed_data, out, indent=4, ensure_ascii=False)
                    print(f"SUCCESS (+{new_entries} unique items)")
                else:
                    print("SKIPPED (Empty/Filtered)")
            except Exception as e:
                print(f"ERROR: {e}")

print("\nPIPELINE COMPLETED.")