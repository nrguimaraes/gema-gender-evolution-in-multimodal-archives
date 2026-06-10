import os
import requests
import json
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
BASE_URL = "https://www.vercapas.com/capa/arquivo"
SOURCES = ["a-bola", "record", "o-jogo"] # Targeting major Portuguese sports newspapers
IMG_DIR = "data/capas/images"
META_DIR = "data/capas/metadata"

# Ensure target directories exist for images and metadata
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)

def download_cover(source, date_str):
    """
    Downloads the full-resolution newspaper cover by targeting the correct 
    image container and bypassing thumbnail paths.
    """
    img_name = f"{source}_{date_str}.jpg"
    save_path = os.path.join(IMG_DIR, img_name)
    
    # Skip if file already exists to save time and bandwidth
    # This automatically ignores the Saturdays you already scraped
    if os.path.exists(save_path):
        print(f"      [SKIPPED] Already exists locally: {img_name}")
        return True

    url = f"{BASE_URL}/{source}/{date_str}.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://www.vercapas.com/'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Target the specific span container found in the site structure
        container = soup.find("span", {"class": "center_text"})
        img_tag = container.find("img") if container else None
        
        # Fallback to the meta tag if the container isn't found
        if not img_tag:
            img_tag = soup.find("link", {"rel": "image_src"})
            attr = 'href' if img_tag.name == 'link' else 'src'
        else:
            attr = 'src'

        if img_tag and img_tag.get(attr):
            img_url = img_tag[attr]
            
            # CRITICAL: Convert thumbnail URL to full cover URL by changing the path
            # This ensures we get the entire page, not just a cropped preview.
            if "/thumbc/" in img_url:
                img_url = img_url.replace("/thumbc/", "/covers/")
                print(f"      [UPGRADING] Switched to high-resolution path (/covers/)")

            # Standardize relative URLs to absolute URLs
            if img_url.startswith('//'): 
                img_url = 'https:' + img_url
            elif not img_url.startswith('http'): 
                img_url = 'https://www.vercapas.com' + img_url

            # Download and save the binary image data
            img_res = requests.get(img_url, headers=headers, timeout=15)
            if img_res.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(img_res.content)
                
                # Save metadata for later integration with MongoDB
                meta = {
                    "source": source, 
                    "date": date_str, 
                    "page_url": url, 
                    "img_url": img_url,
                    "resolution": "full"
                }
                with open(os.path.join(META_DIR, f"{img_name}.json"), 'w', encoding='utf-8') as f:
                    json.dump(meta, f, indent=4, ensure_ascii=False)
                return True
                
    except Exception as e:
        print(f"      Error downloading {source} on {date_str}: {e}")
    return False

if __name__ == "__main__":
    # Define the chronological range from Jan 1st, 2016 to the current date in 2026
    start_date = datetime(2016, 1, 1)
    end_date = datetime.now()
    
    current = start_date

    print(f">>> Initializing Stealth Historical Crawl (Daily from 2016 to {end_date.strftime('%Y')})...")

    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\nTargeting Date: {date_str}")

        for src in SOURCES:
            # Execute download logic which includes the file existence check
            if download_cover(src, date_str):
                print(f"   [SUCCESS] {src}")
            else:
                print(f"   [FAILURE] {src} - Verify source availability or selector accuracy.")

            # STEALTH STRATEGY: Random sleep intervals to simulate human browsing behavior
            wait_time = random.uniform(1, 20) 
            print(f"      Throttling: Sleeping for {wait_time:.2f}s...")
            time.sleep(wait_time)

        # Increment by 1 day for daily collection instead of weekly (7 days)
        current += timedelta(days=1)

    print("\n>>> Historical crawl completed successfully.")