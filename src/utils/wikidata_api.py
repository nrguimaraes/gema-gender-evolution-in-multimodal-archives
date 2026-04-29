import requests

def consultar_wikidata_genero(nome):
    """
    Queries the Wikidata API to retrieve the biographical gender (Property P21) 
    of a given entity (PER)[cite: 6, 23].
    
    This function acts as a centralized 'ground truth' for gender disambiguation
    across different NLP models in the project.
    """
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "pt",
        "search": nome
    }
    
    # Mandatory Identification to avoid API blocks and follow Wikimedia's User-Agent policy[cite: 6, 23]
    headers = {
        'User-Agent': 'GemaGenderBot/1.0 (contact: internship_project@iaedu.pt)'
    }
    
    try:
        # Step 1: Search for the entity ID[cite: 23]
        res = requests.get(url, params=params, headers=headers, timeout=5).json()
        
        if res.get('search'):
            entity_id = res['search'][0]['id']
            # Step 2: Fetch detailed entity data[cite: 23]
            entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
            entity_data = requests.get(entity_url, headers=headers, timeout=5).json()
            
            claims = entity_data['entities'][entity_id].get('claims', {})
            
            # P21: Sex or Gender property[cite: 6, 23]
            if 'P21' in claims:
                gender_id = claims['P21'][0]['mainsnak']['datavalue']['value']['id']
                
                # Q6581097 = Male / Q6581072 = Female[cite: 23]
                if gender_id == 'Q6581097': 
                    return "Masculino"
                if gender_id == 'Q6581072': 
                    return "Feminino"
                    
    except Exception:
        # Silently fail and return unknown to avoid crashing the main pipeline[cite: 23]
        pass
        
    return "Desconhecido"