import traceback
import requests
from bs4 import BeautifulSoup, Tag
import re
import json
from urllib.parse import urljoin 

def clean_source_text(text, source):
    """
    Performs source-specific text cleaning to handle dates, timestamps,
    legal notices, and unfinished sentences across different archive eras.
    """
    if not text: return ""

    
    # Filter out 404 errors and ASP/INETPUB server errors
    if "The page cannot be found" in text or "HTTP Error 404" in text or "Not Found" in text:
        return ""
    if "INETPUB" in text or "Recordset.ASP" in text:
        return ""

    # Global Cleanup: Remove double spaces and excessive line breaks
    text = re.sub(r'\s+', ' ', text).strip()
    src = source.lower()

    if "noticiasaominuto" in src:
        text = re.sub(r'Há \d+ (mins?|minutos?|horas?)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^(Desporto|Economia|Mundo|País|Fama|Cultura).*?\d+ (mins?|horas?)', '', text, flags=re.IGNORECASE)

    elif "record.pt" in src:
        if "votos" in text.lower() and "%" in text: return ""

    elif "ojogo.pt" in src:
        if "Nenhuma parte desta publicação" in text:
            text = text.split("Nenhuma parte desta publicação")[0]
        if any(x in text.upper() for x in ["JOGO EM DIRETO", "DIRETO |"]): return ""
        if "Ocorreu um erro inesperado" in text: return ""
        # Remove fixed copyright footer
        if "Comentário para O Jogo" in text:
            text = text.split("Comentário para O Jogo")[0].strip()
        # Discard if only footer text remains
        if not text or len(text) < 30: return ""

    elif "abola.pt" in src:
        text = re.sub(r'\d{2}\.\d{2}\.\d{4}\d{2}:\d{2}', '', text)
        text = re.sub(r'\b\d{2}:\d{2}\b', '', text)

    elif "sapo.pt" in src:
        text = text.replace("Abrir numa nova janela", "").replace("fechar", "")
        if "Não foi possível encontrar a página" in text: return ""

    return text.strip()

def generic_clean(elements, url, soup, source):
    """
    Extraction logic with flexible filters to capture textual content from various archive periods.
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

        # Title Filter: Length check and advertisement removal
        if len(title) < 15 or len(title) > 250 or any(ad in title_l for ad in ad_blacklist):
            continue

        # Content relevance check
        is_sports_site = any(s in url.lower() for s in ["abola", "record", "ojogo", "desporto"])
        has_keyword = any(key in title_l for key in sports_keywords)
        if not (is_sports_site or has_keyword):
            continue

        # Body Text Extraction using varied selectors for different archive layouts
        raw_body = ""
        body_target = soup.select_one('.article-body, .main-content, .texto-noticia, .article-content, #noticia-texto, .noticia-corpo, .txt-noticia')
        if body_target:
            raw_body = body_target.get_text(separator=" ")
        else:
            # Fallback to the next textual block
            sibling = e.find_next(['p', 'div', 'td', 'span'])
            if sibling: raw_body = sibling.get_text()

        # Clean extracted text
        clean_text = clean_source_text(raw_body, source)

        # Body Filter: Minimum length check for article content
        if len(clean_text) > 70 and clean_text.lower() != title_l:
            extracted.append({
                "title": title,
                "link": url,
                "body_text": clean_text[:5000]
            })

            # If direct article link, stop after first extraction
            if any(x in url.lower() for x in [".html", "/artigo/", "/noticia/"]): break

    return extracted

def get_closest_url(original_url, timestamp):
    try:
        api = requests.get(
            'https://arquivo.pt/wayback/available',
            params={'url': original_url, 'timestamp': timestamp},
            timeout=10
        )
        if api.status_code == 200:
            data = api.json()
            closest = data.get('archived_snapshots', {}).get('closest', {})
            if closest.get('available'):
                return closest['url'].replace('/wayback/', '/noFrame/replay/').replace('http://arquivo.pt', 'https://arquivo.pt')
    except Exception:
        pass
    return None

# --- SOURCE-SPECIFIC EXTRACTORS ---

def abola_extractor_2000_2003(snapshot_url, year, logger):
    """
    A Bola extractor (2000-2003) — Frames era.
    Reads the daily edition link from the homepage and navigates to the central content frame.
    """
    article_list = []
    source = "abola.pt"

    try:
        # 1. Load the homepage
        response = requests.get(snapshot_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 2. Find the daily edition link (contains 'wdia.htm')
        edition_link = None
        for a in soup.find_all('a', href=True):
            href = a.get('href', '').lower()
            if 'wdia.htm' in href:
                edition_link = a.get('href')  # e.g. wqui/wdia.htm
                break

        if not edition_link:
            print(f"[{source} - {year}] Edition link not found in homepage.")
            return []

        # 3. Replace 'wdia.htm' with 'wfcdia.htm' to jump straight to the content frame
        central_relative = edition_link.lower().replace('wdia.htm', 'wfcdia.htm')
        frame_central = urljoin(snapshot_url, central_relative)

        print(f"[{source} - {year}] Navigating to main content frame: {frame_central}")

        # 4. Load the main content page
        central_resp = requests.get(frame_central, timeout=30)
        central_soup = BeautifulSoup(central_resp.text, 'html.parser')

        # 5. Find article links (.htm or .asp), filtering out menus, forums, and standings
        links = central_soup.find_all('a', href=True)
        article_urls = set()

        for a in links:
            href = a['href']
            href_lower = href.lower()

            if ('.htm' in href_lower or '.asp' in href_lower) and not any(x in href_lower for x in ['wdia', 'wfcdia', 'forum', 'votacao', 'sugestao', 'wfotosdia', 'wclassif', 'wepocas', 'arqepocas', 'fifa', 'ranking', 'wuefa', 'arquefa']):
                full_link = urljoin(frame_central, href)
                if "arquivo.pt" in full_link:
                    article_urls.add(full_link)

        print(f"[{source} - {year}] Found {len(article_urls)} article links. Extracting...")

        # 6. Visit each article and extract text
        for article_url in list(article_urls):
            try:
                art_response = requests.get(article_url, timeout=15)
                art_response.encoding = art_response.apparent_encoding
                art_soup = BeautifulSoup(art_response.text, 'html.parser')

                # Title
                title = ""
                if art_soup.title:
                    title = art_soup.title.get_text(strip=True)
                    title = title.replace("- A BOLA", "").replace("A BOLA -", "").strip()

                # Fallback: if title is a weekday edition name, use first <b> tag
                if len(title) < 5 or "Edição" in title:
                    bold_tag = art_soup.find('b')
                    if bold_tag:
                        title = bold_tag.get_text(strip=True)

                # Remove junk tags
                for element in art_soup(["script", "style", "form", "option", "applet"]):
                    element.decompose()

                # Extract text
                raw_body = art_soup.get_text(separator=' ', strip=True)
                clean_text = clean_source_text(raw_body, source)

                if len(clean_text) > 100:
                    article_list.append({
                        "link": article_url,
                        "source": source,
                        "year": year,
                        "title": title,
                        "body_text": clean_text[:5000]
                    })

            except Exception as ex_art:
                continue

    except Exception as ex:
        print(f"Error processing {snapshot_url}: {str(ex)}")

    return article_list

def abola_extractor_2004_2007(snapshot_url, year, logger):
    """
    A Bola extractor (2004-2007) — ASPX era.
    Uses regex on raw HTML to work around malformed tags that break BeautifulSoup.
    """
    article_list = []
    source = "abola.pt"

    try:
        # 1. Load the homepage
        response = requests.get(snapshot_url, timeout=30)
        response.encoding = response.apparent_encoding

        # 2. Use regex on raw HTML (BeautifulSoup fails on unclosed tags in this era)
        import re
        hrefs_encontrados = re.findall(r'href=[\'"]?([^\'" >]+)', response.text, flags=re.IGNORECASE)

        article_urls = set()
        for href in hrefs_encontrados:
            href_lower = href.lower()

            # Filter: only links with "noticia="
            if 'noticia=' in href_lower:
                full_link = urljoin(snapshot_url, href)
                if "arquivo.pt" in full_link:
                    article_urls.add(full_link)

        print(f"[{source} - {year}] Found {len(article_urls)} article links. Extracting...")

        # 3. Visit each article
        for article_url in list(article_urls):
            try:
                art_response = requests.get(article_url, timeout=15)
                art_response.encoding = art_response.apparent_encoding
                art_soup = BeautifulSoup(art_response.text, 'html.parser')

                # Title
                title = ""
                if art_soup.title:
                    title = art_soup.title.get_text(strip=True)
                    title = title.replace("- A BOLA", "").replace("A BOLA -", "").replace("abola.pt -", "").strip()

                # Strip classic ASPX visual junk
                for element in art_soup(["script", "style", "form", "iframe"]):
                    element.decompose()

                raw_body = art_soup.get_text(separator=' ', strip=True)
                clean_text = clean_source_text(raw_body, source)

                # Only save if content is substantial
                if len(clean_text) > 100:
                    article_list.append({
                        "link": article_url,
                        "source": source,
                        "year": year,
                        "title": title,
                        "body_text": clean_text[:5000]
                    })

            except Exception as ex_art:
                continue

    except Exception as ex:
        print(f"Error processing {snapshot_url}: {str(ex)}")

    return article_list

def abola_extractor_2009(url, logger):
    """A Bola extractor (2009) — matches ASPX article links."""
    article_list = list()
    try:
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Match ASPX article links
        links = soup.find_all('a', href=re.compile(r'nnh/ver\.aspx\?id='))

        for a in links:
            try:
                # Build absolute URL
                article_url = urljoin(url, a['href'])
                # Clean title
                title = re.sub(r'\s+', ' ', a.get_text()).strip()

                # Skip "view all" links and duplicates
                if "todas.aspx" in article_url or any(d['link'] == article_url for d in article_list):
                    continue

                # Fetch and extract article body
                art_resp = requests.get(article_url, timeout=15)
                art_soup = BeautifulSoup(art_resp.text, 'html.parser')

                # Find the article text container (based on 2009 HTML structure)
                body_elem = art_soup.find(attrs={"class": ["justificado", "texto-noticia"]})
                body_text = body_elem.get_text(separator=' ', strip=True) if body_elem else ""

                if len(body_text) > 50:
                    article_list.append({
                        "link": article_url,
                        "source": "abola.pt",
                        "year": "2009",
                        "title": title,
                        "body_text": clean_source_text(body_text, "abola.pt")
                    })
            except Exception as ex:
                continue
    except Exception as ex2:
        if logger: logger.error(f"Error in 2009 extractor: {str(ex2)}")

    return article_list

def abola_extractor_2010_2014(url, year, logger):
    """
    Unified A Bola extractor for 2010-2014.
    """
    article_list = list()
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

        target_url = url
        if url.endswith(".pt/"):
            target_url = url + "nnh/index.aspx"
        elif url.endswith(".pt"):
            target_url = url + "/nnh/index.aspx"

        print(f"-> Redirecting to news list: {target_url}")

        response = requests.get(target_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        links = soup.find_all('a', href=re.compile(r'ver\.aspx\?id='))

        for a in links:
            try:
                href = a['href']
                article_url = target_url.replace("index.aspx", href)

                if any(d['link'] == article_url for d in article_list):
                    continue

                title = re.sub(r'\s+', ' ', a.get_text()).strip()
                if len(title) < 5:
                    continue

                art_resp = requests.get(article_url, headers=headers, timeout=15)
                art_soup = BeautifulSoup(art_resp.text, 'html.parser')

                # Article body is inside div id="a5g4"
                body_elem = art_soup.find(id="a5g4")

                # Fallback for articles using the old structure
                if not body_elem:
                    body_elem = art_soup.find(attrs={"class": ["justificado", "texto-noticia", "corpo-noticia", "noticia-texto", "texto"]})

                if body_elem:
                    # Remove unwanted nested elements (e.g. timestamp span)
                    hora = body_elem.find('div', id='a5x')
                    if hora:
                        hora.extract()

                    body_text = body_elem.get_text(separator=' ', strip=True)
                else:
                    body_text = ""

                body_text = re.sub(r'Actualizações a cada 5 minutos\.', '', body_text, flags=re.IGNORECASE).strip()

                if len(body_text) > 50:
                    article_list.append({
                        "link": article_url,
                        "source": "abola.pt",
                        "year": str(year),
                        "title": title,
                        "body_text": clean_source_text(body_text, "abola.pt")
                    })

            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in 2010-2014 extractor (year {year}): {str(ex)}")

    return article_list

def abola_extractor_2015_2016(url, year, logger):
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        html_limpo = re.sub(r'<!-{2,}.*?-{2,}>', '', response.text, flags=re.DOTALL)
        soup = BeautifulSoup(html_limpo, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        arquivo_prefix = match.group(1) if match else ""
        base_site = match.group(2) if match else ""

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            if "ver.aspx" not in href.lower() and "/noticia/" not in href.lower():
                continue

            if href.startswith("http"):
                article_url = href if "arquivo.pt" in href else arquivo_prefix + href
            elif href.startswith("/"):
                article_url = arquivo_prefix + base_site + href
            else:
                article_url = url.rstrip("/") + "/" + href

            if article_url in visited:
                continue
            visited.add(article_url)

            try:
                art_resp = requests.get(article_url, headers=headers, timeout=15)
                if art_resp.status_code != 200:
                    continue

                art_html_limpo = re.sub(r'<!-{2,}.*?-{2,}>', '', art_resp.text, flags=re.DOTALL)
                art_soup = BeautifulSoup(art_html_limpo, 'lxml')

                title = ""
                title_elem = art_soup.find("div", class_=lambda c: c and "titulo" in c and "arial-black" in c)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                if not title and art_soup.title:
                    title = re.sub(r'\s*[-|]\s*[Aa]bola.*', '', art_soup.title.get_text(strip=True)).strip()
                if len(title) < 5:
                    continue

                body_elem = art_soup.find(id="noticia")
                if not body_elem:
                    body_elem = art_soup.find(attrs={"class": ["texto", "noticia-texto", "article-body"]})

                if body_elem:
                    body_text = body_elem.get_text(separator=' ', strip=True)
                else:
                    body_text = " ".join(
                        p.get_text(strip=True) for p in art_soup.find_all('p')
                        if len(p.get_text(strip=True)) > 20
                    )

                body_text = re.sub(r'Actualizações a cada 5 minutos\.', '', body_text, flags=re.IGNORECASE).strip()

                if len(body_text) > 50:
                    article_list.append({
                        "link": article_url,
                        "source": "abola.pt",
                        "year": str(year),
                        "title": title,
                        "body_text": clean_source_text(body_text, "abola.pt")
                    })

            except Exception:
                continue

    except Exception as ex:
        if logger:
            logger.error(f"Error in default extractor (year {year}): {str(ex)}")

    return article_list

def abola_extractor_2017_2023(url, year, logger):
    article_list = list()
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

        response = requests.get(url, headers=headers, timeout=30)

        # BUG FIX 1: Pattern was empty (r'') — didn't strip anything. Use same strip as 2015-2016.
        html_limpo = re.sub(r'<!-{2,}.*?-{2,}>', '', response.text, flags=re.DOTALL)
        soup = BeautifulSoup(html_limpo, 'lxml')

        # BUG FIX 2: 2017 links use /Nnh/Noticias/Ver/ (CamelCase), already wrapped
        # in the Arquivo.pt prefix. Old lowercase filter ('ver.aspx'/'noticia') missed them.
        links = soup.find_all('a', href=lambda x: x and re.search(
            r'noticias/ver|ver\.aspx|/noticia/', x, re.IGNORECASE
        ))

        print(f"[DEBUG 2017+] Found {len(links)} candidate links.")

        visited = set()

        for a in links:
            try:
                href = a['href']

                # BUG FIX 3: href is already a full Arquivo.pt path like
                # /noFrame/replay/20170909170222/http://www.abola.pt/Nnh/Noticias/Ver/691289
                # urljoin("http://www.abola.pt/", href) produced a wrong URL pointing at
                # the live site instead of the archived snapshot.
                if href.startswith("http"):
                    # Absolute link already complete (rare but possible)
                    article_url = href if "arquivo.pt" in href else "https://arquivo.pt" + href
                elif href.startswith("/noFrame/"):
                    # Path relativo do Arquivo.pt — o caso mais comum em 2017
                    article_url = "https://arquivo.pt" + href
                else:
                    # Fallback: reconstruir a partir do prefixo da snapshot
                    match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
                    if match:
                        article_url = match.group(1) + match.group(2) + "/" + href.lstrip("/")
                    else:
                        continue

                if article_url in visited:
                    continue
                visited.add(article_url)

                # Title fix: in 2017 the <a> wraps a <div> with an image — get_text() is empty.
                # Readable title is in the 'title' attribute of the inner <div> or the <a> itself.
                title = a.get('title', '').strip()
                if not title:
                    inner_div = a.find('div', title=True)
                    if inner_div:
                        title = inner_div.get('title', '').strip()
                if not title:
                    title = a.get_text(strip=True)
                if len(title) < 5:
                    continue

                art_resp = requests.get(article_url, headers=headers, timeout=15)
                if art_resp.status_code != 200:
                    continue

                # Same comment-strip fix applied to individual article pages
                art_html_limpo = re.sub(r'<!-{2,}.*?-{2,}>', '', art_resp.text, flags=re.DOTALL)
                art_soup = BeautifulSoup(art_html_limpo, 'lxml')

                # Multi-target selector for article body
                body_elem = art_soup.select_one('#noticia, .article-body, .texto, .noticia-texto, .corpo-noticia')

                body_text = body_elem.get_text(separator=' ', strip=True) if body_elem else ""

                # Fallback: join all <p> with sufficient text
                if not body_text:
                    body_text = " ".join(
                        p.get_text(strip=True) for p in art_soup.find_all('p')
                        if len(p.get_text(strip=True)) > 20
                    )

                if len(body_text) > 50:
                    article_list.append({
                        "link": article_url,
                        "source": "abola.pt",
                        "year": str(year),
                        "title": title,
                        "body_text": clean_source_text(body_text, "abola.pt")
                    })
            except:
                continue

    except Exception as ex:
        if logger:
            logger.error(f"Error in 2017+ extractor: {ex}")

    return article_list

def abola_extractor_2024(url, year, logger):
    """
    A Bola extractor (2024+) — Next.js era.

    The site uses Next.js: visible HTML is nearly empty.
    All content (homepage article list, article body) is embedded in
    <script id="__NEXT_DATA__"> as structured JSON.

    Strategy:
      1. Homepage → read __NEXT_DATA__ → extract canonical_url from listsData and latestData.
      2. Article  → read __NEXT_DATA__ of article page → extract body from pageProps.article.body
                    (each block has type="paragraph"/"lead"/etc. and a "content" HTML field).
      3. Fallback → if __NEXT_DATA__ is missing (incomplete snapshot), fall back to CSS selectors.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    # ------------------------------------------------------------------ #
    # Helper: extract and parse __NEXT_DATA__ from a page                #
    # ------------------------------------------------------------------ #
    def get_next_data(html_text):
        match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Helper: given __NEXT_DATA__ of an article, extract the body        #
    # ------------------------------------------------------------------ #
    def extract_body_from_next_data(next_data):
        try:
            article = next_data["props"]["pageProps"].get("article", {})
            if not article:
                # Some years use "post" instead of "article"
                article = next_data["props"]["pageProps"].get("post", {})

            # Body is a list of blocks with type + content
            body_blocks = article.get("body", [])
            paragraphs = []
            for block in body_blocks:
                btype = block.get("type", "")
                if btype in ("paragraph", "lead", "blockquote", "h2", "h3"):
                    content = block.get("content", "")
                    if content:
                        # Strip inner HTML tags (bold, links, etc.)
                        clean = re.sub(r'<[^>]+>', ' ', content)
                        clean = re.sub(r'\s+', ' ', clean).strip()
                        if clean:
                            paragraphs.append(clean)

            return " ".join(paragraphs)
        except Exception:
            return ""

    # ------------------------------------------------------------------ #
    # STEP 1 — Download the homepage and extract article URLs             #
    # ------------------------------------------------------------------ #
    try:
        response = requests.get(url, headers=headers, timeout=30)
        next_data = get_next_data(response.text)

        article_urls = []  # lista de (title, subtitle, canonical_url)

        if next_data:
            pp = next_data.get("props", {}).get("pageProps", {})

            # --- listsData: homepage sections (top-slider, benfica-section, etc.) ---
            lists_data = pp.get("listsData", {})
            for section_name, section in lists_data.items():
                if not isinstance(section, dict):
                    continue
                for item in section.get("items", []):
                    if not isinstance(item, dict) or item.get("type") != "ARTICLE":
                        continue
                    d = item.get("data", {})
                    canonical = (d.get("urls") or {}).get("canonical_url", "")
                    title     = (d.get("title") or "").strip()
                    subtitle  = (d.get("subtitle") or "").strip()
                    if canonical and title:
                        article_urls.append((title, subtitle, canonical))

            # --- latestData: "latest news" blocks by category ---
            latest_data = pp.get("latestData", {})
            for cat, cat_val in latest_data.items():
                if not isinstance(cat_val, dict):
                    continue
                for item in cat_val.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    d = item.get("data", item)  # some items have no "data" wrapper
                    canonical = (d.get("urls") or {}).get("canonical_url", "") if isinstance(d.get("urls"), dict) else ""
                    title     = (d.get("title") or "").strip()
                    subtitle  = (d.get("subtitle") or "").strip()
                    if canonical and title:
                        article_urls.append((title, subtitle, canonical))

        else:
            # Fallback: parse HTML with BeautifulSoup if __NEXT_DATA__ is missing
            soup = BeautifulSoup(response.text, 'lxml')
            for a in soup.find_all('a', href=True):
                href = a['href']
                # URLs of the form /futebol/noticias/slug-NUMEROID or /noticias/slug-ID
                if re.search(r'/noticias/[a-z0-9-]+-\d{15,}', href, re.IGNORECASE):
                    title = a.get_text(strip=True) or a.get('title', '').strip()
                    canonical = href if href.startswith('http') else 'https://www.abola.pt' + href
                    if title:
                        article_urls.append((title, '', canonical))

        # Deduplicate by canonical URL
        seen_urls = set()
        unique_articles = []
        for t, s, u in article_urls:
            if u not in seen_urls:
                seen_urls.add(u)
                unique_articles.append((t, s, u))

        print(f"[DEBUG 2024+] {len(unique_articles)} unique articles found on homepage.")

    except Exception as ex:
        if logger:
            logger.error(f"Error loading 2024+ homepage ({url}): {ex}")
        return []

    # ------------------------------------------------------------------ #
    # STEP 2 — Download and extract each article                          #
    # ------------------------------------------------------------------ #

    # Extract the Arquivo.pt prefix to reconstruct archived article URLs
    # e.g. "https://arquivo.pt/noFrame/replay/20240903094118/"
    arquivo_prefix_match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)', url)
    arquivo_prefix = arquivo_prefix_match.group(1) if arquivo_prefix_match else ""

    for title, subtitle, canonical_url in unique_articles:
        try:
            # Build archived URL: prefix + canonical URL
            if arquivo_prefix:
                article_url = arquivo_prefix + canonical_url
            else:
                # Not from Arquivo.pt (e.g. local test) — use directly
                article_url = canonical_url

            art_resp = requests.get(article_url, headers=headers, timeout=15)
            if art_resp.status_code != 200:
                continue

            body_text = ""
            art_next_data = get_next_data(art_resp.text)

            if art_next_data:
                body_text = extract_body_from_next_data(art_next_data)

            # HTML fallback if article's __NEXT_DATA__ has no body
            if not body_text:
                art_soup = BeautifulSoup(art_resp.text, 'lxml')
                body_elem = art_soup.select_one(
                    '.article-body, .article__body, .news-body, '
                    '.texto, .noticia-texto, #noticia, .corpo-noticia'
                )
                if body_elem:
                    body_text = body_elem.get_text(separator=' ', strip=True)
                else:
                    body_text = " ".join(
                        p.get_text(strip=True) for p in art_soup.find_all('p')
                        if len(p.get_text(strip=True)) > 20
                    )

            # Prepend subtitle to body if present and not already included
            if subtitle and subtitle.lower() not in body_text.lower():
                body_text = subtitle + ". " + body_text

            body_text = clean_source_text(body_text, "abola.pt")

            if len(body_text) > 50:
                article_list.append({
                    "link": article_url,
                    "source": "abola.pt",
                    "year": str(year),
                    "title": title,
                    "body_text": body_text[:5000]
                })

        except Exception:
            continue

    return article_list

