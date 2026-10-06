import os
import json
import pymongo
from classifiers.process_wikineural_pesos import analyze_wikineural_weighted

# --- NETWORK CONFIGURATION ---
# Note: When operating within WSL2, 'localhost' refers to the Linux container.
# The virtual gateway IP (172.17.16.1) is used to bridge the connection 
# to the MongoDB instance hosted on the Windows host.
WIN_IP = "172.17.16.1"
client = pymongo.MongoClient(f'mongodb://{WIN_IP}:27017/', serverSelectionTimeoutMS=5000)
db = client['estagio_desporto']

# --- DATA PERSISTENCE STRATEGY ---
# Maintaining separate collections ensures raw data integrity while providing 
# a dedicated space for NLP-enriched records.
col_raw = db['articles_raw']    # Original enriched articles (Archive/Backup)
col_final = db['articles_final'] # Classified articles (Production/Analysis)

INPUT_FOLDER = "data/enriched"

def run_production_pipeline():
    """
    Executes the full text-processing pipeline:
    1. Loads local JSON files from the enriched directory.
    2. Synchronizes raw article data to MongoDB.
    3. Performs weighted NLP gender analysis on combined title and body text.
    4. Persists the final classified documents to the production collection.
    """
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Source directory '{INPUT_FOLDER}' not found.")
        return

    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.json')]
    
    for file in files:
        print(f"--- Synchronizing and Analyzing: {file} ---")
        file_path = os.path.join(INPUT_FOLDER, file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
            
            for art in articles:
                # Use the unique article URL as the primary key (_id) to prevent duplicates
                art_id = art.get('link')
                if not art_id:
                    continue
                
                # 1. Persist the raw version to the archival collection
                art['_id'] = art_id
                col_raw.update_one({"_id": art_id}, {"$set": art}, upsert=True)
                
                # 2. Execute the optimized biographical and grammatical analysis
                # The analysis combines the title and body text for holistic context.
                full_text = f"{art.get('title', '')}. {art.get('body_text', '')}"
                analysis = analyze_wikineural_weighted(full_text)
                
                # 3. Augment article data with classification results and store in the final collection
                classified_doc = art.copy()
                classified_doc['gender_analysis'] = analysis
                col_final.update_one({"_id": art_id}, {"$set": classified_doc}, upsert=True)

    print("\nSUCCESS: All enriched sources have been synchronized and classified in MongoDB.")

if __name__ == "__main__":
    run_production_pipeline()