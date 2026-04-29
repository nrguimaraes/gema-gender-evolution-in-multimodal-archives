import requests
import json
import os

def get_past_urls(year, url):
    """
    Retrieves historical snapshots from Arquivo.pt API.
    Optimized for longitudinal analysis (1998-2025) by handling HTTP/HTTPS variations 
    and implementing timeouts for slow archival responses[cite: 6, 25].
    """
    api_url = 'https://arquivo.pt/textsearch'
    
    # Use a standard browser User-Agent to ensure stable API connection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    clean_url = url.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    
    # Protocol handling: HTTPS was rare before 2015[cite: 25]
    if int(year) < 2015:
        variations = [f"http://www.{clean_url}", clean_url]
    else:
        variations = [f"http://www.{clean_url}", f"https://www.{clean_url}", clean_url]
    
    # Increase item limit for older years to compensate for lower archival frequency[cite: 25]
    limit = "500" if int(year) <= 2006 else "200"
    
    all_links = []
    for v in variations:
        payload = {
            'versionHistory': v, 
            'maxItems': limit, 
            'from': f'{year}0101000000', 
            'to': f'{year}1231235959'
        }
        try:
            # 60s timeout to handle slow archival database queries[cite: 25]
            r = requests.get(api_url, params=payload, headers=headers, timeout=60)
            if r.status_code == 200:
                items = r.json().get('response_items', [])
                # Store linkToNoFrame to avoid archive frame noise during content extraction[cite: 25]
                links = [item['linkToNoFrame'] for item in items]
                all_links.extend(links)
        except Exception:
            continue
            
    return list(set(all_links))

def save_links_to_json(links, url, year, filepath):
    """
    Saves extracted links into a structured JSON format in the data/raw/links directory.
    """
    js = [{"link": l, "source": url, "year": str(year)} for l in links]
    safe_name = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "")
    filename = f"{safe_name}_{year}.json"
    
    if links:
        # Filepath is provided by main.py (data/raw/links)[cite: 6, 22]
        output_path = os.path.join(filepath, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(js, f, indent=4, ensure_ascii=False)