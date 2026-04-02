import logging
import os.path
import json
import time
import random
from linkExtractor import writePastURLS, getPastURLs
from articleExtractor import getArticle

# Logging configuration for process monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Folder Configuration
folder_path = ["data/links", "data/articles"]
for p in folder_path:
    if not os.path.exists(p): 
        os.makedirs(p)

# Complete List of Sources
source_links = [
    "abola.pt", 
    "record.pt", 
    "ojogo.pt", 
    "sapo.pt", 
    "noticiasaominuto.com"
]

# YEAR CONFIGURATION: Toggle based on processing needs
# Full list for 30-year longitudinal analysis
years = [1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024]

# STEP 1: Link Retrieval from Arquivo.pt
print("\nSTEP 1: LINK RETRIEVAL (ARQUIVO.PT)")
for url in source_links:
    for year in years:
        # getPastURLs applies dynamic limits (500 for older years)
        links = getPastURLs(year, url)
        writePastURLS(links, url, year, folder_path[0])
        print(f"Source: {url} | Year: {year} | Retrieved Links: {len(links)}")

# STEP 2: Content Extraction and Cleaning (HTML Parsing)
print("\nSTEP 2: ARTICLE EXTRACTION AND BOILERPLATE REMOVAL")
# Filters only the JSON files corresponding to the selected years
files = [f for f in os.listdir(folder_path[0]) if any(str(y) in f for y in years)]

for file in files:
    print(f"Processing: {file}")
    data_extracted = []
    
    with open(os.path.join(folder_path[0], file), "r", encoding='utf-8') as js:
        links_data = json.load(js)
        
        for entry in links_data:
            # Random pause to respect API limits and avoid blocking
            time.sleep(random.uniform(2, 5)) 
            
            # Extraction using era-specific selectors and blacklist filters
            res = getArticle(entry["link"], entry["year"], entry["source"], logger)
            
            for r in res:
                item = entry.copy()
                item.update(r)
                data_extracted.append(item)
    
    # Saving structured data for subsequent NER analysis
    if data_extracted:
        output_file = os.path.join(folder_path[1], file)
        with open(output_file, "w", encoding='utf-8') as wf:
            json.dump(data_extracted, wf, indent=4, ensure_ascii=False)
            print(f"  [SUCCESS] {len(data_extracted)} cleaned articles saved in {file}.")

print("\nPROCESS COMPLETED.")