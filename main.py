import logging
import os
import json
import time
import random

from src.crawlers.linkExtractor import get_past_urls, save_links_to_json
from src.crawlers.articleExtractor import getArticle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

FOLDERS = {
    "links":    "data/raw/links",
    "articles": "data/raw/articles",
}

for folder in FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

SOURCE_LINKS = [
    "abola.pt",
    "record.pt",
    "ojogo.pt",
    "desporto.sapo.pt",
    "zap.aeiou.pt/noticias/desporto",
    "www.noticiasaominuto.com/desporto",
    "https://pt.euronews.com/noticias/desporto",
    "https://www.flashscore.pt/noticias/",
]
YEARS = list(range(1998, 2024))


# ============================================================
# PHASE 1: LINK COLLECTION (commented out by default)
# ============================================================
# print("\n--- PHASE 1: LINK COLLECTION ---")
# for url in SOURCE_LINKS:
#     clean_name = url.replace("https://", "").replace("http://", "") \
#                     .replace("/", "_").replace(".", "")
#     for year in YEARS:
#         link_file = os.path.join(FOLDERS["links"], f"{clean_name}_{year}.json")
#         if os.path.exists(link_file):
#             continue
#         print(f"Searching: {url} ({year})...", end=" ", flush=True)
#         links = get_past_urls(year, url)
#         if links:
#             save_links_to_json(links, url, year, FOLDERS["links"])
#             print(f"OK ({len(links)} links)")
#         else:
#             print("No links found.")
#         time.sleep(1)


# ============================================================
# PHASE 2: ARTICLE EXTRACTION
# ============================================================
# Deduplication by article URL only — not by title, to avoid losing
# articles from sources with generic titles (e.g. A Bola 2004).
#
# Auto-resume: processed homepages are tracked in a parallel
# _processed.json file — if the script is interrupted it resumes
# without repeating already-processed homepages.

print("\n--- PHASE 2: ARTICLE EXTRACTION ---")

# Mapping: actual file prefix (from linkExtractor) → simple output name
FILE_PREFIX_MAP = {
    "desportosapopt":                  "sapo",
    "zapaeioupt_noticias_desporto":    "zapaeiou",
    "wwwnoticiasaominutocom_desporto": "noticiasaominuto",
    "pteuronewscom_noticias_desporto": "euronews",
    "wwwflashscorept_noticias_":       "flashcore",
}

def get_simple_name(filename):
    """Returns the simple name (e.g. 'sapo_2001') for a links file."""
    name = filename.replace('.json', '')
    # Extract year (last 4 digits after the last '_')
    year_part = name.rsplit('_', 1)[-1]
    if not year_part.isdigit() or len(year_part) != 4:
        return None
    # Check if prefix matches a known source
    for prefix, simple in FILE_PREFIX_MAP.items():
        if name.startswith(prefix):
            return f"{simple}_{year_part}"
    return None

link_files = sorted(
    f for f in os.listdir(FOLDERS["links"])
    if f.endswith('.json') and '_processed' not in f
    and get_simple_name(f) is not None
)

# Filter: only what remains — zap 2013-2024 and noticiasaominuto 2021-2024
def should_process(filename):
    name = get_simple_name(filename)
    if not name:
        return False
    prefix, year_str = name.rsplit('_', 1)
    year = int(year_str)
    if prefix == 'zapaeiou' and 2013 <= year <= 2024:
        return True
    if prefix == 'noticiasaominuto' and 2023 <= year <= 2024:
        return True
    return False

link_files = [f for f in link_files if should_process(f)]

for file in link_files:
    simple_name = get_simple_name(file)
    links_path  = os.path.join(FOLDERS["links"],    file)
    output_path = os.path.join(FOLDERS["articles"], f"{simple_name}.json")
    done_path   = os.path.join(FOLDERS["articles"], f"{simple_name}_processed.json")

    # Load already-extracted articles and seen URLs
    articles_out = []
    seen_links   = set()

    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                articles_out = json.load(f)
            seen_links = {a['link'] for a in articles_out if 'link' in a}
        except Exception:
            articles_out = []

    # Load already-processed homepages
    done_homepages = set()
    if os.path.exists(done_path):
        try:
            with open(done_path, 'r', encoding='utf-8') as f:
                done_homepages = set(json.load(f))
        except Exception:
            done_homepages = set()

    with open(links_path, 'r', encoding='utf-8') as f:
        links_data = json.load(f)

    pending = [e for e in links_data if e['link'] not in done_homepages]

    if not pending:
        print(f"  {file}: already complete ({len(links_data)} homepages, {len(articles_out)} articles)")
        continue

    print(f"\n>>> {file}: {len(pending)}/{len(links_data)} homepages pending "
          f"({len(articles_out)} articles already extracted)")

    for i, entry in enumerate(pending):
        homepage_url = entry['link']
        year         = entry['year']
        source       = entry['source']

        print(f"  [{i+1}/{len(pending)}] {homepage_url[:80]}...", end=" ", flush=True)

        time.sleep(random.uniform(1.5, 3.0))

        try:
            results = getArticle(homepage_url, year, source, logger)

            if not results:
                print("EMPTY")
                done_homepages.add(homepage_url)
                with open(done_path, 'w', encoding='utf-8') as f:
                    json.dump(list(done_homepages), f, ensure_ascii=False)
                continue

            new_count = 0
            for article in results:
                art_link = article.get('link', '')
                # Skip only if this exact URL already exists
                if art_link and art_link in seen_links:
                    continue
                articles_out.append(article)
                if art_link:
                    seen_links.add(art_link)
                new_count += 1

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(articles_out, f, indent=4, ensure_ascii=False)

            done_homepages.add(homepage_url)
            with open(done_path, 'w', encoding='utf-8') as f:
                json.dump(list(done_homepages), f, ensure_ascii=False)

            print(f"OK (+{new_count} articles | total: {len(articles_out)})")

        except ConnectionError as e:
            # 403 or inaccessible snapshot — do NOT mark as done so it retries next run
            print(f"403/INACCESSIBLE (will retry)")
        except Exception as e:
            print(f"ERROR: {e}")

print("\nPIPELINE COMPLETE.")
