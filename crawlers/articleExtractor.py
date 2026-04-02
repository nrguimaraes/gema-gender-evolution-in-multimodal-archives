import requests
from bs4 import BeautifulSoup
import re

def generic_clean(elements, url):
    """
    Filters 'garbage' from menus, titles with context, and removes local duplicates.
    """
    extracted = []
    # Words that indicate navigation menus rather than news content
    blacklist = ["chat", "fórum", "discussão", "on-line", "classificações", "pesquisa", 
                 "contactos", "contatos", "publicidade", "newsletter", "tópicos", "seguinte"]
    
    for e in elements:
        if e:
            title = e.get_text().strip()
            # Title > 30 characters to ensure enough context for BERTimbau
            if len(title) > 30 and not any(word in title.lower() for word in blacklist):
                # Cleaning double spaces and line breaks
                title = re.sub(r'\s+', ' ', title)
                extracted.append({"title": title, "link": url})
    return extracted

def abola_extractor(url, year, logger):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        y = int(year)
        
        # Era-based selector logic for higher historical precision
        if y <= 2006: 
            elements = soup.select('td.noticia-titulo, b font, .linkNoticias, td.titulo')
        else: 
            elements = soup.find_all(class_="titulo") or soup.select('h1, h2')
            
        return generic_clean(elements, url)
    except Exception as e:
        logger.error(f"A Bola Error {year}: {e}")
        return []

def record_extractor(url, year, logger):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        y = int(year)
        
        # Era-based selectors (Record)
        if y <= 2006: 
            elements = soup.select('.noticia_box a, b')
        elif y <= 2015:
            elements = soup.select('.txt-preto, .newsslot h2')
        else: 
            elements = soup.select('h1, .title')
            
        return generic_clean(elements, url)
    except Exception as e:
        logger.error(f"Record Error {year}: {e}")
        return []

def ojogo_extractor(url, year, logger):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        # O Jogo maintains high consistency between h2 and specific classes
        elements = soup.select('article h2, .titnot, h1')
        return generic_clean(elements, url)
    except Exception as e:
        logger.error(f"O Jogo Error {year}: {e}")
        return []

def desportosapo_extractor(url, year, logger):
    try:
        response = requests.get(url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        elements = soup.select('.title, h1, h2')
        return generic_clean(elements, url)
    except: return []

def noticiasminuto_extractor(url, year, logger):
    try:
        response = requests.get(url, timeout=60)
        soup = BeautifulSoup(response.text, 'html.parser')
        elements = soup.select('.article-thumb-text, h1')
        return generic_clean(elements, url)
    except: return []

def getArticle(link, year, source, logger):
    """Main router for multimodal article extraction."""
    source_lower = source.lower()
    if "abola.pt" in source_lower: 
        return abola_extractor(link, year, logger)
    elif "record.pt" in source_lower: 
        return record_extractor(link, year, logger)
    elif "ojogo.pt" in source_lower: 
        return ojogo_extractor(link, year, logger)
    elif "sapo.pt" in source_lower: 
        return desportosapo_extractor(link, year, logger)
    elif "noticiasaominuto.com" in source_lower: 
        return noticiasminuto_extractor(link, year, logger)
    else: 
        return []