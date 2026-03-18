import logging



import os.path
from crawlers.linkExtractor import writePastURLS, getPastURLs
from crawlers.articleExtractor import getArticle

import time
import random



# Set up basic logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)



logger = logging.getLogger(__name__)


folder_path = [os.path.join("data", "links"),os.path.join("data","articles")]
for folder in folder_path:
    if not os.path.exists(folder):
        # If the folder does not exist, create it
        os.makedirs(folder)
        print(f"Folder '{folder}' created.")
    else:
        print(f"Folder '{folder}' already exists.")


'''
Step 1:
Extract the links from Arquivo.pT
'''

"""
source_links = ["abola.pt",
                "record.pt",
                "ojogo.pt",
                "desporto.sapo.pt",
                "zap.aeiou.pt/noticias/desporto",
                "www.noticiasaominuto.com/desporto",
                "https://pt.euronews.com/noticias/desporto",
                "https://www.flashscore.pt/noticias/"]

begin_year = 1998
end_year = 2024
for url in source_links:
    print(f"Extracting: {url}")

    for year in range(begin_year, end_year):
        time.sleep(random.randint(2, 5))
        links = getPastURLs(year=str(year), url=url)
        writePastURLS(links=links, url=url, year=str(year), filepath=folder_path)
        print(f"year:{year} - size: {len(links)}")


"""


'''
Step 2:
Extract the articles from each link:
'''



import json
files=[f for f in os.listdir(os.path.join("data","links")) if f.endswith(".json")]

import time
import random


for file in files:
    print(file)
    data_extracted=list()
    if not (os.path.exists(os.path.join("data", "articles", file))):
        with open(os.path.join("data","links",file),"r") as js:
            data=json.load(js)
            print(data)
            for entry in data:
                print(entry)
                time.sleep(random.randint(3,5))

                result=getArticle(entry["link"],entry["year"],entry["source"],logger)
                for r in result:
                    temp=entry
                    temp.update(r)
                    data_extracted.append(temp)


        with open(os.path.join("data", "articles", file), "w") as wf:
            json.dump(data_extracted, wf, indent=4)
    else:
        print("File already outputted")