def ojogo_extractor_1998(url, year, logger):
    """
    O Jogo extractor (1998-2002) — HTML table era.
    Links: artigo.asp?id_art=XXXXX (sidebar, title only)
           Artigo.asp?ID_art=XXXXX (central column, has lead in <p> or next block)
    Individual articles rarely archived — uses homepage leads as fallback.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)
        base_site = match.group(2)

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'artigo.asp' not in href.lower() or 'id_art' not in href.lower():
                continue

            # Skip category links: the <a> wraps a <div class="catsec">
            if a.find('div', class_='catsec'):
                continue

            # Build full Arquivo.pt URL
            if href.startswith("http"):
                article_url = href if "arquivo.pt" in href else arquivo_prefix + href
            elif href.startswith("/"):
                article_url = arquivo_prefix + base_site + href
            else:
                base_path = url.rsplit('/', 1)[0]
                article_url = base_path + "/" + href

            if article_url in visited:
                continue
            visited.add(article_url)

            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            if len(title) < 5:
                continue

            body_text = ""

            # Try individual article first
            try:
                art_resp = requests.get(article_url, headers=headers, timeout=10)
                if art_resp.status_code == 200:
                    art_resp.encoding = art_resp.apparent_encoding
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "select", "img"]):
                        tag.decompose()
                    all_tds = art_soup.find_all('td')
                    if all_tds:
                        best_td = max(all_tds, key=lambda td: len(td.get_text(strip=True)))
                        body_text = re.sub(r'\s+', ' ', best_td.get_text(separator=' ', strip=True))
            except Exception:
                pass

            # Fallback only for central column — sidebar links have no lead
            is_lateral = bool(a.find('div', class_='linkartigo'))

            if len(body_text) < 50 and not is_lateral:
                parent_heading = a.find_parent(['h1', 'h2'])
                start_node = parent_heading if parent_heading else a
                next_article_a = a.find_next('a', href=lambda h: h and 'artigo.asp' in h.lower())
                node = start_node.next_sibling
                fragments = []
                while node and node != next_article_a:
                    if isinstance(node, Tag):
                        if node.find('a', href=lambda h: h and 'artigo.asp' in h.lower()):
                            break
                        text = re.sub(r'\s+', ' ', node.get_text(separator=' ', strip=True))
                        if len(text) > 10:
                            fragments.append(text)
                    else:
                        text = str(node).strip()
                        if len(text) > 5:
                            fragments.append(text)
                    node = node.next_sibling
                if fragments:
                    body_text = ' '.join(fragments).strip()

            # No lead available — save title only
            if len(body_text) < 10:
                body_text = title

            article_list.append({
                "link": article_url,
                "source": "ojogo.pt",
                "year": str(year),
                "title": title,
                "body_text": clean_source_text(body_text, "ojogo.pt")
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 1998-2002 extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 1998-2002 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor_1999(url, year, logger):
    """
    O Jogo extractor (1999-2002).
    Individual articles are archived — extracts full text via <p>.
    Removes ads (script/noscript) before extracting.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)
        base_site = match.group(2)

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'artigo.asp' not in href.lower() or 'id_art' not in href.lower():
                continue
            if a.find('div', class_='catsec'):
                continue

            if href.startswith("http"):
                article_url = href if "arquivo.pt" in href else arquivo_prefix + href
            elif href.startswith("/"):
                article_url = arquivo_prefix + base_site + href
            else:
                base_path = url.rsplit('/', 1)[0]
                article_url = base_path + "/" + href

            if article_url in visited:
                continue
            visited.add(article_url)

            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            if len(title) < 5:
                continue

            body_text = ""

            try:
                art_resp = requests.get(article_url, headers=headers, timeout=10)
                if art_resp.status_code == 200:
                    art_resp.encoding = art_resp.apparent_encoding
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "select", "img", "noscript"]):
                        tag.decompose()
                    paragraphs = art_soup.find_all('p')
                    body_text = " ".join(
                        re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                        for p in paragraphs
                        if len(p.get_text(strip=True)) > 30
                    )
            except Exception:
                pass

            # Homepage fallback if article unavailable
            if len(body_text) < 50:
                is_lateral = bool(a.find('div', class_='linkartigo'))
                if not is_lateral:
                    parent_heading = a.find_parent(['h1', 'h2'])
                    start_node = parent_heading if parent_heading else a
                    next_article_a = a.find_next('a', href=lambda h: h and 'artigo.asp' in h.lower())
                    node = start_node.next_sibling
                    fragments = []
                    while node and node != next_article_a:
                        if isinstance(node, Tag):
                            if node.find('a', href=lambda h: h and 'artigo.asp' in h.lower()):
                                break
                            text = re.sub(r'\s+', ' ', node.get_text(separator=' ', strip=True))
                            if len(text) > 10:
                                fragments.append(text)
                        else:
                            text = str(node).strip()
                            if len(text) > 5:
                                fragments.append(text)
                        node = node.next_sibling
                    if fragments:
                        body_text = ' '.join(fragments).strip()

            if len(body_text) < 10:
                body_text = title

            clean = clean_source_text(body_text, "ojogo.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "ojogo.pt",
                "year": str(year),
                "title": title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 1999-2002 extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 1999-2002 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor_2001_2006(url, year, logger):
    """
    O Jogo extractor (2001-2006).
    New layout: articles in .htm files (e.g. artigo101558.htm).
    Edition folder (e.g. 17-121/) detected from menu links.
    Central column: h1/h2 + p with lead; sidebar: font class="BDTitulo".
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)

        # Detect the edition folder from menu links that already carry the full path
        # e.g. /noFrame/replay/.../http://www.ojogo.pt:80/17-121/artigo101558.htm
        edition_folder = ""
        for a_menu in soup.find_all('a', href=True):
            href_menu = a_menu['href']
            folder_match = re.search(r'(https?://[^/]+/\d+-\d+/)artigo\d+\.htm', href_menu, re.IGNORECASE)
            if folder_match:
                inner_url = folder_match.group(0)
                edition_folder = arquivo_prefix + inner_url.rsplit('/', 1)[0] + "/"
                break

        if not edition_folder:
            edition_folder = url.rstrip("/") + "/"

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: only .htm files with "artigo" in name
            if not re.search(r'artigo\d+\.htm', href, re.IGNORECASE):
                continue

            # Skip links that already contain the Arquivo.pt prefix (menu links)
            if href.startswith('/noFrame') or href.startswith('http'):
                continue

            article_url = edition_folder + href

            if article_url in visited:
                continue
            visited.add(article_url)

            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            if len(title) < 5:
                continue

            body_text = ""

            # Try individual article
            try:
                art_resp = requests.get(article_url, headers=headers, timeout=10)
                if art_resp.status_code == 200:
                    art_resp.encoding = art_resp.apparent_encoding
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "select", "img", "noscript"]):
                        tag.decompose()
                    paragraphs = art_soup.find_all('p')
                    body_text = " ".join(
                        re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                        for p in paragraphs
                        if len(p.get_text(strip=True)) > 30
                    )
            except Exception:
                pass

            # Fallback: lead from central column (h1/h2 + following siblings)
            if len(body_text) < 50:
                parent_heading = a.find_parent(['h1', 'h2'])
                if parent_heading:
                    next_article_a = a.find_next(
                        'a', href=lambda h: h and re.search(r'artigo\d+\.htm', h, re.IGNORECASE) if h else False
                    )
                    node = parent_heading.next_sibling
                    fragments = []
                    while node and node != next_article_a:
                        if isinstance(node, Tag):
                            if node.find('a', href=lambda h: h and re.search(r'artigo\d+\.htm', h, re.IGNORECASE) if h else False):
                                break
                            text = re.sub(r'\s+', ' ', node.get_text(separator=' ', strip=True))
                            if len(text) > 10:
                                fragments.append(text)
                        else:
                            text = str(node).strip()
                            if len(text) > 5:
                                fragments.append(text)
                        node = node.next_sibling
                    if fragments:
                        body_text = ' '.join(fragments).strip()

            if len(body_text) < 10:
                body_text = title

            clean = clean_source_text(body_text, "ojogo.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "ojogo.pt",
                "year": str(year),
                "title": title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 2001-2002 extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 2001-2002 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor_2007_2011(url, year, logger):
    """
    O Jogo extractor (2007-2011).
    Homepage uses iframe — content is in index.asp inside the edition folder.
    Article links: artigo######.asp with full Arquivo.pt prefix embedded.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        # Step 1: Load homepage and follow the iframe
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        iframe = soup.find('iframe', src=True)
        if not iframe:
            return []

        iframe_src = iframe['src']
        # src may be relative (/noFrame/...) or absolute
        if iframe_src.startswith('/'):
            iframe_url = "https://arquivo.pt" + iframe_src
        else:
            iframe_url = iframe_src

        response = requests.get(iframe_url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: only numbered .asp article links
            if not re.search(r'artigo\d+\.asp', href, re.IGNORECASE):
                continue

            # 2007+ links already include the Arquivo.pt prefix
            if href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            elif href.startswith('http'):
                article_url = href
            else:
                continue  # Skip relative links without prefix

            if article_url in visited:
                continue
            visited.add(article_url)

            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            # Filter out menu category links (short titles like "FC Porto", "Sporting")
            if len(title) < 10:
                continue

            body_text = ""

            try:
                art_resp = requests.get(article_url, headers=headers, timeout=10)
                if art_resp.status_code == 200:
                    art_resp.encoding = art_resp.apparent_encoding
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "select", "img", "noscript"]):
                        tag.decompose()
                    paragraphs = art_soup.find_all('p')
                    body_text = " ".join(
                        re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                        for p in paragraphs
                        if len(p.get_text(strip=True)) > 30
                    )
            except Exception:
                pass

            if len(body_text) < 10:
                body_text = title

            clean = clean_source_text(body_text, "ojogo.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "ojogo.pt",
                "year": str(year),
                "title": title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 2007+ extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 2007+ extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor_2012_2014(url, year, logger):
    """
    O Jogo extractor (2012+).
    Modern layout: articles at interior.aspx?content_id=XXXXXXX.
    Titles in <h2> inside <a class="LLBlock_1">; leads in <em class="LLIBLead">.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: only article links with content_id
            if 'interior.aspx' not in href.lower() or 'content_id' not in href.lower():
                continue

            # Build URL
            if href.startswith('http'):
                article_url = href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                continue

            # Strip anchors (#Comment, etc.)
            article_url = article_url.split('#')[0]

            if article_url in visited:
                continue
            visited.add(article_url)

            # Title: from the block's <h2>
            title = ""
            h2 = a.find('h2')
            if h2:
                title = re.sub(r'\s+', ' ', h2.get_text()).strip()

            # Lead: from block's <em class="LLIBLead">
            lead = ""
            em_lead = a.find('em', class_='LLIBLead')
            if em_lead:
                lead = re.sub(r'\s+', ' ', em_lead.get_text()).strip()

            if not title or len(title) < 5:
                continue

            body_text = lead if lead else ""

            # Fetch individual article for full body
            if len(body_text) < 50:
                try:
                    art_resp = requests.get(article_url, headers=headers, timeout=10)
                    if art_resp.status_code == 200:
                        art_resp.encoding = art_resp.apparent_encoding
                        art_soup = BeautifulSoup(art_resp.text, 'lxml')
                        for tag in art_soup(["script", "style", "form", "select", "img", "noscript"]):
                            tag.decompose()
                        paragraphs = art_soup.find_all('p')
                        body_text = " ".join(
                            re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                            for p in paragraphs
                            if len(p.get_text(strip=True)) > 30
                        )
                except Exception:
                    pass

            if len(body_text) < 10:
                body_text = title

            clean = clean_source_text(body_text, "ojogo.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "ojogo.pt",
                "year": str(year),
                "title": title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 2012+ extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 2012+ extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor_2015(url, year, logger):
    """
    O Jogo extractor (2015).
    Arquivo.pt limitation: individual articles not accessible programmatically.
    Extracts titles from ADCLink_2 and LLBlock_1.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        visited = set()

        for a in soup.find_all('a', class_='ADCLink_2'):
            href = a.get('href', '')
            if 'content_id' not in href:
                continue
            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            if len(title) < 5:
                continue
            if href.startswith('http'):
                article_url = href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                continue
            article_url = article_url.split('#')[0].strip()
            if article_url in visited:
                continue
            visited.add(article_url)
            clean = clean_source_text(title, "ojogo.pt")
            if not clean:
                continue
            article_list.append({"link": article_url, "source": "ojogo.pt",
                                  "year": str(year), "title": title, "body_text": clean})

        for a in soup.find_all('a', class_='LLBlock_1'):
            href = a.get('href', '')
            if 'content_id' not in href:
                continue
            title_tag = a.find('strong') or a.find('h2')
            if not title_tag:
                continue
            title = re.sub(r'\s+', ' ', title_tag.get_text()).strip()
            if len(title) < 5:
                continue
            if href.startswith('http'):
                article_url = href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                continue
            article_url = article_url.split('#')[0].strip()
            if article_url in visited:
                continue
            visited.add(article_url)
            clean = clean_source_text(title, "ojogo.pt")
            if not clean:
                continue
            article_list.append({"link": article_url, "source": "ojogo.pt",
                                  "year": str(year), "title": title, "body_text": clean})

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 2015 extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 2015 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor_2016_2018(url, year, logger):
    """
    O Jogo extractor (2016-2018).
    Links: noticias/interior/titulo-XXXXXXX.html.
    Article body in <div class="t-a-c-wrap">.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        visited = set()

        for article in soup.find_all('article'):
            h2 = article.find('h2')
            if not h2:
                continue
            a = h2.find('a', href=True)
            if not a:
                continue
            href = a.get('href', '')
            if 'interior' not in href or '.html' not in href:
                continue

            title = re.sub(r'\s+', ' ', h2.get_text()).strip()
            if len(title) < 5:
                continue

            if href.startswith('http'):
                article_url = href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                continue

            article_url = article_url.split('#')[0].strip()

            if article_url in visited:
                continue
            visited.add(article_url)

            body_text = ""

            try:
                art_resp = requests.get(article_url, headers=headers, timeout=10)
                if art_resp.status_code == 200:
                    art_resp.encoding = art_resp.apparent_encoding
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "select", "img", "noscript"]):
                        tag.decompose()

                    body_elem = art_soup.find('div', class_='t-a-c-wrap')
                    if body_elem:
                        paragraphs = body_elem.find_all('p')
                        body_text = " ".join(
                            re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                            for p in paragraphs
                            if len(p.get_text(strip=True)) > 30
                        )
            except Exception:
                pass

            # Fallback: lead from homepage <h4>
            if len(body_text) < 10:
                h4 = article.find('h4')
                body_text = re.sub(r'\s+', ' ', h4.get_text()).strip() if h4 else title

            if len(body_text) < 10:
                body_text = title

            clean = clean_source_text(body_text, "ojogo.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "ojogo.pt",
                "year": str(year),
                "title": title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo 2016-2018 extractor (year {year}): {str(ex)}")
        print(f"ERROR in ojogo 2016-2018 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def ojogo_extractor(url, year, logger):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
        r = requests.get(url, timeout=30, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('article h2, .titnot, h1, .article-title, .header-artigo h1')
        results = generic_clean(elements, url, soup, "ojogo.pt")
        return [
            {
                "link": item["link"],
                "source": "ojogo.pt",
                "year": str(year),
                "title": item["title"],
                "body_text": item["body_text"]
            }
            for item in results
        ]
    except Exception as ex:
        if logger:
            logger.error(f"Error in O Jogo default extractor (year {year}): {str(ex)}")
        return []
    
def record_extractor_2000(url, year, logger):
    article_list = list()
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=30)
        
        html_limpo = re.sub(r'', '', r.text, flags=re.DOTALL)
        soup = BeautifulSoup(html_limpo, 'html.parser')
        
        links = soup.find_all('a', href=re.compile(r'nId=', re.IGNORECASE))
        
        if "nId=" in url or "id=" in url.lower():
            links = [{'href': url}]
            
        for a in links:
            try:
                href = a.get('href', url) if isinstance(a, dict) else a['href']
                
                # Fix urljoin slash collapse on http:// URLs
                article_url = urljoin(url, href).replace("http:/www", "http://www")
                
                if any(d['link'] == article_url for d in article_list): 
                    continue
                
                art_resp = requests.get(article_url, headers=headers, timeout=15)
                art_html = re.sub(r'', '', art_resp.text, flags=re.DOTALL)
                art_soup = BeautifulSoup(art_html, 'html.parser')
                
                title_elem = art_soup.find('font', attrs={'color': '#FF0000', 'size': '6'})
                if not title_elem:
                    title_elem = art_soup.find('font', color=re.compile(r'#FF0000', re.I))
                    
                if not title_elem: continue
                    
                title = title_elem.get_text(strip=True)
                
                # Skip very short titles or "ON-LINE" error pages
                if len(title) < 5 or title.upper() == "ON-LINE":
                    continue
                
                body_text = ""
                font_tags = art_soup.find_all('font', attrs={'size': '2'})
                for font in font_tags:
                    text = font.get_text(separator=' ', strip=True)
                    if len(text) > len(body_text):
                        body_text = text
                        
                body_text = clean_source_text(body_text, "record.pt")

                # Save if text is still valid after cleaning
                if len(body_text) > 50:
                    article_list.append({
                        "link": article_url,
                        "source": "record.pt",
                        "year": str(year),
                        "title": title,
                        "body_text": body_text
                    })
            except: continue
                
    except Exception as ex:
        if logger: logger.error(f"Error in Record 2000 extractor: {ex}")
        
    return article_list

def record_extractor_2001_2002(url, year, logger):
    """
    Extrator para o Record (2001 - 2003).
    Lida com os links 'shownews.asp' e 'noticia.asp' e extrai o texto das peculiares tags <aux>.
    """
    article_list = list()
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=30)
        
        html_limpo = re.sub(r'', '', r.text, flags=re.DOTALL)
        soup = BeautifulSoup(html_limpo, 'html.parser')
        
        # 1. FIND LINKS: searches for 'shownews' and 'noticia' patterns
        links = soup.find_all('a', href=re.compile(r'(shownews\.asp|noticia\.asp)\?id=', re.IGNORECASE))

        # If the test URL is already an article
        if "shownews.asp?id=" in url.lower() or "noticia.asp?id=" in url.lower() or "id=" in url.lower():
            links = [{'href': url}]
            
        for a in links:
            try:
                href = a.get('href', url) if isinstance(a, dict) else a['href']
                
                # Fix Arquivo.pt slash collapse bug
                article_url = urljoin(url, href).replace("http:/www", "http://www")
                
                if any(d['link'] == article_url for d in article_list): continue
                
                # 2. OPEN ARTICLE
                art_resp = requests.get(article_url, headers=headers, timeout=15)
                art_html = re.sub(r'', '', art_resp.text, flags=re.DOTALL)
                art_soup = BeautifulSoup(art_html, 'html.parser')
                
                # 3. EXTRACT TITLE (skip "PROCURA" search results)
                title = ""
                title_elem = art_soup.find('font', attrs={'color': '#FF0000', 'size': ['5', '6']})
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                else:
                    for font in art_soup.find_all('font', color=re.compile(r'#FF0000', re.I)):
                        txt = font.get_text(strip=True)
                        if len(txt) > len(title) and txt.upper() != "PROCURA":
                            title = txt
                            
                if len(title) < 5 or title.upper() == "ON-LINE": 
                    continue
                
                # 4. EXTRACT BODY (try <aux> tag first)
                body_text = ""
                aux_tags = art_soup.find_all('aux')
                
                if aux_tags:
                    body_text = " ".join([tag.get_text(separator=' ', strip=True) for tag in aux_tags])
                else:
                    # Fallback
                    font_tags = art_soup.find_all('font', attrs={'size': '2'})
                    for font in font_tags:
                        text = font.get_text(separator=' ', strip=True)
                        if len(text) > len(body_text):
                            body_text = text
                            
                body_text = clean_source_text(body_text, "record.pt")
                
                if len(body_text) > 50:
                    article_list.append({
                        "link": article_url,
                        "source": "record.pt",
                        "year": str(year),
                        "title": title,
                        "body_text": body_text
                    })
            except Exception:
                continue
                
    except Exception as ex:
        if logger: logger.error(f"Error in Record 2001-2003 extractor: {ex}")
        
    return article_list

def record_extractor_2005(url, year, logger):
    """
    Record extractor (2003-2007).

    Homepage:
      - Article links: noticia.asp?id=XXXXXX&idCanal=YY (relative)
      - Headline: ante-title in <font color="#FF0000"><b> (outside <a>) +
                  title in <font color="#000000" size="2"><b> (inside <a>) +
                  lead in <span class="record"> (sibling of <a>)
      - Featured: ante-title as text in <td> +
                  title in <font color="#FF0000"><b class="record"> (inside <a>)

    Article page (2006+ layout served by arquivo.pt):
      - Title: <span class="tituleira18red1">
      - Subtitle: <span class="acinza12b"> immediately after
      - Body: <aux> tag inside <span class="apreto12n">
      - Body fallback: all <p> with more than 30 chars
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)
        base_site = match.group(2)

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: only news links with numeric id
            if not re.search(r'noticia\.asp\?id=\d+', href, re.IGNORECASE):
                continue

            # Build article URL
            if href.startswith('http'):
                article_url = href if 'arquivo.pt' in href else arquivo_prefix + href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                article_url = arquivo_prefix + base_site + "/" + href.lstrip('/')

            # Fix slash collapse (http:/www → http://www)
            article_url = re.sub(r'(https?:/)([^/])', r'\1/\2', article_url)
            article_url = article_url.split('#')[0].strip()

            if article_url in visited:
                continue
            visited.add(article_url)

            # Homepage title
            # Try the red font inside <a> first (feature items)
            title = ""
            font_red = a.find('font', color=re.compile(r'#FF0000', re.I))
            if font_red:
                b_tag = font_red.find('b')
                title = re.sub(r'\s+', ' ', (b_tag or font_red).get_text()).strip()
            # Fallback: any bold text inside the <a>
            if not title:
                b_tag = a.find('b')
                if b_tag:
                    title = re.sub(r'\s+', ' ', b_tag.get_text()).strip()
            # Last resort: full link text
            if not title:
                title = re.sub(r'\s+', ' ', a.get_text()).strip()
            if len(title) < 5:
                continue

            # Fetch the article to extract the full body
            body_text = ""
            art_title = title  # fallback title
            try:
                art_resp = requests.get(article_url, headers=headers, timeout=15)
                if art_resp.status_code == 200:
                    art_resp.encoding = art_resp.apparent_encoding
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')

                    # Article title: <span class="tituleira18red1"> (2006+ layout)
                    title_elem = art_soup.find('span', class_='tituleira18red1')
                    if title_elem:
                        art_title = re.sub(r'\s+', ' ', title_elem.get_text()).strip()

                    # Subtitle: <span class="acinza12b"> following the title
                    subtitle = ""
                    if title_elem:
                        sub_elem = title_elem.find_next('span', class_='acinza12b')
                        if sub_elem:
                            subtitle = re.sub(r'\s+', ' ', sub_elem.get_text()).strip()

                    # Main body: <aux> tag (used by Record 2005-2007)
                    aux_tags = art_soup.find_all('aux')
                    if aux_tags:
                        body_text = " ".join(
                            re.sub(r'\s+', ' ', tag.get_text(separator=' ')).strip()
                            for tag in aux_tags
                            if len(tag.get_text(strip=True)) > 30
                        )

                    # Fallback: join all <p> with sufficient text
                    if len(body_text) < 50:
                        for tag in art_soup(["script", "style", "form", "select",
                                             "img", "noscript", "nav", "footer"]):
                            tag.decompose()
                        paragraphs = art_soup.find_all('p')
                        body_text = " ".join(
                            re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                            for p in paragraphs
                            if len(p.get_text(strip=True)) > 30
                        )

                    # Prepend subtitle if not already in body
                    if subtitle and subtitle.lower() not in body_text.lower():
                        body_text = subtitle + ". " + body_text

            except Exception:
                pass

            # If article was not accessible, use the homepage lead as fallback
            if len(body_text) < 30:
                parent = a.parent
                if parent:
                    # Lead is in a <span class="record"> sibling of <a>
                    for span in parent.find_all('span', class_='record'):
                        t = re.sub(r'\s+', ' ', span.get_text()).strip()
                        if len(t) > 30:
                            body_text = t
                            break

            # Last fallback: use title as body
            if len(body_text) < 10:
                body_text = art_title

            # Use the article title if longer/richer than the homepage title
            final_title = art_title if len(art_title) >= len(title) else title

            clean = clean_source_text(body_text, "record.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "record.pt",
                "year": str(year),
                "title": final_title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in Record 2005 extractor (year {year}): {str(ex)}")
        print(f"ERROR in record 2005 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def record_extractor_2006(url, year, logger):
    """
    Record extractor (2006-2007).

    In 2006 the site migrated to a new layout with hashed URLs:
      noticia[4hexchars].html?id=XXXXXX&idCanal=YY

    Homepage:
      - Headline:  <a class="v18b_red">TITLE</a>
                   <span class="v12b_black">SUBTITLE</span>
                   <td class="v12_black">LEAD</td> (next row)
      - Featured: <a class="v9b_red" href="noticia...">TITLE</a>
                  <span class="v9_black">SUBTITLE</span>
      - Latest/All: <a class="v9b_red">CATEGORY - </a>
                    <a class="v9_black" href="noticia...">TITLE</a>
      - Matches/Columns: <a class="v9_black" href="noticia...">TITLE</a>

    Article page (2006-2007 layout — same CMS as 2005):
      - Title: <span class="tituleira18red1">
      - Subtitle: <span class="acinza12b">
      - Body: <aux> tag inside <span class="apreto12n">
      - Fallback: all <p> with more than 30 chars
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)
        base_site = match.group(2)

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: 2006 URL pattern — noticia[hex].html?id=NUMBER
            if not re.search(r'noticia[0-9a-f]+\.html\?id=\d+', href, re.IGNORECASE):
                continue

            # Build article URL
            if href.startswith('http'):
                article_url = href if 'arquivo.pt' in href else arquivo_prefix + href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                article_url = arquivo_prefix + base_site + "/" + href.lstrip('/')

            article_url = re.sub(r'(https?:/)([^/])', r'\1/\2', article_url)
            article_url = article_url.split('#')[0].strip()

            if article_url in visited:
                continue
            visited.add(article_url)

            # Homepage title
            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            if len(title) < 5:
                continue

            # Homepage subtitle: immediate <span class="v9_black"|"v12b_black"> sibling
            homepage_sub = ""
            next_span = a.find_next_sibling('span')
            if next_span and any(c in (next_span.get('class') or [])
                                 for c in ['v9_black', 'v12b_black']):
                homepage_sub = re.sub(r'\s+', ' ', next_span.get_text()).strip()

            # Headline lead: <td class="v12_black"> in next table row
            homepage_lead = ""
            if 'v18b_red' in (a.get('class') or []):
                td = a.find_parent('td')
                if td:
                    parent_tr = td.find_parent('tr')
                    if parent_tr:
                        for sib_tr in parent_tr.find_next_siblings('tr'):
                            td2 = sib_tr.find('td', class_='v12_black')
                            if td2:
                                homepage_lead = re.sub(r'\s+', ' ', td2.get_text()).strip()
                                break

            # Fetch the article to extract the full body
            body_text = ""
            art_title = title

            # Extract homepage URL timestamp for snapshot lookup
            ts_match = re.search(r'/replay/(\d+)/', url)
            homepage_ts = ts_match.group(1) if ts_match else "20060601000000"

            # Extract original article URL (without Arquivo.pt prefix)
            orig_match = re.search(r'/replay/\d+/(https?://.+)', article_url)
            orig_article_url = orig_match.group(1) if orig_match else ""

            def _fetch_and_parse_article(fetch_url):
                """Fetch and extract article body from a URL."""
                nonlocal art_title
                try:
                    r = requests.get(fetch_url, headers=headers, timeout=15)
                    if r.status_code != 200:
                        return ""
                    r.encoding = r.apparent_encoding
                    s = BeautifulSoup(r.text, 'lxml')

                    # Article title: <span class="tituleira18red1"> (2006-2008 layout)
                    title_elem = s.find('span', class_='tituleira18red1')
                    if title_elem:
                        t = re.sub(r'\s+', ' ', title_elem.get_text()).strip()
                        if len(t) >= len(art_title):
                            art_title = t

                    # Article subtitle
                    art_sub = ""
                    if title_elem:
                        sub_elem = title_elem.find_next('span', class_='acinza12b')
                        if sub_elem:
                            art_sub = re.sub(r'\s+', ' ', sub_elem.get_text()).strip()

                    # Body 1: <aux> tag
                    aux_tags = s.find_all('aux')
                    body = " ".join(
                        re.sub(r'\s+', ' ', tag.get_text(separator=' ')).strip()
                        for tag in aux_tags
                        if len(tag.get_text(strip=True)) > 30
                    ) if aux_tags else ""

                    # Body 2: <td class="v12_black"> (2006 table layout)
                    if len(body) < 50:
                        tds = s.find_all('td', class_='v12_black')
                        body = " ".join(
                            re.sub(r'\s+', ' ', td.get_text(separator=' ', strip=True))
                            for td in tds
                            if len(td.get_text(strip=True)) > 50
                        )

                    # Body 3: all <p>
                    if len(body) < 50:
                        for tag in s(["script", "style", "form", "select",
                                      "img", "noscript", "nav", "footer"]):
                            tag.decompose()
                        body = " ".join(
                            re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                            for p in s.find_all('p')
                            if len(p.get_text(strip=True)) > 30
                        )

                    if art_sub and art_sub.lower() not in body.lower():
                        body = art_sub + ". " + body

                    return body
                except Exception:
                    return ""

            # Attempt 1: URL with homepage timestamp
            body_text = _fetch_and_parse_article(article_url)

            # Attempt 2: if 404, find closest snapshot via API
            if len(body_text) < 50 and orig_article_url:
                closest = get_closest_url(orig_article_url, homepage_ts)
                if closest and closest != article_url:
                    body_text = _fetch_and_parse_article(closest)

            # Final fallback: use homepage lead/subtitle/title
            if len(body_text) < 30:
                body_text = homepage_lead or homepage_sub or art_title

            # Use article title if more informative than homepage title
            final_title = art_title if len(art_title) >= len(title) else title

            clean = clean_source_text(body_text, "record.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "record.pt",
                "year": str(year),
                "title": final_title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in Record 2006 extractor (year {year}): {str(ex)}")
        print(f"ERROR in record 2006 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def record_extractor_2007_2008(url, year, logger):
    """
    Record extractor (2007-2008).

    In 2007 the site returned to the classic URL format:
      noticia.asp?id=XXXXXX&idCanal=YY

    Homepage (different layout from 2006):
      - Headline:  <a class="tituleira18red1">TITLE</a>
                   <br><span class="apreto12">SUBTITLE</span>
                   <td class="apreto12n">LEAD</td> (next table row)
      - Featured: <a class="apreto12" href="noticia...">TITLE</a>
                  <br><span class="ared10">CATEGORY</span>
                  <br><span class="apreto10">LEAD</span>
      - Latest:    <a class="apreto10" href="noticia..."><span class="ared10">CAT</span> - TITLE</a>

    Article page (same CMS as 2005-2006):
      - Title: <span class="tituleira18red1">
      - Subtitle: <span class="acinza12b">
      - Body: <aux> tag
      - Fallback: all <p> with more than 30 chars
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)
        base_site = match.group(2)

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: 2007 URL format — noticia.asp?id=NUMBER
            if not re.search(r'noticia\.asp\?id=\d+', href, re.IGNORECASE):
                continue

            # Build article URL
            if href.startswith('http'):
                article_url = href if 'arquivo.pt' in href else arquivo_prefix + href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                article_url = arquivo_prefix + base_site + "/" + href.lstrip('/')

            article_url = re.sub(r'(https?:/)([^/])', r'\1/\2', article_url)
            article_url = article_url.split('#')[0].strip()

            # Homepage title (validated BEFORE marking as visited)
            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            # For "últimas", text includes "CATEGORY - Title" — strip the prefix
            title = re.sub(r'^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]{3,30}\s+-\s+', '', title).strip()

            # Skip links whose text is a timestamp (e.g. 18:11) — don't add to visited
            # so the next link with the real title for the same URL is still processed
            if re.match(r'^\d{1,2}:\d{2}$', title):
                continue

            if len(title) < 5:
                continue

            if article_url in visited:
                continue
            visited.add(article_url)

            a_classes = a.get('class') or []

            # Headline lead: <td class="apreto12n"> in the next table row
            homepage_lead = ""
            if 'tituleira18red1' in a_classes:
                # Search in same cell or next table row
                parent_td = a.find_parent('td')
                if parent_td:
                    lead_td = parent_td.find_next('td', class_='apreto12n')
                    if lead_td:
                        homepage_lead = re.sub(r'\s+', ' ', lead_td.get_text()).strip()

            # Featured lead: <span class="apreto10"> in the same <td>
            homepage_sub = ""
            if not homepage_lead:
                # Check for featured lead span
                parent_td = a.find_parent('td')
                if parent_td:
                    sub_span = parent_td.find('span', class_='apreto10')
                    if sub_span:
                        homepage_sub = re.sub(r'\s+', ' ', sub_span.get_text()).strip()
                if not homepage_sub:
                    # Try direct sibling span
                    sib = a.find_next_sibling('span')
                    if sib and 'ared10' not in (sib.get('class') or []):
                        t = re.sub(r'\s+', ' ', sib.get_text()).strip()
                        if len(t) > 20:
                            homepage_sub = t

            # Fetch the article to extract the full body
            body_text = ""
            art_title = title

            ts_match = re.search(r'/replay/(\d+)/', url)
            homepage_ts = ts_match.group(1) if ts_match else "20071217000000"

            orig_match = re.search(r'/replay/\d+/(https?://.+)', article_url)
            orig_article_url = orig_match.group(1) if orig_match else ""

            def _fetch_and_parse_article_2007(fetch_url):
                nonlocal art_title
                try:
                    r = requests.get(fetch_url, headers=headers, timeout=15)
                    if r.status_code != 200:
                        return ""
                    r.encoding = r.apparent_encoding
                    s = BeautifulSoup(r.text, 'lxml')

                    title_elem = s.find('span', class_='tituleira18red1')
                    if title_elem:
                        t = re.sub(r'\s+', ' ', title_elem.get_text()).strip()
                        if len(t) >= len(art_title):
                            art_title = t

                    art_sub = ""
                    if title_elem:
                        sub_elem = title_elem.find_next('span', class_='acinza12b')
                        if sub_elem:
                            art_sub = re.sub(r'\s+', ' ', sub_elem.get_text()).strip()

                    # Corpo 1: tag <aux>
                    aux_tags = s.find_all('aux')
                    body = " ".join(
                        re.sub(r'\s+', ' ', tag.get_text(separator=' ')).strip()
                        for tag in aux_tags
                        if len(tag.get_text(strip=True)) > 30
                    ) if aux_tags else ""

                    # Corpo 2: <td class="apreto12n">
                    if len(body) < 50:
                        tds = s.find_all('td', class_='apreto12n')
                        body = " ".join(
                            re.sub(r'\s+', ' ', td.get_text(separator=' ', strip=True))
                            for td in tds
                            if len(td.get_text(strip=True)) > 50
                        )

                    # Body 3: all <p>
                    if len(body) < 50:
                        for tag in s(["script", "style", "form", "select",
                                      "img", "noscript", "nav", "footer"]):
                            tag.decompose()
                        body = " ".join(
                            re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                            for p in s.find_all('p')
                            if len(p.get_text(strip=True)) > 30
                        )

                    if art_sub and art_sub.lower() not in body.lower():
                        body = art_sub + ". " + body

                    return body
                except Exception:
                    return ""

            # Attempt 1: URL with homepage timestamp
            body_text = _fetch_and_parse_article_2007(article_url)

            # Attempt 2: if empty, find closest snapshot via API
            if len(body_text) < 50 and orig_article_url:
                closest = get_closest_url(orig_article_url, homepage_ts)
                if closest and closest != article_url:
                    body_text = _fetch_and_parse_article_2007(closest)

            # Final fallback: use homepage lead/subtitle/title
            if len(body_text) < 30:
                body_text = homepage_lead or homepage_sub or art_title

            final_title = art_title if len(art_title) >= len(title) else title

            clean = clean_source_text(body_text, "record.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "record.pt",
                "year": str(year),
                "title": final_title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in Record 2007 extractor (year {year}): {str(ex)}")
        print(f"ERROR in record 2007 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list


def record_extractor_2009_2010(url, year, logger):
    """
    Record extractor (2009-2010).

    In 2009 the site migrated to GUID-format IDs:
      noticia.aspx?id=GUID&idCanal=GUID

    Homepage (same layout as 2007/2008):
      - Headline:  <a class="tituleira18red1">TITLE</a>
                   <td class="apreto12n">LEAD</td>
      - Featured: <a class="apreto12" href="noticia.aspx?id=...">TITLE</a>
                  <br/><span class="ared10">CATEGORY</span>
                  <br/><span class="apreto10">FULL LEAD</span>
      - Columns:   <a class="apreto12" href="noticia.aspx?id=...">TITLE</a>

    Article page: same structure as 2007/2008.
    """
    article_list = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'lxml')

        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', url)
        if not match:
            return []
        arquivo_prefix = match.group(1)
        base_site = match.group(2)

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filter: 2009+ URL format — noticia.aspx?id=GUID
            if not re.search(r'noticia\.aspx\?id=[\w-]+', href, re.IGNORECASE):
                continue

            # Build article URL
            if href.startswith('http'):
                article_url = href if 'arquivo.pt' in href else arquivo_prefix + href
            elif href.startswith('/noFrame'):
                article_url = "https://arquivo.pt" + href
            else:
                article_url = arquivo_prefix + base_site + "/" + href.lstrip('/')

            article_url = re.sub(r'(https?:/)([^/])', r'\1/\2', article_url)
            article_url = article_url.split('#')[0].strip()
            # Normalize to lowercase for case-insensitive dedup (GUIDs appear in mixed case)
            article_url_key = article_url.lower()

            # Homepage title (validated BEFORE marking as visited)
            title = re.sub(r'\s+', ' ', a.get_text()).strip()
            # Strip "CATEGORY - " prefix from "últimas" links
            title = re.sub(r'^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]{3,30}\s+-\s+', '', title).strip()

            # Skip links with timestamp (15:42) or date (19-05-2009) text — don't add to visited
            if re.match(r'^\d{1,2}:\d{2}$', title) or re.match(r'^\d{2}-\d{2}-\d{4}$', title):
                continue

            if len(title) < 5:
                continue

            if article_url_key in visited:
                continue
            visited.add(article_url_key)

            a_classes = a.get('class') or []

            # Headline lead: <td class="apreto12n"> in the next table row
            homepage_lead = ""
            if 'tituleira18red1' in a_classes:
                parent_td = a.find_parent('td')
                if parent_td:
                    lead_td = parent_td.find_next('td', class_='apreto12n')
                    if lead_td:
                        homepage_lead = re.sub(r'\s+', ' ', lead_td.get_text()).strip()

            # Featured lead: <span class="apreto10"> in the same <td>
            homepage_sub = ""
            if not homepage_lead:
                parent_td = a.find_parent('td')
                if parent_td:
                    sub_span = parent_td.find('span', class_='apreto10')
                    if sub_span:
                        homepage_sub = re.sub(r'\s+', ' ', sub_span.get_text()).strip()

            # Fetch the article to extract the full body
            body_text = ""
            art_title = title

            ts_match = re.search(r'/replay/(\d+)/', url)
            homepage_ts = ts_match.group(1) if ts_match else "20090520000000"

            orig_match = re.search(r'/replay/\d+/(https?://.+)', article_url)
            orig_article_url = orig_match.group(1) if orig_match else ""

            def _fetch_and_parse_article_2009(fetch_url):
                nonlocal art_title
                try:
                    r = requests.get(fetch_url, headers=headers, timeout=15)
                    if r.status_code != 200:
                        return ""
                    r.encoding = r.apparent_encoding
                    s = BeautifulSoup(r.text, 'lxml')

                    title_elem = s.find('span', class_='tituleira18red1')
                    if title_elem:
                        t = re.sub(r'\s+', ' ', title_elem.get_text()).strip()
                        if len(t) >= len(art_title):
                            art_title = t

                    art_sub = ""
                    if title_elem:
                        sub_elem = title_elem.find_next('span', class_='acinza12b')
                        if sub_elem:
                            art_sub = re.sub(r'\s+', ' ', sub_elem.get_text()).strip()

                    # Corpo 1: tag <aux>
                    aux_tags = s.find_all('aux')
                    body = " ".join(
                        re.sub(r'\s+', ' ', tag.get_text(separator=' ')).strip()
                        for tag in aux_tags
                        if len(tag.get_text(strip=True)) > 30
                    ) if aux_tags else ""

                    # Corpo 2: <td class="apreto12n">
                    if len(body) < 50:
                        tds = s.find_all('td', class_='apreto12n')
                        body = " ".join(
                            re.sub(r'\s+', ' ', td.get_text(separator=' ', strip=True))
                            for td in tds
                            if len(td.get_text(strip=True)) > 50
                        )

                    # Body 3: all <p>
                    if len(body) < 50:
                        for tag in s(["script", "style", "form", "select",
                                      "img", "noscript", "nav", "footer"]):
                            tag.decompose()
                        body = " ".join(
                            re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                            for p in s.find_all('p')
                            if len(p.get_text(strip=True)) > 30
                        )

                    if art_sub and art_sub.lower() not in body.lower():
                        body = art_sub + ". " + body

                    return body
                except Exception:
                    return ""

            # Attempt 1: direct URL with homepage timestamp
            body_text = _fetch_and_parse_article_2009(article_url)

            # Attempt 2: nearest snapshot via API
            if len(body_text) < 50 and orig_article_url:
                closest = get_closest_url(orig_article_url, homepage_ts)
                if closest and closest != article_url:
                    body_text = _fetch_and_parse_article_2009(closest)

            # Final fallback: use homepage lead/subtitle/title
            if len(body_text) < 30:
                body_text = homepage_lead or homepage_sub or art_title

            final_title = art_title if len(art_title) >= len(title) else title

            clean = clean_source_text(body_text, "record.pt")
            if not clean:
                continue

            article_list.append({
                "link": article_url,
                "source": "record.pt",
                "year": str(year),
                "title": final_title,
                "body_text": clean
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in record 2009 extractor (year {year}): {str(ex)}")
        print(f"Error in record 2009 extractor: {str(ex)}")
        import traceback
        print(traceback.format_exc())

    return article_list

def record_extractor_2011(url, year, logger=None):
    """
    Extractor for Record (~2009-2013, record.xl.pt era).

    Strategy: 3-pass extraction directly from the received HTML,
    without visiting individual article pages (avoids timeouts and 403s).

    Pass 1 — Rich blocks (div#news_highlight_container_NNNN):
        Each block contains a title (a.vermelho22), subtitle (a.preto11.bold),
        and lead (a.highlight-summary).

    Pass 2 — Sidebar lists (div.lnkArea.descNoticia):
        "most read", "most commented", etc. Captures titles
        not present in Pass 1 blocks.

    Pass 3 — General sweep for interior.aspx:
        Catches any remaining interior.aspx?content_id= links
        not captured in earlier passes.

    body_text is built from subtitle + lead available on the listing page.
    Falls back to title when no lead is available.
    """
    article_list = []
    source = "record.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    # Paths to skip: galleries, betting, polls, e-paper
    BLACKLIST_PATHS = [
        'galerias/fotos', 'galerias/videos', 'galerias/record_tv',
        'apostas', 'poll', 'epaper', 'classif', 'resultados'
    ]

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        html = response.text
        soup = BeautifulSoup(html, 'lxml')

        # Detect Arquivo.pt timestamp dynamically
        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        if not ts_match:
            ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""
        base_arquivo = f"https://arquivo.pt/noFrame/replay/{timestamp}/" if timestamp else ""

        def build_url(href):
            """Reconstruct Arquivo.pt URLs from relative or absolute hrefs."""
            if not href:
                return None
            href = href.split('#')[0].strip()
            if not href:
                return None
            if 'arquivo.pt' in href:
                return href
            if href.startswith('/noFrame/'):
                return 'https://arquivo.pt' + href
            if href.startswith('/'):
                return base_arquivo + 'http://www.record.xl.pt' + href
            return None

        def is_blacklisted(u):
            if not u:
                return True
            ul = u.lower()
            return any(b in ul for b in BLACKLIST_PATHS)

        def clean_title(t):
            """Strip vote/comment/visit counters from link text."""
            t = re.sub(r'\s*\[[\d\s]+(votos?|comentários?|visitas?)\]', '', t, flags=re.IGNORECASE)
            return re.sub(r'\s+', ' ', t).strip()

        articles = {}  # cid -> {title, body_text, link}

        # ============================================================
        # PASS 1: Rich blocks with title + subtitle + lead
        # ============================================================
        for container in soup.find_all('div', id=re.compile(r'^news_highlight_container_(\d+)$')):
            m = re.search(r'news_highlight_container_(\d+)', container.get('id', ''))
            if not m:
                continue
            cid = m.group(1)

            # Main title
            title_tag = container.select_one('a.vermelho22')
            title = clean_title(title_tag.get_text(separator=' ', strip=True)) if title_tag else ''
            if len(title) < 10:
                continue

            # Subtitle
            sub_tag = container.select_one('a.preto11.bold')
            subtitle = sub_tag.get_text(strip=True) if sub_tag else ''

            # Lead
            lead_tag = container.select_one('a.highlight-summary')
            lead = lead_tag.get_text(strip=True) if lead_tag else ''

            # Canonical link: prefer interior.aspx, fall back to default.aspx
            link_tag = container.select_one('a[href*="interior.aspx"][href*="content_id="]')
            if not link_tag:
                link_tag = container.select_one(f'a[href*="content_id={cid}"]')
            if not link_tag:
                continue

            article_url = build_url(link_tag['href'])
            if not article_url or is_blacklisted(article_url):
                continue

            body = ' '.join(filter(None, [subtitle, lead]))
            if cid not in articles:
                articles[cid] = {'title': title, 'body_text': body, 'link': article_url}

        # ============================================================
        # PASS 2: Sidebar lists (most read, most commented, etc.)
        # ============================================================
        for div in soup.find_all('div', class_='lnkArea descNoticia'):
            a = div.find('a', href=True)
            if not a:
                continue
            href = a['href']
            if 'content_id=' not in href:
                continue
            m = re.search(r'content_id=(\d+)', href)
            if not m:
                continue
            cid = m.group(1)
            if cid in articles:
                continue
            title = clean_title(a.get_text(strip=True))
            if len(title) < 10:
                continue
            article_url = build_url(href)
            if not article_url or is_blacklisted(article_url):
                continue
            articles[cid] = {'title': title, 'body_text': '', 'link': article_url}

        # ============================================================
        # PASS 3: General sweep — remaining interior.aspx links
        # ============================================================
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'interior.aspx' not in href or 'content_id=' not in href or '#' in href:
                continue
            m = re.search(r'content_id=(\d+)', href)
            if not m:
                continue
            cid = m.group(1)
            if cid in articles:
                continue
            title = clean_title(a.get_text(strip=True))
            if len(title) < 10:
                continue
            article_url = build_url(href)
            if not article_url or is_blacklisted(article_url):
                continue
            articles[cid] = {'title': title, 'body_text': '', 'link': article_url}

        # ============================================================
        # Build final list
        # ============================================================
        for cid, art in articles.items():
            body = art['body_text']
            # Fall back to title if no lead/subtitle available
            if len(body) < 20:
                body = art['title']
            body = clean_source_text(body, source)
            if not body:
                body = art['title']
            article_list.append({
                'link': art['link'],
                'source': source,
                'year': str(year),
                'title': art['title'],
                'body_text': body[:5000],
            })

    except Exception as ex:
        if logger:
            logger.error(f"Error in record 2011 extractor: {str(ex)}")
        print(f"Error in record_extractor_2011: {str(ex)}")

    return article_list

def record_extractor_2013(snapshot_url, year, logger):
    """
    Extractor for Record 2013 (also compatible with 2011-2014).

    Strategy:
    1. Find all news_highlight_container_XXXXX blocks
    2. For each block: extract title, subtitle, lead, link
    3. Look for related links inside hp_related
    4. Deduplicate by content_id
    """
    article_list = []
    source = "record.pt"
    
    try:
        response = requests.get(snapshot_url, timeout=30)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = {}  # content_id -> article_data (deduplication)

        # ====================================================================
        # PASS 1: Main featured blocks (news_highlight_container_)
        # ====================================================================
        containers = soup.find_all('div', id=re.compile(r'^news_highlight_container_(\d+)$'))
        
        for container in containers:
            cid_match = re.search(r'news_highlight_container_(\d+)', container.get('id', ''))
            if not cid_match:
                continue
            
            content_id = cid_match.group(1)
            
            # Extract title (tituloprincipal, titulosecundario, or titulopremium)
            title_elem = container.select_one(
                'a.tituloprincipal, a.titulosecundario, a.titulopremium'
            )
            title = ''
            if title_elem:
                title = title_elem.get_text(strip=True)
                title = re.sub(r'\s+', ' ', title).strip()
                title = re.sub(r'\s*\[[\d\s]+(votos?|comentários?|visitas?|images?|foto?)\]', '', 
                              title, flags=re.IGNORECASE)
            
            if len(title) < 15:
                continue
            
            # Subtitle
            subtitle_elem = container.select_one('a.subtitulo')
            subtitle = subtitle_elem.get_text(strip=True) if subtitle_elem else ''

            # Lead
            lead_elem = container.select_one('div.texto_destaques')
            lead = lead_elem.get_text(strip=True) if lead_elem else ''

            # URL
            article_url = None
            if title_elem and title_elem.get('href'):
                article_url = title_elem['href']
            
            if not article_url or 'content_id=' not in article_url:
                continue
            
            # Build body_text
            body_parts = []
            if subtitle:
                body_parts.append(subtitle)
            if lead:
                body_parts.append(lead)
            body_text = ' '.join(body_parts)
            body_text = clean_source_text(body_text, source)
            
            if not article_url:
                continue
            
            if content_id not in articles:
                articles[content_id] = {
                    'title': title,
                    'body_text': body_text,
                    'link': article_url,
                    'source': source,
                    'year': str(year)
                }
            
            # ================================================================
            # Links Relacionados (dentro do mesmo container)
            # ================================================================
            hp_related = container.select_one('div.hp_related')
            if hp_related:
                related_links = hp_related.find_all('li')
                
                for li in related_links:
                    rel_link = li.find('a', href=True)
                    if not rel_link:
                        continue
                    
                    rel_cid_match = re.search(r'content_id=(\d+)', rel_link.get('href', ''))
                    if not rel_cid_match:
                        continue
                    
                    rel_cid = rel_cid_match.group(1)
                    if rel_cid in articles:
                        continue
                    
                    rel_title = rel_link.get_text(strip=True)
                    rel_title = re.sub(r'\s+', ' ', rel_title).strip()
                    rel_title = re.sub(r'\s*\[[\d\s]+(votos?|comentários?|visitas?|images?|foto?)\]', '', 
                                      rel_title, flags=re.IGNORECASE)
                    
                    if len(rel_title) < 10:
                        continue
                    
                    rel_url = rel_link['href']
                    if not rel_url or 'content_id=' not in rel_url:
                        continue
                    
                    articles[rel_cid] = {
                        'title': rel_title,
                        'body_text': rel_title,
                        'link': rel_url,
                        'source': source,
                        'year': str(year)
                    }
        
        # ====================================================================
        # PASS 2: General sweep for interior.aspx (fallback)
        # ====================================================================
        all_links = soup.find_all('a', href=True)
        
        for a in all_links:
            href = a['href']
            
            if 'interior.aspx' not in href or 'content_id=' not in href:
                continue
            
            if '#' in href:
                continue
            
            cid_match = re.search(r'content_id=(\d+)', href)
            if not cid_match:
                continue
            
            content_id = cid_match.group(1)
            if content_id in articles:
                continue
            
            title = a.get_text(strip=True)
            title = re.sub(r'\s+', ' ', title).strip()
            title = re.sub(r'\s*\[[\d\s]+(votos?|comentários?|visitas?|images?|foto?)\]', '', 
                          title, flags=re.IGNORECASE)
            
            if len(title) < 10 or len(title) > 250:
                continue
            
            articles[content_id] = {
                'title': title,
                'body_text': title,
                'link': href,
                'source': source,
                'year': str(year)
            }
        
        # ====================================================================
        # BUILD FINAL LIST
        # ====================================================================
        for content_id, article in articles.items():
            body = article['body_text']
            
            if len(body) < 15:
                body = article['title']
            
            body = clean_source_text(body, source)
            
            if not body:
                body = article['title']
            
            article_list.append({
                'link': article['link'],
                'source': source,
                'year': str(year),
                'title': article['title'],
                'body_text': body[:5000]
            })
    
    except Exception as ex:
        if logger:
            logger.error(f"Error in Record 2013 extractor: {str(ex)}")
        print(f"Error in record_extractor_2013: {str(ex)}")
    
    return article_list

def record_extractor(url, year, logger):
    try:
        r = requests.get(url, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('h1, .title, .newsslot h2, .noticia_box, b, strong')
        return generic_clean(elements, url, soup, "record.pt")
    except: return []


def sapo_extractor_2001(url, year, logger=None):
    """
    SAPO 2001 extractor — infordesporto.pt

    Confirmed structure (sapo_homepage_2001.html):
      - Site: infordesporto.pt (own domain, not yet migrated to sapo.pt)
      - Articles: RELATIVE hrefs with 'Noticias' in path ending in .asp
        e.g. "Futebol/Noticias/2001/Maio/15/porto01.asp"
             "ANDEBOL/Noticias/2001/Mai/15/index.asp" ← skip (index.asp = section)
      - Article body: <font> tags with text > 80 chars (table layout)
        The 2001 interior uses <font> for body, not <p>

    Previous version bug:
      - Filter ".asp + (noticias OR \d{2}\.asp$)" matched 70 links including
        27 junk ones (Christmas specials, Figo pages, live goals, etc.)
      - Now uses 'Noticias' (capitalized, as in real path) + .asp + non-index
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 403 or len(response.text) < 100:
            if logger: logger.warning(f'SAPO: 403/vazio em {url}')
            raise ConnectionError('403')
        response.encoding = response.apparent_encoding
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        if not ts_match:
            ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""

        # Detect the real domain of the archived site dynamically
        url_match = re.search(r'wbinfo\.url\s*=\s*"(https?://[^/"]+)', html)
        if url_match:
            base_site = url_match.group(1).rstrip('/')
        else:
            site_m = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', response.url)
            base_site = site_m.group(1) if site_m else "http://www.infordesporto.pt"
        base_arquivo = f"https://arquivo.pt/noFrame/replay/{timestamp}/" if timestamp else ""

        def build_url(href):
            if not href: return None
            href = href.split('#')[0].strip()
            if not href: return None
            if 'arquivo.pt' in href: return href
            if href.startswith('/noFrame/'): return 'https://arquivo.pt' + href
            if href.startswith('/'): return base_arquivo + base_site + href
            return base_arquivo + base_site + '/' + href

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
                # Filter: 'Noticias' in path + .asp + not index.asp
            if 'Noticias' not in href: continue
            if not href.lower().endswith('.asp'): continue
            if 'index.asp' in href.lower(): continue
            if 'javascript' in href.lower(): continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            article_url = build_url(href)
            if not article_url: continue
            clean_url = article_url.split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = art_r.apparent_encoding
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'form']): tag.decompose()

                # Known noise strings in infordesporto.pt 2001
                NOISE_2001 = [
                    'internet grátis', 'leilões | sms', 'salas de cinema',
                    'andebol | atletismo | automobilismo',  # sports category footer
                    '| andebol | atletismo |',               # footer variant
                    'trivia futebol trivia selecção',        # menu de jogos
                    'este site só funciona correctamente',
                    '© 2001 infordesporto', 'infordesporto s.a.',
                    'include file not found',                # erro ASP
                ]

                def is_noise(text):
                    tl = text.lower()
                    return any(n in tl for n in NOISE_2001)

                # Body is in <font> with > 100 chars (menu items have ~96)
                body_parts = []
                for font in art_soup.find_all('font'):
                    t = re.sub(r'\s+', ' ', font.get_text(separator=' ', strip=True))
                    if len(t) > 100 and not is_noise(t):
                        body_parts.append(t)

                # Fallback: long paragraphs without noise
                if not body_parts:
                    for p in art_soup.find_all('p'):
                        t = re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                        if len(t) > 60 and not is_noise(t):
                            body_parts.append(t)

                body_text = ' '.join(body_parts[:5])
                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2001 extractor: {str(ex)}")
        print(f"Error in sapo_extractor_2001: {str(ex)}")

    return article_list


def sapo_extractor_2002(url, year, logger=None):
    """
    SAPO 2002 extractor — infordesporto.sapo.pt

    Confirmed structure (sapo_homepage_2002.html):
      - Site: infordesporto.sapo.pt
      - Articles: RELATIVE hrefs with a unique pattern:
          "Notícia Futebol_FutCroSLBLEIRIA_210902_8248.asp"
          "Notícia Futebol_FutJesualdo_210902_8256.asp"
        Always start with "Notícia " (accented, with space) + category + data + .asp
      - Body: long <font> and <p> tags (same layout as infordesporto)

    Previous version bug (sapo_extractor_2002_2007):
      - Filtered by 'id=' or 'noticia' (no accent, lowercase)
      - Real pattern is "Notícia " (accented, capitalized) → caught ~0 articles
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 403 or len(response.text) < 100:
            if logger: logger.warning(f'SAPO: 403/vazio em {url}')
            raise ConnectionError('403')
        response.encoding = response.apparent_encoding
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        if not ts_match:
            ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""

        # Detect the real domain of the archived site dynamically
        url_match = re.search(r'wbinfo\.url\s*=\s*"(https?://[^/"]+)', html)
        if url_match:
            base_site = url_match.group(1).rstrip('/')
        else:
            site_m = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', response.url)
            base_site = site_m.group(1) if site_m else "http://www.infordesporto.pt"
        base_arquivo = f"https://arquivo.pt/noFrame/replay/{timestamp}/" if timestamp else ""

        def build_url(href):
            if not href: return None
            href = href.split('#')[0].strip()
            if not href: return None
            if 'arquivo.pt' in href: return href
            if href.startswith('/noFrame/'): return 'https://arquivo.pt' + href
            # URL-encode: href "Notícia Futebol_..." contains spaces and accents
            from urllib.parse import quote
            encoded = quote(href, safe='/:@!$&\'()*+,;=')
            if href.startswith('/'):
                return base_arquivo + base_site + encoded
            return base_arquivo + base_site + '/' + encoded

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            # 2002 pattern: starts with "Notícia " and ends in .asp
            if not (href.startswith('Notícia ') or href.startswith('Not\u00edcia ')):
                continue
            if not href.lower().endswith('.asp'):
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            article_url = build_url(href)
            if not article_url: continue
            clean_url = article_url.split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = art_r.apparent_encoding
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'form']): tag.decompose()

                body_parts = []
                NOISE_2002 = [
                    'internet grátis', 'leilões | sms', 'salas de cinema',
                    '| andebol | atletismo |', 'andebol | atletismo | automobilismo',
                    'trivia futebol', 'este site só funciona',
                    '© 2002 infordesporto', '© infordesporto', 'infordesporto s.a.',
                    'include file not found',
                ]
                def is_noise_2002(t): return any(n in t.lower() for n in NOISE_2002)

                for font in art_soup.find_all('font'):
                    t = re.sub(r'\s+', ' ', font.get_text(separator=' ', strip=True))
                    if len(t) > 100 and not is_noise_2002(t):
                        body_parts.append(t)
                if not body_parts:
                    for p in art_soup.find_all('p'):
                        t = re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                        if len(t) > 80 and not is_noise_2002(t):
                            body_parts.append(t)

                body_text = ' '.join(body_parts[:5])
                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2002 extractor: {str(ex)}")
        print(f"Error in sapo_extractor_2002: {str(ex)}")

    return article_list


def sapo_extractor_2003_2004(url, year, logger=None):
    """
    SAPO extractor (2003-2004).
    Classic structure. Skips <div seccao="titulo">.
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        actual_url = response.url
        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', actual_url)
        arquivo_prefix = match.group(1) if match else ""
        base_site = match.group(2) if match else ""

        visited_urls = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            
            if 'id=' not in href.lower() and 'noticia' not in href.lower():
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10:
                continue

            if href.startswith("http"): article_url = href if "arquivo.pt" in href else arquivo_prefix + href
            elif href.startswith("/noFrame/"): article_url = "https://arquivo.pt" + href
            elif href.startswith("/"): article_url = arquivo_prefix + base_site + href
            else:
                base_path = actual_url.rsplit('/', 1)[0]
                article_url = base_path + "/" + href

            clean_url = article_url.split('#')[0]
            if clean_url in visited_urls: continue
            visited_urls.add(clean_url)

            try:
                art_resp = requests.get(clean_url, headers=headers, timeout=15)
                body_text = ""
                if art_resp.status_code == 200:
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "noscript", "iframe"]): 
                        tag.decompose()

                    # Skip the "titulo" seccao division
                    seccao_divs = art_soup.find_all('div', attrs={'seccao': True})
                    if seccao_divs:
                        body_text = " ".join(d.get_text(separator=' ', strip=True) for d in seccao_divs if d.get('seccao') != 'titulo')
                    
                    if len(body_text) < 50:
                        paragraphs = art_soup.find_all('p')
                        body_text = " ".join(p.get_text(separator=' ', strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

                body_text = clean_source_text(body_text, source)

                if len(body_text) > 50 and body_text.lower() != title.lower():
                    article_list.append({"link": clean_url, "source": source, "year": str(year), "title": title, "body_text": body_text[:5000]})
            except Exception:
                continue
    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2003-2004 extractor: {str(ex)}")

    return article_list

def sapo_extractor_2005_2007(url, year, logger=None):
    """
    SAPO extractor (2005-2007).
    Handles text inside <div seccao="titulo"> and applies strict noise filters.
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'lxml')
        actual_url = response.url
        match = re.match(r'(https://arquivo\.pt/noFrame/replay/\d+/)(https?://[^/]+)', actual_url)
        arquivo_prefix = match.group(1) if match else ""
        base_site = match.group(2) if match else ""

        visited_urls = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            
            if 'id=' not in href.lower() and 'noticia' not in href.lower():
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10:
                continue

            if href.startswith("http"): article_url = href if "arquivo.pt" in href else arquivo_prefix + href
            elif href.startswith("/noFrame/"): article_url = "https://arquivo.pt" + href
            elif href.startswith("/"): article_url = arquivo_prefix + base_site + href
            else:
                base_path = actual_url.rsplit('/', 1)[0]
                article_url = base_path + "/" + href

            clean_url = article_url.split('#')[0]
            if clean_url in visited_urls: continue
            visited_urls.add(clean_url)

            try:
                art_resp = requests.get(clean_url, headers=headers, timeout=15)
                body_text = ""
                if art_resp.status_code == 200:
                    art_soup = BeautifulSoup(art_resp.text, 'lxml')
                    for tag in art_soup(["script", "style", "form", "noscript", "iframe"]): 
                        tag.decompose()

                    body_parts = []
                    lixo = [
                        "Para o envio de notícias", "Contactos | Política de Privacidade",
                        "© Infordesporto", "Nenhuma parte deste site", "Desenvolvimento Tecnológico",
                        "Concepção Gráfica", "Camisola C. Europeias", "Camisola Listada", 
                        "Camisola 1º Equip", "Comprar ver mais", "Bandeira Auto", "Mini Kit Alternativo",
                        "_____WB$wombat"
                    ]
                    
                    # In 2005 we must read ALL seccao divs
                    seccao_divs = art_soup.find_all('div', attrs={'seccao': True})
                    for d in seccao_divs:
                        text = d.get_text(separator=' ', strip=True)
                        if len(text) < 20 or text.lower() == title.lower() or any(j.lower() in text.lower() for j in lixo):
                            continue
                        if text not in body_parts:
                            body_parts.append(text)
                    
                    paragraphs = art_soup.find_all('p')
                    for p in paragraphs:
                        text = p.get_text(separator=' ', strip=True)
                        if len(text) < 20 or text.lower() == title.lower() or any(j.lower() in text.lower() for j in lixo):
                            continue
                        if not any(text in bp for bp in body_parts):
                            body_parts.append(text)

                    body_text = " ".join(body_parts)

                body_text = re.sub(r'<[^>]+>', '', body_text)
                body_text = clean_source_text(body_text, source)

                if len(body_text) > 50 and body_text.lower() != title.lower():
                    article_list.append({"link": clean_url, "source": source, "year": str(year), "title": title, "body_text": body_text[:5000]})
            except Exception:
                continue
    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2005-2007 extractor: {str(ex)}")

    return article_list


def sapo_extractor_2009_2013(url, year, logger=None):
    """
    SAPO 2009-2013 extractor — desporto.sapo.pt

    Confirmed structure (sapo_homepage_2009/2010.html + sapo_interior_2009.html):
      - Site: desporto.sapo.pt (full migration from infordesporto)
      - Articles: hrefs containing '/artigo/' and ending in '.html'
        e.g. "http://desporto.sapo.pt/futebol/liga_europa/artigo/2009/12/17/benfica_recebe_aek.html"
      - Article body:
          .article-intro → lead/intro
          .article-txt   → main body
        (confirmed with sapo_interior_2009.html)

    Note: 2008 is a maintenance page on Arquivo.pt — no content available.
    This function covers 2009 and 2010 only.
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 403 or len(response.text) < 100:
            if logger: logger.warning(f'SAPO: 403/empty at {url}')
            raise ConnectionError('403')

        # Force UTF-8 on the homepage
        response.encoding = 'utf-8' 
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        if not ts_match:
            ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""

        site_match = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', url)
        base_site = site_match.group(1) if site_match else "http://desporto.sapo.pt"

        def build_url(href):
            if not href: return None
            href = href.split('#')[0].strip()
            if not href: return None
            if 'arquivo.pt' in href: return href
            if href.startswith('/noFrame/'): return 'https://arquivo.pt' + href
            if href.startswith('/'):
                return f"https://arquivo.pt/noFrame/replay/{timestamp}/{base_site}{href}"
            if href.startswith('http'):
                return f"https://arquivo.pt/noFrame/replay/{timestamp}/{href}"
            return None

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()
            if '/artigo/' not in hl or not hl.endswith('.html'):
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            article_url = build_url(href)
            if not article_url: continue
            clean_url = article_url.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                
                # Force UTF-8 on the article page
                art_r.encoding = 'utf-8'
                
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'form']): tag.decompose()

                body_text = ''
                intro = art_soup.select_one('.article-intro')
                body  = art_soup.select_one('.article-txt')

                parts = []
                if intro:
                    t = re.sub(r'\s+', ' ', intro.get_text(separator=' ', strip=True))
                    if t: parts.append(t)
                if body:
                    t = re.sub(r'\s+', ' ', body.get_text(separator=' ', strip=True))
                    if t: parts.append(t)
                body_text = ' '.join(parts)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(separator=' ', strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 40]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2009-2013 extractor: {str(ex)}")
        print(f"Error in sapo_extractor_2009_2013: {str(ex)}")

    return article_list

def sapo_extractor_2014_2017(url, year, logger=None):
    """
    SAPO 2014-2017 extractor — Ink Framework phase.
    Links contain '/artigo/' (no .html suffix).
    Body is in <div class="entry" itemprop="articleBody">.
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 403 or len(response.text) < 100:
            if logger: logger.warning(f'SAPO: 403/vazio em {url}')
            raise ConnectionError('403')
        
        response.encoding = 'utf-8' 
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        if not ts_match: ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""

        site_match = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', url)
        base_site = site_match.group(1) if site_match else "http://desporto.sapo.pt"

        def build_url(href):
            if not href: return None
            href = href.split('#')[0].strip()
            if not href: return None
            if 'arquivo.pt' in href: return href
            if href.startswith('/noFrame/'): return 'https://arquivo.pt' + href
            if href.startswith('/'): return f"https://arquivo.pt/noFrame/replay/{timestamp}/{base_site}{href}"
            if href.startswith('http'): return f"https://arquivo.pt/noFrame/replay/{timestamp}/{href}"
            return None

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()
            
            # Filter: must contain '/artigo/' or '/artigos/'
            if '/artigo/' not in hl and '/artigos/' not in hl:
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            article_url = build_url(href)
            if not article_url: continue
            clean_url = article_url.split('?')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'form']): tag.decompose()

                body_text = ''
                # 2014-2017: body in div.entry[itemprop=articleBody]
                article_body = art_soup.find('div', class_='entry', itemprop='articleBody')
                if article_body:
                    paragraphs = article_body.find_all('p')
                    parts = [re.sub(r'\s+', ' ', p.get_text(strip=True)) for p in paragraphs if 'ref' not in p.get('class', [])]
                    body_text = ' '.join([t for t in parts if len(t) > 30])

                body_text = clean_source_text(body_text, source)
                
                if len(body_text) > 50 and body_text.lower() != title.lower():
                    article_list.append({
                        'link': clean_url, 'source': source, 'year': str(year),
                        'title': title, 'body_text': body_text[:5000],
                    })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2014-2017 extractor: {str(ex)}")

    return article_list

