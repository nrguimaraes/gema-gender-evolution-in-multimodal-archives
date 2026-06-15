import os
import sys
import json
import pymongo
from pymongo import UpdateOne # Importante para inserir em lote

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# --- NETWORK CONFIGURATION ---
WIN_IP = "172.17.16.1"
client = pymongo.MongoClient(f'mongodb://{WIN_IP}:27017/', serverSelectionTimeoutMS=5000)
db = client['estagio_desporto']

col_raw = db['articles_raw']       
col_final = db['articles_final']   

RAW_FOLDER = os.path.join(PROJECT_ROOT, "data", "enriched")
CLASSIFIED_FOLDER = os.path.join(PROJECT_ROOT, "data", "processed", "processed_wikineural_final")

# Tamanho do lote de inserção (5000 é um valor muito rápido e seguro)
BATCH_SIZE = 5000 

def upload_to_mongo():
    # --- 0. LIMPEZA DA BASE DE DADOS ANTIGA ---
    print("A limpar as coleções antigas para evitar dados fantasma...")
    col_raw.drop()
    col_final.drop()
    print("Coleções limpas! A iniciar o upload...")

    # --- 1. Upload raw articles ---
    if not os.path.exists(RAW_FOLDER):
        print(f"Error: Folder '{RAW_FOLDER}' not found.")
    else:
        raw_files = [f for f in os.listdir(RAW_FOLDER) if f.endswith('.json')]
        raw_count = 0
        operations = [] # Lista para guardar o lote

        for file in raw_files:
            with open(os.path.join(RAW_FOLDER, file), 'r', encoding='utf-8') as f:
                articles = json.load(f)

            for art in articles:
                art_id = art.get('link')
                if not art_id:
                    continue
                art['_id'] = art_id
                
                # Adiciona à lista de operações em vez de enviar logo
                operations.append(UpdateOne({"_id": art_id}, {"$set": art}, upsert=True))
                raw_count += 1

                # Quando chegar a 5000, envia tudo de uma vez para o Mongo
                if len(operations) >= BATCH_SIZE:
                    col_raw.bulk_write(operations)
                    operations = [] # Limpa a lista para o próximo lote

        # Envia o que sobrou (se o último lote não chegar a 5000)
        if operations:
            col_raw.bulk_write(operations)

        print(f"articles_raw: {raw_count} documents synced from {len(raw_files)} files.")

    # --- 2. Upload classified articles ---
    if not os.path.exists(CLASSIFIED_FOLDER):
        print(f"Error: Folder '{CLASSIFIED_FOLDER}' not found.")
    else:
        classified_files = [f for f in os.listdir(CLASSIFIED_FOLDER) if f.endswith('.json')]
        classified_count = 0
        operations = [] # Lista para guardar o lote

        for file in classified_files:
            with open(os.path.join(CLASSIFIED_FOLDER, file), 'r', encoding='utf-8') as f:
                articles = json.load(f)

            for art in articles:
                art_id = art.get('link')
                if not art_id:
                    continue
                art['_id'] = art_id
                
                operations.append(UpdateOne({"_id": art_id}, {"$set": art}, upsert=True))
                classified_count += 1

                if len(operations) >= BATCH_SIZE:
                    col_final.bulk_write(operations)
                    operations = []

        if operations:
            col_final.bulk_write(operations)

        print(f"articles_final: {classified_count} documents synced from {len(classified_files)} files.")

    print("\nUpload to MongoDB complete.")

if __name__ == "__main__":
    upload_to_mongo()