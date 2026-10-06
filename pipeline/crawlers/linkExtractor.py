import requests
import json
import os

# Sources that changed domain over time.
# Arquivo.pt indexes each domain separately, so we must query the correct
# historical domain for each year.
#
# Format: "canonical_source" -> { range(start_year, end_year): ["domain1", ...] }
# An empty list means no archived content exists for that period.

DOMAIN_HISTORY = {
    "desporto.sapo.pt": {
        range(1998, 2002): ["infordesporto.pt", "www.infordesporto.pt"],
        range(2002, 2008): ["infordesporto.sapo.pt", "www.infordesporto.sapo.pt"],
        range(2008, 2009): [],   # Maintenance page — no useful content
        range(2009, 2030): ["desporto.sapo.pt"],
    }
}


def _get_domain_variations(url, year):
    """
    Returns the domain variations to query for a given source and year.

    For sources with a known domain change history (DOMAIN_HISTORY),
    returns the correct historical domains. For others, uses the
    standard http/https variation logic.

    Returns an empty list if no archived content exists for that period.
    """
    ano = int(year)
    clean_url = url.replace("https://", "").replace("http://", "") \
                   .replace("www.", "").strip("/")

    # Check if this source has a special domain history
    for canonical, history in DOMAIN_HISTORY.items():
        if clean_url == canonical or clean_url.startswith(canonical):
            for year_range, domains in history.items():
                if ano in year_range:
                    if not domains:
                        return []  # No content for this period
                    variations = []
                    for d in domains:
                        variations.append(f"http://{d}")
                        if ano >= 2015:
                            variations.append(f"https://{d}")
                    return variations

    # Standard logic for sources without a special history
    if ano < 2015:
        return [f"http://www.{clean_url}", clean_url]
    else:
        return [f"http://www.{clean_url}", f"https://www.{clean_url}", clean_url]


def get_past_urls(year, url):
    """
    Retrieves historical snapshots from Arquivo.pt API.

    Handles sources that changed domain over time — e.g. desporto.sapo.pt
    was infordesporto.pt in 2001 and infordesporto.sapo.pt in 2002-2007.
    Returns an empty list immediately for years with no archived content.
    """
    api_url = 'https://arquivo.pt/textsearch'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    variations = _get_domain_variations(url, year)

    if not variations:
        return []  # e.g. SAPO 2008 — no archived content

    # Higher limit for years with sparser archive coverage
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
            r = requests.get(api_url, params=payload, headers=headers, timeout=60)
            if r.status_code == 200:
                items = r.json().get('response_items', [])
                links = [item['linkToNoFrame'] for item in items]
                all_links.extend(links)
        except Exception:
            continue

    return list(set(all_links))


def save_links_to_json(links, url, year, filepath):
    """
    Saves extracted links into a structured JSON format.

    The 'source' field always stores the canonical source name
    (e.g. "desporto.sapo.pt") regardless of the historical domain used
    to find the links — so articleExtractor always knows which extractor to use.
    """
    js = [{"link": l, "source": url, "year": str(year)} for l in links]
    safe_name = url.replace("https://", "").replace("http://", "") \
                   .replace("/", "_").replace(".", "")
    filename = f"{safe_name}_{year}.json"

    if links:
        output_path = os.path.join(filepath, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(js, f, indent=4, ensure_ascii=False)