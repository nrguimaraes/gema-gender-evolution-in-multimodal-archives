import os
import sys
import json

# Set project root so Python can find the 'classifiers' package.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from classifiers.process_wikineural_pesos import analyze_wikineural_weighted
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Check that the 'classifiers' folder is inside: {PROJECT_ROOT}")
    sys.exit(1)

INPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "enriched")
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "processed", "processed_wikineural_final")

def run_classification():
    """
    Classifies enriched articles with WikiNeural gender analysis.
    Saves results to JSON and skips files that are already classified.
    """
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Folder '{INPUT_FOLDER}' not found.")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.json')]

    if not files:
        print(f"No JSON files found in '{INPUT_FOLDER}'.")
        return

    for file in files:
        output_path = os.path.join(OUTPUT_FOLDER, file)

        # Skip files already classified
        if os.path.exists(output_path):
            print(f"--- Skipping: {file} (already classified) ---")
            continue

        print(f"--- Classifying: {file} ---")
        file_path = os.path.join(INPUT_FOLDER, file)

        with open(file_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)

        classified_articles = []

        for i, art in enumerate(articles):
            art_id = art.get('link')
            if not art_id:
                continue

            # Gender analysis on title + body
            full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
            analysis = analyze_wikineural_weighted(full_text)

            classified_doc = art.copy()
            classified_doc['gender_analysis'] = analysis
            classified_articles.append(classified_doc)

            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(articles)} articles processed...")

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(classified_articles, f_out, ensure_ascii=False, indent=4)
            
        print(f"Done: {file}\n")

if __name__ == "__main__":
    run_classification()