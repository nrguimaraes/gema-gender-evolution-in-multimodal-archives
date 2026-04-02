import requests
import string
import json
import os

def getPastURLs(year, url):
    """
    Retrieves historical URLs from Arquivo.pt for a specific domain and year.
    Implements dynamic limit logic to maximize collection in years with lower archive density.
    """
    url_api = 'https://arquivo.pt/textsearch'
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Prepare variations to cover changes in protocols and subdomains (http/https/www)
    clean = url.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    variations = [f"http://www.{clean}", f"https://www.{clean}", clean]
    
    # Rescue Logic: Increase the limit to 500 for older years (<= 2006) 
    # to compensate for the lower frequency of historical captures
    limit = "500" if int(year) <= 2006 else "150"
    
    all_links = []
    for v in variations:
        # Define the complete time interval for the specific year
        payload = {
            'versionHistory': v, 
            'maxItems': limit, 
            'from': f'{year}0101000000', 
            'to': f'{year}1231235959'
        }
        
        try:
            r = requests.get(url_api, params=payload, headers=headers, timeout=20)
            if r.status_code == 200:
                items = r.json().get('response_items', [])
                if items:
                    # Extract unique links (NoFrame) to avoid archive navigation frames
                    links = [item['linkToNoFrame'] for item in items]
                    all_links.extend(links)
        except Exception:
            continue
            
    # Return a list of unique links to avoid redundant processing
    return list(set(all_links))

def writePastURLS(links, url, year, filepath):
    """
    Saves the retrieved links into a structured JSON file for subsequent processing.
    """
    # Structure data as required for the extraction phase
    js = [{"link": l, "source": url, "year": str(year)} for l in links]
    
    # Generate a safe filename by removing punctuation from the URL
    clean_name = url.translate(str.maketrans('', '', string.punctuation))
    filename = f"{clean_name}_{year}.json"
    
    if links:
        output_path = os.path.join(filepath, filename)
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(js, file, indent=4, ensure_ascii=False)