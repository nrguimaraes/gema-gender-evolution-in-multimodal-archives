import json
import os
from pymongo import MongoClient, UpdateOne

# Define paths
BASE_PATH = os.getcwd()
VISION_JSON_PATH = os.path.join(BASE_PATH, 'data/processed/image_analysis/gender_vision_results_retinaface.json')

BATCH_SIZE = 5000

def import_to_mongo():
    print(">>> Connecting to MongoDB...")
    # MongoDB connection via WSL2 virtual gateway
    client = MongoClient('mongodb://172.17.16.1:27017/', serverSelectionTimeoutMS=5000)
    db = client['estagio_desporto']
    collection = db['covers_analysis']

    # --- 0. LIMPEZA DA BASE DE DADOS ANTIGA ---
    print(">>> A limpar a coleção antiga 'covers_analysis' para evitar dados fantasma...")
    collection.drop()
    print(">>> Coleção limpa! A iniciar o upload...")

    if not os.path.exists(VISION_JSON_PATH):
        print(f"Error: Could not find {VISION_JSON_PATH}")
        return

    print(">>> Loading JSON data...")
    # Load the RetinaFace results file
    with open(VISION_JSON_PATH, 'r', encoding='utf-8') as f:
        vision_data = json.load(f)

    operations = []
    count = 0

    print(f">>> Preparing {len(vision_data)} records for MongoDB...")
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
            
            # Adiciona ao lote em vez de inserir logo
            operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True))
            count += 1

            # Dispara para o MongoDB quando o lote chega aos 5000
            if len(operations) >= BATCH_SIZE:
                collection.bulk_write(operations)
                operations = []

    # Dispara o resto das operações que sobraram
    if operations:
        collection.bulk_write(operations)

    print(f">>> SUCCESS! {count} records synchronized in 'covers_analysis' collection.")

if __name__ == "__main__":
    import_to_mongo()