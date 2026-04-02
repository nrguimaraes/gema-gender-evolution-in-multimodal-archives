import json
import os

input_folder = "data/articles"
output_folder = "data/cleaned"

# Ensure the output directory exists for the processed data
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

total_original = 0
total_unique = 0

# Retrieve all JSON files from the input directory
files = [f for f in os.listdir(input_folder) if f.endswith('.json')]

# Print table header for the cleaning process
print(f"{'File':<40} | {'Original':<10} | {'Unique':<10}")

for file in files:
    with open(os.path.join(input_folder, file), 'r', encoding='utf-8') as f:
        data = json.load(f)
        total_original += len(data)
        
        # Dictionary to store only unique titles per file to ensure data quality
        unique_articles = {}
        for art in data:
            # Basic title cleaning to ensure a fair comparison during deduplication
            title_clean = art['title'].strip().lower()
            if title_clean not in unique_articles:
                unique_articles[title_clean] = art
        
        cleaned_list = list(unique_articles.values())
        total_unique += len(cleaned_list)
        
        print(f"{file:<40} | {len(data):<10} | {len(cleaned_list):<10}")
        
        # Save the cleaned and deduplicated file
        with open(os.path.join(output_folder, file), 'w', encoding='utf-8') as wf:
            json.dump(cleaned_list, wf, indent=4, ensure_ascii=False)

print(f"FINAL SUMMARY:")
print(f"Total Processed: {total_original}")
print(f"Total Unique: {total_unique}")