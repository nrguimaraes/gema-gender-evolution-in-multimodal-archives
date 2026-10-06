import os
import sys
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROCESSING_DIR = os.path.abspath(os.path.dirname(__file__))
for _p in (PROJECT_ROOT, PROCESSING_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from classifiers.process_wikineural_pesos import analyze_wikineural_weighted
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Check that the 'classifiers' folder is inside: {PROJECT_ROOT}")
    sys.exit(1)

INPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "enriched")
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "processed", "processed_wikineural_final")

# Conservative worker count: enough to parallelize Wikidata I/O without hammering the API.
# Once the local cache (gender_cache.json) is warm, raise this to 8-10 if desired.
MAX_WORKERS = 5

def _classify_article(art):
    """Classifies a single article. Returns None if the article has no link."""
    if not art.get('link'):
        return None
    full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
    classified_doc = art.copy()
    classified_doc['gender_analysis'] = analyze_wikineural_weighted(full_text)
    return classified_doc

def _classify_file(file):
    """
    Classifies all articles in one enriched JSON file using a thread pool.
    Preserves original article order. Returns (file, classified_articles, elapsed_seconds).
    """
    output_path = os.path.join(OUTPUT_FOLDER, file)
    if os.path.exists(output_path):
        print(f"--- Skipping: {file} (already classified) ---")
        return file, None, 0

    file_path = os.path.join(INPUT_FOLDER, file)
    with open(file_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    print(f"--- Classifying: {file} ({len(articles)} articles, {MAX_WORKERS} workers) ---")
    start = time.time()

    # Submit all articles, preserving index so we can restore order afterwards
    results = [None] * len(articles)
    counter = {"done": 0}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {executor.submit(_classify_article, art): i for i, art in enumerate(articles)}

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

            with lock:
                counter["done"] += 1
                done = counter["done"]

            if done % 50 == 0:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                remaining = (len(articles) - done) / rate if rate > 0 else 0
                print(f"  {done}/{len(articles)} articles — {rate:.1f} art/s — ~{remaining/60:.1f} min left")

    classified_articles = [r for r in results if r is not None]
    elapsed = time.time() - start
    return file, classified_articles, elapsed

def run_classification():
    """
    Classifies all enriched articles with WikiNeural gender analysis.
    Uses a ThreadPoolExecutor per file to parallelize Wikidata lookups.
    Skips files that are already classified. Original article order is preserved.
    """
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Folder '{INPUT_FOLDER}' not found.")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.json')]
    if not files:
        print(f"No JSON files found in '{INPUT_FOLDER}'.")
        return

    total_start = time.time()

    for file in files:
        file, classified_articles, elapsed = _classify_file(file)

        if classified_articles is None:
            continue

        output_path = os.path.join(OUTPUT_FOLDER, file)
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(classified_articles, f_out, ensure_ascii=False, indent=4)

        print(f"Done: {file} — {len(classified_articles)} articles in {elapsed:.1f}s\n")

    total = time.time() - total_start
    print(f"All files classified in {total/60:.1f} minutes.")

if __name__ == "__main__":
    run_classification()
