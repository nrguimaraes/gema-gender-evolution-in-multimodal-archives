import json
import os

# Folder containing the extracted article files
folder = "data/articles"
total = 0

# List all JSON files in the directory
files = [f for f in os.listdir(folder) if f.endswith('.json')]

print(f"{'File':<40} | {'Articles':<10}")

for file in files:
    with open(os.path.join(folder, file), 'r', encoding='utf-8') as f:
        data = json.load(f)
        count = len(data)
        total += count
        print(f"{file:<40} | {count:<10}")

print(f"TOTAL ARTICLES EXTRACTED: {total}")