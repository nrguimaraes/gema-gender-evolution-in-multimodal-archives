import json
import os
from pymongo import MongoClient

# Define paths
BASE_PATH = os.getcwd()
VISION_JSON_PATH = os.path.join(BASE_PATH, 'data/processed/image_analysis/gender_vision_results_retinaface.json')

def import_to_mongo():
    print(">>> Connecting to MongoDB...")
    # MongoDB connection via WSL2 virtual gateway
    client = MongoClient('mongodb://172.17.16.1:27017/', serverSelectionTimeoutMS=5000)
    db = client['estagio_desporto']
    collection = db['covers_analysis']

    if not os.path.exists(VISION_JSON_PATH):
        print(f"Error: Could not find {VISION_JSON_PATH}")
        return

    print(">>> Loading JSON data...")
    # Load the RetinaFace results file
    with open(VISION_JSON_PATH, 'r', encoding='utf-8') as f:
        vision_data = json.load(f)

    mongo_docs = []
    for filename, content in vision_data.items():
        # Extract metadata from the filename (e.g. "a-bola_2016-05-21.jpg")
        parts = filename.replace(".jpg", "").split("_")
        if len(parts) >= 2:
            source = parts[0]
            date_str = parts[1]
            year = int(date_str.split("-")[0])
            
            doc = {
                "_id": filename,
                "source": source,
                "date": date_str,
                "year": year,
                "faces_detected": content.get("full_image", [])  # face list with coverage percentages
            }
            mongo_docs.append(doc)

    print(f">>> Inserting {len(mongo_docs)} records into MongoDB...")
    for doc in mongo_docs:
        collection.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)

    print(">>> SUCCESS! Data synchronized in 'covers_analysis' collection.")

if __name__ == "__main__":
    import_to_mongo()