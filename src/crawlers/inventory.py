import json
import os

# Updated path to the new data structure
# Articles are now stored in data/raw/articles
folder = "data/raw/articles"
total_articles = 0

# Verify if the folder exists to prevent crashes
if not os.path.exists(folder):
    print(f"Error: Folder '{folder}' not found. Run main.py first.")
else:
    # List all JSON files containing extracted raw content
    files = [f for f in os.listdir(folder) if f.endswith('.json')]

    print(f"{'Source File':<45} | {'Count':<10}")
    print("-" * 60)

    for file in files:
        file_path = os.path.join(folder, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                count = len(data)
                total_articles += count
                print(f"{file:<45} | {count:<10}")
            except json.JSONDecodeError:
                print(f"{file:<45} | Error reading file")

    print("-" * 60)
    print(f"TOTAL RAW ARTICLES EXTRACTED: {total_articles}")