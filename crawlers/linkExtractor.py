import os.path

import requests
from requests.exceptions import Timeout
def getPastURLs(year, url, startMonth='01', endMonth='12'):

    url_api = 'https://arquivo.pt/textsearch'

    versionHistory = url
    maxItems = '500'
    fromDate = f'{year}{startMonth}01000000'
    toDate = f'{year}{endMonth}31235959'
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0 "}
    payload = {'versionHistory': versionHistory, 'maxItems': maxItems, 'from': fromDate, 'to': toDate}

    try:
        r = requests.get(url_api, params=payload, headers=headers)
        content = r.json()
        pastURLs = []

        for item in content['response_items']:
            pastURLs.append(item['linkToNoFrame'])

        return list(set(pastURLs))

    except Exception as e:
        print('Error: ' + str(e))
        return []



import string
import json

def writePastURLS(links,url,year,filepath):
    js=list()
    for l in links:
        temp={
            "link":l,
            "source":url,
            "year":year
        }
        js.append(temp)
    filename=url.translate(str.maketrans('', '', string.punctuation))+"_"+str(year)+".json"
    if(len(links)!=0):
        with open(os.path.join(filepath,filename), 'w') as file:
            json.dump(js, file, indent=4)

#ex=getPastURLs(2019,"abola.pt")
#print(ex)

