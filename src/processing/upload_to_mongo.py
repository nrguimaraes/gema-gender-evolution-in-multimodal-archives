import os
import sys
import json
import pymongo

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# --- NETWORK CONFIGURATION ---
WIN_IP = "172.17.16.1"
client = pymongo.MongoClient(f'mongodb://{WIN_IP}:27017/', serverSelectionTimeoutMS=5000)
db = client['estagio_desporto']

col_raw = db['articles_raw']       # Raw articles (archive/backup)
col_final = db['articles_final']   # Classified articles (production/analysis)

RAW_FOLDER = os.path.join(PROJECT_ROOT, "data", "enriched")
CLASSIFIED_FOLDER = os.path.join(PROJECT_ROOT, "data", "processed", "processed_wikineural_final")


def upload_to_mongo():
    """
    Uploads to MongoDB:
      1. Raw articles (from data/enriched) → articles_raw collection
      2. Classified articles (from data/processed/processed_wikineural_final) → articles_final collection
    """

    # --- 1. Upload raw articles ---
    if not os.path.exists(RAW_FOLDER):
        print(f"Error: Folder '{RAW_FOLDER}' not found.")
    else:
        raw_files = [f for f in os.listdir(RAW_FOLDER) if f.endswith('.json')]
        raw_count = 0

        for file in raw_files:
            with open(os.path.join(RAW_FOLDER, file), 'r', encoding='utf-8') as f:
                articles = json.load(f)

            for art in articles:
                art_id = art.get('link')
                if not art_id:
                    continue
                art['_id'] = art_id
                col_raw.update_one({"_id": art_id}, {"$set": art}, upsert=True)
                raw_count += 1

        print(f"articles_raw: {raw_count} documents synced from {len(raw_files)} files.")

    # --- 2. Upload classified articles ---
    if not os.path.exists(CLASSIFIED_FOLDER):
        print(f"Error: Folder '{CLASSIFIED_FOLDER}' not found.")
        print("Run classify_articles.py first to generate the classified files.")
    else:
        classified_files = [f for f in os.listdir(CLASSIFIED_FOLDER) if f.endswith('.json')]
        classified_count = 0

        for file in classified_files:
            with open(os.path.join(CLASSIFIED_FOLDER, file), 'r', encoding='utf-8') as f:
                articles = json.load(f)

            for art in articles:
                art_id = art.get('link')
                if not art_id:
                    continue
                art['_id'] = art_id
                col_final.update_one({"_id": art_id}, {"$set": art}, upsert=True)
                classified_count += 1

        print(f"articles_final: {classified_count} documents synced from {len(classified_files)} files.")

    print("\nUpload to MongoDB complete.")


if __name__ == "__main__":
    upload_to_mongo()