import requests
from bs4 import BeautifulSoup
import os
import json
import time
import hashlib
from urllib.parse import urljoin

# --- CONFIGURATION ---
SOURCE_DOMAINS = ["abola.pt", "record.pt", "ojogo.pt", "desporto.sapo.pt", "noticiasaominuto.com"]
YEARS = list(range(1998, 2026)) 

BASE_DIR = "data/covers"
IMG_DIR = os.path.join(BASE_DIR, "images")
META_DIR = os.path.join(BASE_DIR, "metadata")

# Ensure directories exist
for folder in [IMG_DIR, META_DIR]:
    if not os.path.exists(folder): 
        os.makedirs(folder)

def get_homepage_snapshots(domain, year):
    """
    Uses Arquivo.pt text search API to find historical homepage snapshots.
    Attempts to retrieve one per month for longitudinal diversity[cite: 6, 24].
    """
    api_url = 'https://arquivo.pt/textsearch'
    # Test with standard www prefix
    v = f"http://www.{domain}"
    payload = {
        'versionHistory': v, 
        'maxItems': 12, 
        'from': f'{year}0101000000', 
        'to': f'{year}1231235959'
    }
    try:
        r = requests.get(api_url, params=payload, timeout=30)
        if r.status_code == 200:
            return [item['linkToNoFrame'] for item in r.json().get('response_items', [])]
    except: 
        return []
    return []

def extract_main_image(page_url):
    """
    Parses the page to find the largest image, likely being the front page cover.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(page_url, timeout=20, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        images = soup.find_all('img')
        if not images: 
            return None
        
        # Filter for content images (ignoring logos and icons)
        best_img = None
        max_area = 0
        
        for img in images:
            src = img.get('src')
            if not src or "logo" in src.lower() or "icon" in src.lower(): 
                continue
            
            # Try to get dimensions if available in HTML attributes
            try:
                w = int(img.get('width', 0) or 0)
                h = int(img.get('height', 0) or 0)
                area = w * h
            except:
                area = 0
            
            if area > max_area or (not best_img and len(src) > 10):
                max_area = area
                best_img = urljoin(page_url, src)
                
        return best_img
    except: 
        return None

# --- EXECUTION ---
print("=== COVER EXTRACTION: HOMEPAGE HISTORY RECOVERY ===")

for domain in SOURCE_DOMAINS:
    clean_domain = domain.replace(".", "_")
    for year in YEARS:
        print(f"> {domain} ({year}):", end=" ", flush=True)
        
        snapshots = get_homepage_snapshots(domain, year)
        if not snapshots:
            print("SKIPPED (Site not archived in this year)")
            continue
            
        saved = 0
        for snap_url in snapshots:
            img_url = extract_main_image(snap_url)
            if img_url:
                # Generate unique ID for the image to prevent duplicates
                img_id = hashlib.md5(img_url.encode()).hexdigest()[:10]
                filename = f"{clean_domain}_{year}_{img_id}.jpg"
                filepath = os.path.join(IMG_DIR, filename)
                
                # Physical download of the image
                try:
                    img_data = requests.get(img_url, timeout=10).content
                    # 10KB threshold to avoid trackers/transparent pixels
                    if len(img_data) > 10000: 
                        with open(filepath, 'wb') as f:
                            f.write(img_data)
                        saved += 1
                        # 3 covers per year is enough for the initial analysis[cite: 24]
                        if saved >= 3: 
                            break 
                except: 
                    continue
        
        if saved > 0:
            print(f"SUCCESS ({saved} covers found)")
        else:
            print("NO USEFUL IMAGES FOUND")
        time.sleep(1)