def sapo_extractor_2018_2019(url, year, logger=None):
    """
    SAPO 2018-2019 extractor — first major redesign.
    Links change to the plural '/artigos/'.
    Body is in <div class="article-body">.
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8' 
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        timestamp = ts_match.group(1) if ts_match else (re.search(r'/replay/(\d+)/', url).group(1) if re.search(r'/replay/(\d+)/', url) else "")
        site_match = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', url)
        base_site = site_match.group(1) if site_match else "http://desporto.sapo.pt"

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/artigos/' not in href.lower():
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            if href.startswith('http') and 'arquivo.pt' not in href:
                article_url = f"https://arquivo.pt/noFrame/replay/{timestamp}/{href}"
            elif href.startswith('/noFrame/'):
                article_url = 'https://arquivo.pt' + href
            elif href.startswith('/'):
                article_url = f"https://arquivo.pt/noFrame/replay/{timestamp}/{base_site}{href}"
            elif 'arquivo.pt' in href:
                article_url = href
            else:
                continue

            clean_url = article_url.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'form']): tag.decompose()

                body_text = ''
                # 2018-2019: body in div.article-body
                article_body = art_soup.find('div', class_='article-body')
                if article_body:
                    paragraphs = article_body.find_all('p')
                    parts = [re.sub(r'\s+', ' ', p.get_text(strip=True)) for p in paragraphs]
                    body_text = ' '.join([t for t in parts if len(t) > 30])

                body_text = clean_source_text(body_text, source)
                
                if len(body_text) > 50 and body_text.lower() != title.lower():
                    article_list.append({
                        'link': clean_url, 'source': source, 'year': str(year),
                        'title': title, 'body_text': body_text[:5000],
                    })
            except Exception:
                continue
    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2018-2019 extractor: {str(ex)}")

    return article_list


def sapo_extractor_2020_2023(url, year, logger=None):
    """
    SAPO 2020-2023 extractor (dark mode / modern era).
    Uses flexible selectors for the article body regardless of CSS class variations.
    """
    article_list = []
    source = "sapo.pt"
    # Modern browser user-agent
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8' 
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Extract Arquivo.pt timestamp for rebuilding internal URLs
        ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""
        site_match = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', url)
        base_site = site_match.group(1) if site_match else "https://desporto.sapo.pt"

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            # Filter: modern article links use plural '/artigos/'
            if '/artigos/' not in href.lower():
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            # Reconstruct URL for Arquivo.pt
            if href.startswith('http') and 'arquivo.pt' not in href:
                article_url = f"https://arquivo.pt/noFrame/replay/{timestamp}/{href}"
            elif href.startswith('/noFrame/'):
                article_url = 'https://arquivo.pt' + href
            elif href.startswith('/'):
                article_url = f"https://arquivo.pt/noFrame/replay/{timestamp}/{base_site}{href}"
            else:
                article_url = href

            clean_url = article_url.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            # Fetch the article page
            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                
                # Aggressively remove noise elements
                for tag in art_soup(['script', 'style', 'form', 'aside', 'figure', 'noscript', 'iframe']): 
                    tag.decompose()

                body_text = ''
                
                # Flexible selector: any div with 'article-body' in its class, fallback to <main>
                article_body = art_soup.find('div', class_=lambda x: x and 'article-body' in x) or art_soup.find('main')

                if article_body:
                    content_div = article_body.find('div', class_=lambda x: x and ('content' in x or 'body' in x)) or article_body
                    paragraphs = content_div.find_all('p')
                    parts = [re.sub(r'\s+', ' ', p.get_text(strip=True)) for p in paragraphs]
                    # Skip short paragraphs (photo captions, footers)
                    body_text = ' '.join([t for t in parts if len(t) > 30])

                body_text = clean_source_text(body_text, source)
                
                if len(body_text) > 50 and body_text.lower() != title.lower():
                    article_list.append({
                        'link': clean_url, 'source': source, 'year': str(year),
                        'title': title, 'body_text': body_text[:5000],
                    })
            except Exception:
                continue
    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2020-2023 extractor: {str(ex)}")

    return article_list

def sapo_extractor_2024(url, year, logger=None):
    """
    SAPO 2024 extractor — modern era (Vite/bundled).
    Extracts text from highly dynamic layouts.
    """
    article_list = []
    source = "sapo.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Extract timestamp and base site
        ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""
        site_match = re.match(r'https?://arquivo\.pt/noFrame/replay/\d+/(https?://[^/]+)', url)
        base_site = site_match.group(1) if site_match else "https://desporto.sapo.pt"

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            # Strict filter: skip navigation/menu links
            if '/artigos/' not in href.lower():
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 10: continue

            # Safe URL reconstruction for Arquivo.pt
            if 'arquivo.pt' in href: article_url = href
            elif href.startswith('/'): article_url = f"https://arquivo.pt/noFrame/replay/{timestamp}/{base_site}{href}"
            else: article_url = f"https://arquivo.pt/noFrame/replay/{timestamp}/{href}"

            clean_url = article_url.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                
                # Strip Vite scripts and bundles from the 2024 layout
                for tag in art_soup(['script', 'style', 'form', 'aside', 'figure', 'noscript', 'iframe']):
                    tag.decompose()

                body_text = ''
                # 2024 structure: main > div.article-body > div.content > p
                main_container = art_soup.find('main') or art_soup.find('div', class_='article-body')
                
                if main_container:
                    content_div = main_container.find('div', class_='content') or main_container
                    paragraphs = content_div.find_all('p')
                    parts = [re.sub(r'\s+', ' ', p.get_text(strip=True)) for p in paragraphs]
                    body_text = ' '.join([t for t in parts if len(t) > 30])

                body_text = clean_source_text(body_text, source)
                
                if len(body_text) > 50 and body_text.lower() != title.lower():
                    article_list.append({
                        'link': clean_url, 'source': source, 'year': str(year),
                        'title': title, 'body_text': body_text[:5000],
                    })
            except Exception:
                continue
    except Exception as ex:
        if logger: logger.error(f"Error in SAPO 2024 extractor: {str(ex)}")

    return article_list

def zap_extractor_2013_2016(url, year, logger=None):
    """
    ZAP 2013-2016 extractor — zap.aeiou.pt (Forceful theme).

    Confirmed structure (zap_homepage_2013-2016.html + zap_interior_2014.html):
      - Homepage: articles linked directly by slug (zap.aeiou.pt/slug-NNNNN)
        Arquivo.pt full URLs already present in hrefs
      - Interior: body in <div class="elements-box"> with <p> paragraphs
        (NOT entry-content — that selector belongs to later years)
      - Article filter: href contains 'zap.aeiou.pt' and ends with slug-NNNNN pattern
        (numeric ID at end, e.g. sporting-vence-no-dragao-45879)

    Previous version bugs:
      - Wrong selector: used 'entry-content' (2021-2022 era)
      - Did not reconstruct Arquivo.pt URLs — requested zap.aeiou.pt directly
      - Output missing 'link', 'source', 'year' fields — incompatible with getArticle
    """
    article_list = []
    source = "zap.aeiou.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    SKIP = ['javascript', 'mailto', 'facebook.com', 'twitter.com',
            'instagram.com', 'youtube.com', '/conta', '/login',
            '/newsletter', '/noticias/desporto', '/thread/']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ts_match = re.search(r'wbinfo\.timestamp\s*=\s*"(\d+)"', html)
        if not ts_match:
            ts_match = re.search(r'/replay/(\d+)/', url)
        timestamp = ts_match.group(1) if ts_match else ""

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            # Filter: must be from zap.aeiou.pt with a numeric ID slug at the end
            if 'zap.aeiou.pt' not in hl: continue
            if any(s in hl for s in SKIP): continue
            if not re.search(r'-\d+$', href.split('?')[0].rstrip('/')): continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 15: continue

            # URL is already a full Arquivo.pt URL
            clean_url = href.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = art_r.apparent_encoding
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                # Body in div.elements-box (confirmed with zap_interior_2014.html)
                body_text = ''
                body_elem = art_soup.select_one('div.elements-box')
                if body_elem:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 40]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in ZAP 2013-2016 extractor: {str(ex)}")
        print(f"Error in zap_extractor_2013_2016: {str(ex)}")

    return article_list


def zap_extractor_2017_2020(url, year, logger=None):
    """
    ZAP 2017-2020 extractor — zap.aeiou.pt (Newspaper/TagDiv theme).

    Confirmed structure (zap_homepage_2017-2020.html + zap_interior_2018.html):
      - Homepage: same slug-with-numeric-ID structure
      - Interior: body in <td class="td-post-content"> with <p>
        (TagDiv Newspaper theme — different from 2013-2016)
      - Ad removal: divs with class 'td-a-rec'

    Previous version bugs:
      - Used 'a.td-image-wrap' to find articles — that element exists but
        get_text() returns nothing → titles came out as None
      - Did not reconstruct URLs / missing required output fields
    """
    article_list = []
    source = "zap.aeiou.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    SKIP = ['javascript', 'mailto', 'facebook.com', 'twitter.com',
            'instagram.com', 'youtube.com', '/conta', '/login',
            '/newsletter', '/noticias/desporto', '/thread/']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            if 'zap.aeiou.pt' not in hl: continue
            if any(s in hl for s in SKIP): continue
            if not re.search(r'-\d+$', href.split('?')[0].rstrip('/')): continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 15: continue

            clean_url = href.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                # zap.aeiou.pt always uses UTF-8; apparent_encoding can misdetect in 2020
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                # Body in td.td-post-content (confirmed with zap_interior_2018.html)
                body_text = ''
                body_elem = art_soup.select_one('td.td-post-content, div.td-post-content')
                if body_elem:
                    # Remove TagDiv theme ads
                    for ads in body_elem.find_all(class_=lambda c: c and 'td-a-rec' in str(c)):
                        ads.decompose()
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 40]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in ZAP 2017-2020 extractor: {str(ex)}")
        print(f"Error in zap_extractor_2017_2020: {str(ex)}")

    return article_list


def zap_extractor_2021_2024(url, year, logger=None):
    """
    ZAP 2021-2024 extractor — zap.aeiou.pt (renewed theme).

    Confirmed structure (zap_homepage_2021-2024.html + zap_interior_2024.html):
      - Homepage: same slug-with-numeric-ID structure
      - Interior: body in <div class="entry-content"> with <p>
        (theme change — back to entry-content, different from 2017-2020)
      - Remove Gutenberg/wp-block blocks and dynamic widgets

    Previous version bugs:
      - Used 'h3.entry-title' to find articles — that selector didn't exist in 2021-2022
      - Wrong body selector 'td-post-content' for this period (was 2017-2020)
    """
    article_list = []
    source = "zap.aeiou.pt"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    SKIP = ['javascript', 'mailto', 'facebook.com', 'twitter.com',
            'instagram.com', 'youtube.com', '/conta', '/login',
            '/newsletter', '/noticias/desporto', '/thread/']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            if 'zap.aeiou.pt' not in hl: continue
            if any(s in hl for s in SKIP): continue
            if not re.search(r'-\d+$', href.split('?')[0].rstrip('/')): continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 15: continue

            clean_url = href.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = art_r.apparent_encoding
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                # Body in div.entry-content (confirmed with zap_interior_2022.html)
                body_text = ''
                body_elem = art_soup.select_one('div.entry-content')
                if body_elem:
                    # Remove Gutenberg blocks and dynamic widgets
                    for junk in body_elem.find_all(
                        class_=lambda c: c and any(
                            x in str(c) for x in ['wp-block', 'td-block', 'sharedaddy', 'jp-relatedposts']
                        )
                    ):
                        junk.decompose()
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 40]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in ZAP 2021-2024 extractor: {str(ex)}")
        print(f"Error in zap_extractor_2021_2024: {str(ex)}")

    return article_list

def nam_extractor_2015_2016(url, year, logger=None):
    """
    Notícias ao Minuto 2015-2016 extractor — noticiasaominuto.com

    Confirmed structure (nam_interior_2015.html):
      - Homepage: articles at /desporto/NNNNNN/slug (numeric ID + slug)
        Full Arquivo.pt URLs already in hrefs
      - Interior: body in <div class="newsText"> with <p> paragraphs
      - Encoding: apparent_encoding can fail — force utf-8

    Previous version bugs (nam_extractor_2015_2017):
      - Selector 'div.article-body' does not exist — correct is 'div.newsText'
      - urljoin without Arquivo.pt URL reconstruction → direct requests to live site
      - Dirty title: included "DESPORTO Mercado Há 3 mins" prefix
      - Output missing 'source' and 'year'
      - No URL deduplication
    """
    article_list = []
    source = "noticiasaominuto.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    NOISE = ['consentimento', 'newsletter', 'subscritor', 'aposte', 'parceiros']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            # Sports articles: /desporto/NNNNN/slug
            if 'noticiasaominuto' not in hl and not href.startswith('/'): continue
            if '/desporto/' not in hl: continue
            # Skip category pages (no numeric ID after /desporto/)
            m = re.search(r'/desporto/(\d+)/', href)
            if not m: continue

            # Clean title — link text includes metadata
            # e.g. "DESPORTO Mercado Há 3 mins Sporting anuncia renovação"
            # Real title is the last substantial text block
            raw_text = a.get_text(separator=' ', strip=True)
            raw_text = re.sub(r'\s+', ' ', raw_text)
            # Strip metadata prefix (category + tag + time)
            raw_text = re.sub(r'^(DESPORTO|Desporto)\s+\S+\s+Há\s+[\d\w\s]+\s+', '', raw_text).strip()
            title = raw_text
            if len(title) < 10: continue

            clean_url = href.split('?')[0].split('#')[0]
            if not clean_url.startswith('http'):
                clean_url = 'https://arquivo.pt' + clean_url
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                body_text = ''
                body_elem = art_soup.find('div', class_='newsText')
                if body_elem:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 30
                             and not any(n in p.get_text(strip=True).lower() for n in NOISE)]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60
                             and not any(n in p.get_text(strip=True).lower() for n in NOISE)]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in NAM 2015-2016 extractor: {str(ex)}")
        print(f"Error in nam_extractor_2015_2016: {str(ex)}")

    return article_list


def nam_extractor_2017_2024(url, year, logger=None):
    """
    Notícias ao Minuto 2017-2024 extractor — noticiasaominuto.com

    Confirmed structure (nam_interior_2018.html + nam_interior_2022.html):
      - Homepage: articles at /desporto/NNNNNN/slug (same as 2015-2016)
        Full Arquivo.pt URLs already in hrefs
      - Interior: body in <div class="news-main-text"> with <p> paragraphs
        (layout migration — 'newsText' no longer exists from ~2017)
      - Noise filter: newsletter modal and ad paragraphs with > 30 chars

    Previous version bugs:
      - nam_extractor_2018_2020: selector 'a.item' doesn't exist on homepage
      - nam_extractor_2021_2024: selector 'a.item-link, a.headline' doesn't exist
      - Both used 'div[itemprop="articleBody"]' which doesn't exist
      - Correct selector 'div.news-main-text' works from 2017 to 2024
        → single function covers the whole period
    """
    article_list = []
    source = "noticiasaominuto.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    NOISE = ['consentimento', 'newsletter', 'subscritor', 'aposte', 'parceiros',
             'modal', 'descarregue a aplic', 'seja sempre o primeiro']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            if 'noticiasaominuto' not in hl and not href.startswith('/'): continue
            if '/desporto/' not in hl: continue
            # Skip category pages without a numeric ID
            m = re.search(r'/desporto/(\d+)/', href)
            if not m: continue

            # Clean title
            raw_text = re.sub(r'\s+', ' ', a.get_text(separator=' ', strip=True))
            # Strip "Desporto Tag Há X mins/horas" prefix
            raw_text = re.sub(r'^(DESPORTO|Desporto)\s+\S+\s+Há\s+[\d\w\s]+\s+', '', raw_text).strip()
            title = raw_text
            if len(title) < 10: continue

            clean_url = href.split('?')[0].split('#')[0]
            if not clean_url.startswith('http'):
                clean_url = 'https://arquivo.pt' + clean_url
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                body_text = ''
                body_elem = art_soup.find('div', class_='news-main-text')
                if body_elem:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 30
                             and not any(n in p.get_text(strip=True).lower() for n in NOISE)]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60
                             and not any(n in p.get_text(strip=True).lower() for n in NOISE)]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in NAM 2017-2024 extractor: {str(ex)}")
        print(f"Error in nam_extractor_2017_2024: {str(ex)}")

    return article_list

def euronews_extractor_2016_2019(url, year, logger=None):
    """
    Euronews PT 2016-2019 extractor — pt.euronews.com

    Confirmed structure (euronews_interior_2016.html):
      - Article filter: /YYYY/MM/DD/ in path, excluding /video/
      - Interior: body in <div class="article__content"> (double underscores)

    Known noise sources resolved:
      1. Videos: hrefs with '/video/' → excluded (no text content)
      2. Non-sports articles (politics, culture) in homepage sidebar → excluded by path category list
      3. urljoin with Arquivo.pt URLs → fixed with 'https://arquivo.pt'+href
    """
    article_list = []
    source = "pt.euronews.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Navigation paths and non-sports categories to skip
    SKIP = ['/video/', '/programas/', 'globalconversation', 'bruxelas',
            'newsletters', 'my-europe', 'serie-a-minha', '/tag/', 'javascript',
            '/pais/', '/mundo/', '/politica/', '/economia/', '/tech/',
            '/cultura/', '/lifestyle/', '/ciencia/', '/green/', '/europa/']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            if not re.search(r'/\d{4}/\d{2}/\d{2}/', href): continue
            if any(s in hl for s in SKIP): continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 15: continue

            # Build full Arquivo.pt URL
            if href.startswith('//'): clean_url = 'https:' + href
            elif href.startswith('/noFrame/'): clean_url = 'https://arquivo.pt' + href
            elif href.startswith('http'): clean_url = href
            else: continue
            clean_url = clean_url.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                body_text = ''
                body_elem = (art_soup.select_one('div.article__content') or
                             art_soup.select_one('div[itemprop="articleBody"]') or
                             art_soup.select_one('div.c-article-content') or
                             art_soup.select_one('div.js-article-content'))
                if body_elem:
                    for junk in body_elem.find_all(
                        class_=lambda c: c and any(x in str(c) for x in ['share', 'widget', 'newsletter', 'ad-'])
                    ): junk.decompose()
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 30]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in Euronews 2016-2019 extractor: {str(ex)}")
        print(f"Error in euronews_extractor_2016_2019: {str(ex)}")

    return article_list


def euronews_extractor_2020_2024(url, year, logger=None):
    """
    Euronews PT 2020-2024 extractor — pt.euronews.com

    Confirmed structure (euronews_interior_2022.html):
      - Filter: /YYYY/MM/DD/ in path, excluding /video/
      - Interior: body in <div class="c-article-content js-article-content">

    Known noise sources resolved:
      1. Videos: hrefs with '/video/' → excluded
      2. Non-sports articles: excluded by path category list
      3. Homepage selector 'a.m-object__title__link' → didn't exist → fixed
    """
    article_list = []
    source = "pt.euronews.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    SKIP = ['/video/', '/programas/', 'globalconversation', 'bruxelas',
            'newsletters', 'my-europe', 'serie-a-minha', '/tag/', 'javascript',
            '/pais/', '/mundo/', '/politica/', '/economia/', '/tech/',
            '/cultura/', '/lifestyle/', '/ciencia/', '/green/', '/europa/']

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            hl = href.lower()

            if not re.search(r'/\d{4}/\d{2}/\d{2}/', href): continue
            if any(s in hl for s in SKIP): continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 15: continue

            if href.startswith('//'): clean_url = 'https:' + href
            elif href.startswith('/noFrame/'): clean_url = 'https://arquivo.pt' + href
            elif href.startswith('http'): clean_url = href
            else: continue
            clean_url = clean_url.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_r = requests.get(clean_url, headers=headers, timeout=15)
                art_r.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_r.text, 'html.parser')
                for tag in art_soup(['script', 'style', 'noscript']): tag.decompose()

                body_text = ''
                body_elem = (art_soup.select_one('div.c-article-content') or
                             art_soup.select_one('div.js-article-content') or
                             art_soup.select_one('div.article__content') or
                             art_soup.select_one('div[itemprop="articleBody"]'))
                if body_elem:
                    for junk in body_elem.find_all(
                        class_=lambda c: c and any(x in str(c) for x in
                                                   ['c-article-read-more', 'share', 'widget', 'newsletter', 'ad-'])
                    ): junk.decompose()
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in body_elem.find_all('p')
                             if len(p.get_text(strip=True)) > 30]
                    body_text = ' '.join(paras)

                if not body_text:
                    paras = [re.sub(r'\s+', ' ', p.get_text(strip=True))
                             for p in art_soup.find_all('p')
                             if len(p.get_text(strip=True)) > 60]
                    body_text = ' '.join(paras[:8])

                body_text = clean_source_text(body_text, source)
                if not body_text: body_text = title

                article_list.append({
                    'link': clean_url, 'source': source, 'year': str(year),
                    'title': title, 'body_text': body_text[:5000],
                })
            except Exception:
                continue

    except Exception as ex:
        if logger: logger.error(f"Error in Euronews 2020-2024 extractor: {str(ex)}")
        print(f"Error in euronews_extractor_2020_2024: {str(ex)}")

    return article_list

def flashscore_extractor_2022_2023(url, year, logger=None):
    """
    Flashscore 2022-2023 extractor.
    Selectors validated against the confirmed interior HTML.
    """
    article_list = []
    source = "flashscore.pt"
    # Updated user-agent to avoid security blocks
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'lxml')
        
        visited = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Strict filter: must be in the news section
            if '/noticias/' not in href.lower() or href.lower().endswith('/noticias/'):
                continue

            title = re.sub(r'\s+', ' ', a.get_text(separator=' ')).strip()
            if len(title) < 15: continue
            
            full_link = urljoin(url, href)
            clean_url = full_link.split('?')[0].split('#')[0]
            if clean_url in visited: continue
            visited.add(clean_url)

            try:
                art_resp = requests.get(clean_url, headers=headers, timeout=10)
                art_resp.encoding = 'utf-8'
                art_soup = BeautifulSoup(art_resp.text, 'lxml')
                
                # Remove Flashscore noise (score iframes, tweets, ads)
                for junk in art_soup(['script', 'style', 'figure', 'aside', 'iframe', 'blockquote']):
                    junk.decompose()

                body_text = ''

                # Selector validated against the 2022 HTML
                body = art_soup.find('div', class_=lambda x: x and ('newsArticle' in x or 'article__content' in x)) \
                       or art_soup.find('article')
                
                if body:
                    paras = body.find_all('p')
                    text = '\n\n'.join([p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 30])
                    
                    if text:
                        article_list.append({
                            'link': clean_url,
                            'source': source,
                            'year': str(year),
                            'title': title,
                            'body_text': text[:5000]
                        })
            except Exception:
                continue
    except Exception as e:
        if logger: logger.error(f"Error in Flashscore 2022-2023 extractor: {e}")
        
    return article_list


def getArticle(link, year, source, logger):
    """Main routing function for article extraction."""
    src = source.lower()
    ano = int(year)

    if "abola.pt" in src:
        # A Bola: route by technological era
        if 2000 <= ano <= 2003:
            return abola_extractor_2000_2003(link, year, logger)
        elif 2004 <= ano <= 2008:
            return abola_extractor_2004_2007(link, year, logger)
        elif ano == 2009:
            return abola_extractor_2009(link, logger)
        elif 2010 <= ano <= 2014:
            return abola_extractor_2010_2014(link, year, logger)
        elif 2015 <= ano <= 2016:
            return abola_extractor_2015_2016(link, year, logger)
        elif 2017 <= ano <= 2023:
            return abola_extractor_2017_2023(link, year, logger)
        else:
            return abola_extractor_2024(link, year, logger)

    if "ojogo.pt" in src:
        if int(year) == 1998:
            return ojogo_extractor_1998(link, year, logger)
        elif int(year) == 1999:
            return ojogo_extractor_1999(link, year, logger)
        elif int(year) <= 2006:
            return ojogo_extractor_2001_2006(link, year, logger)
        elif int(year) <= 2011:
            return ojogo_extractor_2007_2011(link, year, logger)
        elif int(year) <= 2014:
            return ojogo_extractor_2012_2014(link, year, logger)
        elif int(year) == 2015:
            return ojogo_extractor_2015(link, year, logger)
        elif int(year) <= 2018:
            return ojogo_extractor_2016_2018(link, year, logger)
        else:
            return ojogo_extractor(link, year, logger)
        
    if "record.pt" in src:
        if ano <= 2000:
            return record_extractor_2000(link, year, logger)
        elif ano <= 2002:
            return record_extractor_2001_2002(link, year, logger)
        elif ano <= 2005:
            return record_extractor_2005(link, year, logger)
        elif ano == 2006:
            return record_extractor_2006(link, year, logger)
        elif ano <= 2008:
            return record_extractor_2007_2008(link, year, logger)
        elif ano <= 2010:
            return record_extractor_2009_2010(link, year, logger)
        elif ano <= 2013:
            return record_extractor_2013(link, year, logger)
        else:
            return record_extractor(link, year, logger)
        
    if "sapo.pt" in src:
        if ano <= 2004:
            return sapo_extractor_2003_2004(link, year, logger)
        elif ano <= 2007:
            return sapo_extractor_2005_2007(link, year, logger)
        elif ano <= 2013:
            return sapo_extractor_2009_2013(link, year, logger)
        elif ano <= 2017:
            return sapo_extractor_2014_2017(link, year, logger)
        elif ano <= 2019:
            return sapo_extractor_2018_2019(link, year, logger)
        elif ano <= 2023:
            return sapo_extractor_2020_2023(link, year, logger)
        else:
            return sapo_extractor_2024(link, year, logger)
        
    if "zap.aeiou.pt" in src:
        # 2017 is the critical theme switch (Forceful → Newspaper)
        if ano <= 2016:
            return zap_extractor_2013_2016(link, year, logger)
        elif ano <= 2020:
            return zap_extractor_2017_2020(link, year, logger)
        else:
            return zap_extractor_2021_2024(link, year, logger)
    
    if "noticiasaominuto" in src:
        if ano <= 2016:
            return nam_extractor_2015_2016(link, year, logger)
        else:
            return nam_extractor_2017_2024(link, year, logger)
        
    if "euronews" in src:
        if ano <= 2019:
            return euronews_extractor_2016_2019(link, year, logger)
        else:
            return euronews_extractor_2020_2024(link, year, logger)
        
    if "flashscore" in src:
        if ano <= 2023:
            return flashscore_extractor_2022_2023(link, year, logger)

    # Generic logic for other news sources
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
        r = requests.get(link, timeout=30, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        elements = soup.select('h1, h2, h3, .title, .article-thumb-text, .post-item-title, .m-object__title__link')
        return generic_clean(elements, link, soup, source)
    except: return []