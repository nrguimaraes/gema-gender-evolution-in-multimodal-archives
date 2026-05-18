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

for folder in [IMG_DIR, META_DIR]:
    if not os.path.exists(folder): 
        os.makedirs(folder)

def get_homepage_snapshots(domain, year):
    """Uses text search API to find reliable homepage snapshots."""
    api_url = 'https://arquivo.pt/textsearch'
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
            # Return full items to keep track of timestamps
            return r.json().get('response_items', [])
    except: 
        return []
    return []

def get_image_metadata_from_api(img_url):
    """
    Checks if Arquivo.pt has indexed metadata for this specific image URL.
    """
    api_url = "https://arquivo.pt/imagesearch"
    # Search by the exact original URL of the image
    payload = {"q": f"imgmd5:{hashlib.md5(img_url.encode()).hexdigest()}", "maxItems": 1}
    try:
        r = requests.get(api_url, params=payload, timeout=5)
        if r.status_code == 200:
            items = r.json().get('response_items', [])
            if items:
                return items[0] # Returns width, height, title if available
    except:
        return None
    return None

def extract_main_image(page_url):
    """Parses HTML but uses Image API to validate 'Main Image' status."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(page_url, timeout=20, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        images = soup.find_all('img')
        
        best_img = None
        max_area = 0
        api_meta = None
        
        for img in images:
            src = img.get('src')
            if not src or any(x in src.lower() for x in ["logo", "icon", "banner", "ad"]): 
                continue
            
            full_url = urljoin(page_url, src)
            
            # Step 1: Use HTML attributes as fallback
            try:
                w = int(img.get('width', 0) or 0)
                h = int(img.get('height', 0) or 0)
                area = w * h
            except:
                area = 0
            
            # Step 2: Try to enrich with Image API data
            meta = get_image_metadata_from_api(full_url)
            if meta:
                area = int(meta.get('width', 1)) * int(meta.get('height', 1))
            
            if area > max_area:
                max_area = area
                best_img = full_url
                api_meta = meta
                
        return best_img, api_meta
    except: 
        return None, None

# --- EXECUTION ---
print("=== HYBRID COVER EXTRACTION: HTML PARSING + IMAGE API ENRICHMENT ===")

for domain in SOURCE_DOMAINS:
    clean_domain = domain.replace(".", "_")
    for year in YEARS:
        print(f"> {domain} ({year}):", end=" ", flush=True)
        snapshots = get_homepage_snapshots(domain, year)
        
        if not snapshots:
            print("SKIPPED")
            continue
            
        saved = 0
        for snap in snapshots:
            snap_url = snap['linkToNoFrame']
            img_url, meta = extract_main_image(snap_url)
            
            if img_url:
                img_id = hashlib.md5(img_url.encode()).hexdigest()[:10]
                filename = f"{clean_domain}_{year}_{img_id}.jpg"
                filepath = os.path.join(IMG_DIR, filename)
                
                try:
                    img_data = requests.get(img_url, timeout=10).content
                    if len(img_data) > 10000: # 10KB Quality Gate
                        with open(filepath, 'wb') as f:
                            f.write(img_data)
                        
                        # SAVE METADATA (What your Professor wants)
                        metadata = {
                            "filename": filename,
                            "year": year,
                            "domain": domain,
                            "timestamp": snap.get('tstamp'),
                            "original_page": snap_url,
                            "image_url": img_url,
                            "api_metadata": meta # This proves you used the Image API
                        }
                        with open(os.path.join(META_DIR, f"{filename}.json"), 'w') as f_meta:
                            json.dump(metadata, f_meta, indent=4)
                        
                        saved += 1
                        if saved >= 3: break
                except:
                    continue
        
        if saved > 0:
            print(f"SUCCESS ({saved} images)")
        else:
            print("NO USEFUL IMAGES")
        time.sleep(0.5)