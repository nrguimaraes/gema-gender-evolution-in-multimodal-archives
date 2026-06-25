import requests
import json
import os
import threading
import atexit

CACHE_FILE = os.path.join(os.path.dirname(__file__), "gender_cache.json")

_cache_lock = threading.Lock()
_unsaved_count = 0
_SAVE_INTERVAL = 50  # flush to disk every 50 new entries

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        _gender_cache = json.load(f)
else:
    _gender_cache = {}

def _save_cache():
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(_gender_cache, f, ensure_ascii=False, indent=2)

# Always flush on exit so no entries are lost if the script is interrupted
atexit.register(_save_cache)

def consultar_wikidata_genero(nome):
    """
    Queries the Wikidata API to retrieve the biographical gender (Property P21)
    of a given entity (PER).

    Results are cached in a local JSON file so repeated names (e.g. "Cristiano Ronaldo"
    across 200k articles) only trigger one HTTP request. Thread-safe via a lock.
    """
    global _unsaved_count

    with _cache_lock:
        if nome in _gender_cache:
            return _gender_cache[nome]

    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "pt",
        "search": nome
    }
    headers = {
        'User-Agent': 'GemaGenderBot/1.0 (contact: internship_project@iaedu.pt)'
    }

    resultado = "Desconhecido"

    try:
        # Step 1: Search for the entity ID
        res = requests.get(url, params=params, headers=headers, timeout=5).json()

        if res.get('search'):
            entity_id = res['search'][0]['id']
            # Step 2: Fetch detailed entity data
            entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
            entity_data = requests.get(entity_url, headers=headers, timeout=5).json()

            claims = entity_data['entities'][entity_id].get('claims', {})

            # P21: Sex or Gender property
            if 'P21' in claims:
                gender_id = claims['P21'][0]['mainsnak']['datavalue']['value']['id']

                # Q6581097 = Male / Q6581072 = Female
                if gender_id == 'Q6581097':
                    resultado = "Masculino"
                elif gender_id == 'Q6581072':
                    resultado = "Feminino"

    except Exception:
        # Silently fail and return unknown to avoid crashing the main pipeline
        pass

    # Store result (including "Desconhecido") so we never hit the API twice for the same name
    with _cache_lock:
        _gender_cache[nome] = resultado
        _unsaved_count += 1
        should_save = _unsaved_count >= _SAVE_INTERVAL
        if should_save:
            _unsaved_count = 0

    if should_save:
        with _cache_lock:
            _save_cache()

    return resultado


def consultar_wikidata_info_completa(nome):
    """
    Returns extended Wikidata info for a person: gender, sport, nationality, birth_year.
    Results are cached alongside gender results in gender_cache.json.
    Makes up to 4 HTTP requests but only once per unique name (cache-first).
    """
    global _unsaved_count

    cache_key = f"\x00info\x00{nome}"

    with _cache_lock:
        if cache_key in _gender_cache:
            cached = _gender_cache[cache_key]
            # Re-fetch if cached entry is missing newer fields
            if isinstance(cached, dict) and "image_url" in cached:
                return cached

    headers = {'User-Agent': 'GemaGenderBot/1.0 (contact: internship_project@iaedu.pt)'}
    info = {"gender": None, "sport": None, "nationality": None, "birth_year": None, "wikidata_url": None, "image_url": None}

    def _label(entity_id):
        try:
            data = requests.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json",
                headers=headers, timeout=5
            ).json()
            labels = data['entities'][entity_id].get('labels', {})
            return (labels.get('pt') or labels.get('en') or {}).get('value')
        except Exception:
            return None

    try:
        res = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbsearchentities", "format": "json", "language": "pt", "search": nome},
            headers=headers, timeout=5
        ).json()

        if res.get('search'):
            entity_id = res['search'][0]['id']
            info['wikidata_url'] = f"https://www.wikidata.org/wiki/{entity_id}"
            entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
            entity_data = requests.get(entity_url, headers=headers, timeout=5).json()
            claims = entity_data['entities'][entity_id].get('claims', {})

            if 'P21' in claims:
                gid = claims['P21'][0]['mainsnak']['datavalue']['value']['id']
                if gid == 'Q6581097':   info['gender'] = 'Male'
                elif gid == 'Q6581072': info['gender'] = 'Female'

            if 'P641' in claims:
                sport_id = claims['P641'][0]['mainsnak']['datavalue']['value']['id']
                info['sport'] = _label(sport_id)

            if 'P27' in claims:
                nat_id = claims['P27'][0]['mainsnak']['datavalue']['value']['id']
                info['nationality'] = _label(nat_id)

            if 'P569' in claims:
                time_val = claims['P569'][0]['mainsnak']['datavalue']['value'].get('time', '')
                if time_val:
                    try:
                        info['birth_year'] = int(time_val[1:5])
                    except ValueError:
                        pass

            # P18: image — filename on Wikimedia Commons
            if 'P18' in claims:
                filename = claims['P18'][0]['mainsnak']['datavalue']['value']
                # Wikimedia Commons Special:FilePath redirects to the actual image
                filename_encoded = filename.replace(' ', '_')
                info['image_url'] = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename_encoded}?width=300"

    except Exception:
        pass

    with _cache_lock:
        _gender_cache[cache_key] = info
        _unsaved_count += 1
        should_save = _unsaved_count >= _SAVE_INTERVAL
        if should_save:
            _unsaved_count = 0

    if should_save:
        with _cache_lock:
            _save_cache()

    return info
