import requests
from bs4 import BeautifulSoup
import re

def clean_source_text(text, source):
    """
    Performs source-specific text cleaning to handle dates, timestamps, 
    legal notices, and unfinished sentences across different archive eras.
    """
    if not text: return ""
    
    # Global Cleanup: Remove double spaces and excessive line breaks
    text = re.sub(r'\s+', ' ', text).strip()
    src = source.lower()

    if "noticiasaominuto" in src:
        # Remove timestamps and category headers
        text = re.sub(r'Há \d+ (mins?|minutos?|horas?)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^(Desporto|Economia|Mundo|País|Fama|Cultura).*?\d+ (mins?|horas?)', '', text, flags=re.IGNORECASE)

    elif "record.pt" in src:
        # Remove poll results common in older archives[cite: 23]
        if "votos" in text.lower() and "%" in text: return ""

    elif "ojogo.pt" in src:
        # Remove long legal notices from 1998-2006 archives[cite: 23]
        if "Nenhuma parte desta publicação" in text:
            text = text.split("Nenhuma parte desta publicação")[0]
        # Discard news that are just live match markers
        if any(x in text.upper() for x in ["JOGO EM DIRETO", "DIRETO |"]): return ""

    elif "abola.pt" in src:
        # Remove concatenated dates and isolated timestamps[cite: 23]
        text = re.sub(r'\d{2}\.\d{2}\.\d{4}\d{2}:\d{2}', '', text)
        text = re.sub(r'\b\d{2}:\d{2}\b', '', text)

    elif "sapo.pt" in src:
        # Remove navigation noise and common error phrases
        text = text.replace("Abrir numa nova janela", "").replace("fechar", "")
        if "Não foi possível encontrar a página" in text: return ""

    return text.strip()

def generic_clean(elements, url, soup, source):
    """
    Extraction logic with flexible filters to capture textual content from various archive periods[cite: 23].
    """
    extracted = []
    ad_blacklist = ["crédito", "habitação", "carro", "seguro", "casino", "aposta", "irs", "imposto"]
    
    # Sports-related keywords for relevance filtering
    sports_keywords = [
        "futebol", "benfica", "porto", "sporting", "golo", "liga", "clube", "seleção",
        "feminino", "feminina", "mulher", "mulheres", "jogadora", "treinadora", "árbitra",
        "futsal", "andebol", "basquetebol", "ténis", "atletismo", "olímpica"
    ]

    for e in elements:
        title = e.get_text().strip()
        title_l = title.lower()
        
        # Title Filter: Length check and advertisement removal[cite: 23]
        if len(title) < 15 or len(title) > 250 or any(ad in title_l for ad in ad_blacklist):
            continue

        # Content relevance check[cite: 6]
        is_sports_site = any(s in url.lower() for s in ["abola", "record", "ojogo", "desporto"])
        has_keyword = any(key in title_l for key in sports_keywords)
        if not (is_sports_site or has_keyword):
            continue

        # Body Text Extraction using varied selectors for different archive layouts[cite: 23]
        raw_body = ""
        body_target = soup.select_one('.article-body, .main-content, .texto-noticia, .article-content, #noticia-texto, .noticia-corpo, .txt-noticia')
        if body_target:
            raw_body = body_target.get_text(separator=" ")
        else:
            # Fallback to the next textual block
            sibling = e.find_next(['p', 'div', 'td', 'span'])
            if sibling: raw_body = sibling.get_text()

        # Clean extracted text[cite: 23]
        clean_text = clean_source_text(raw_body, source)

        # Body Filter: Minimum length check for article content[cite: 23]
        if len(clean_text) > 70 and clean_text.lower() != title_l:
            extracted.append({
                "title": title,
                "link": url,
                "body_text": clean_text[:5000]
            })
            
            # If direct article link, stop after first extraction
            if any(x in url.lower() for x in [".html", "/artigo/", "/noticia/"]): break
                
    return extracted

# --- SOURCE-SPECIFIC EXTRACTORS ---

def abola_extractor(url, year, logger):
    try:
        r = requests.get(url, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('h1, .noticia-titulo, #titulo_noticia, .titulo, .linkNoticias')
        return generic_clean(elements, url, soup, "abola.pt")
    except: return []

def record_extractor(url, year, logger):
    try:
        r = requests.get(url, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('h1, .title, .newsslot h2, .noticia_box, b, strong')
        return generic_clean(elements, url, soup, "record.pt")
    except: return []

def ojogo_extractor(url, year, logger):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=30, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('article h2, .titnot, h1, .article-title, .header-artigo h1')
        return generic_clean(elements, url, soup, "ojogo.pt")
    except: return []

def getArticle(link, year, source, logger):
    """Main routing function for article extraction[cite: 22]."""
    src = source.lower()
    if "abola.pt" in src: return abola_extractor(link, year, logger)
    if "record.pt" in src: return record_extractor(link, year, logger)
    if "ojogo.pt" in src: return ojogo_extractor(link, year, logger)
    
    # Generic logic for other news sources
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(link, timeout=30, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('h1, h2, h3, .title, .article-thumb-text, .post-item-title, .m-object__title__link')
        return generic_clean(elements, link, soup, source)
    except: return []