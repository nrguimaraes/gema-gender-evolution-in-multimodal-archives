import requests
from bs4 import BeautifulSoup
import re
import os.path
def desportosapo_extractor(url,year,logger):
    article_list=list()

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(class_="title")
        for e in element:
            try:
                link="https://arquivo.pt/"+e.find("a")["href"]
                temp={"title":e.get_text(),"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list


def noticiasminuto_extractor(url,year,logger):
    article_list=list()

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(class_="article-thumb-text")
        article_list=list()
        for e in element:
            try:
                link=e.find("a")["href"]
                temp={"title":e.get_text().replace("\n",""),"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list



def aeiou_extractor(url,year,logger):
    article_list = list()
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(attrs={"class":"post-item-title"})
        for e in element:
            try:
                link=e.find("a")["href"]
                temp={"title":e.get_text().replace("\n",""),"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list


def flashscore_extractor(url,year,logger):
    article_list=list()

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(attrs={"class":"rssNews"})
        for e in element:
            try:
                link=link="https://arquivo.pt/"+e["href"]
                temp={"title":e.get_text().replace("\n",""),"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list

import re

def euronews_extractor(url,year,logger):
    article_list = list()
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(attrs={"class":"m-object__title__link"})
        for e in element:
            try:
                link="https://arquivo.pt/"+e["href"]
                title=e.get_text().replace("\n","")
                title=re.sub(r'\s+', ' ', title)
                temp={"title":title,"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list





def record_extractor(url,year,logger):
    article_list=list()
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(attrs={"class":"noticia_box"})

        for e in element:
            try:

                link="https://arquivo.pt/"+e.find("a")["href"]
                title=e.find("a").get_text().replace("\n","")
                title=re.sub(r'\s+', ' ', title)
                temp={"title":title,"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list


def ojogo_extractor(url,year,logger):
    article_list = list()
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all("article")
        for e in element:
            try:
                e=e.find("h2")
                link="https://arquivo.pt/"+e.find("a")["href"]
                title=e.find("a").get_text().replace("\n","")
                title=re.sub(r'\s+', ' ', title)
                temp={"title":title,"link":link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list



def abola_extractor_2009(url,logger):
    #linkNoticias
    article_list = list()
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find_all(attrs={"class":"linkNoticias"})
        for e in element:
            try:
                link = url+"/"+e["href"]
                title = re.sub(r'\s+', ' ', e.get_text())
                temp = {"title": title, "link": link}
                article_list.append(temp)
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex) + "  " + url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)
    return article_list

print(abola_extractor_2009("https://arquivo.pt/noFrame/replay/20090520150834/http://www.abola.pt/",None))

def abola_extractor(url,year,logger):
    if year in range(2009,2014):
        abola_extractor_2009(url,logger)
    else:
        abola_extractor_default(url,logger)



def abola_extractor_default(url,logger):

    article_list=list()
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        element = soup.find_all(attrs={"class":["col-md-4 col-sm-6 col-xs-12","col-sm-6 col-xs-12","col-xs-12 top-a1","content-box"]})
        for e in element:
            try:
                link="https://arquivo.pt/"+e.find("a")["href"]
                title=e.find(attrs={"class":"titulo"}).get_text().replace("\n","")
                title=re.sub(r'\s+', ' ', title)
                temp={"title":title,"link":link}
                article_list.append(temp)
                logger.info(url + "   extracted")
            except Exception as ex:
                print(str(ex))
                logger.error(str(ex)+"  "+url)
    except Exception as ex2:
        print(str(ex2))
        logger.error(str(ex2) + "  " + url)

    return article_list



def getArticle(link,year,source,logger):
    if(source =="abola.pt"):
        return(abola_extractor(link,logger))
    elif(source=="desporto.sapo.pt"):
        return(desportosapo_extractor(link,logger))
    elif (source == "https://pt.euronews.com/noticias/desporto"):
        return (euronews_extractor(link,logger))
    elif (source == "https://www.flashscore.pt/noticias/"):
        return (flashscore_extractor(link,logger))
    elif (source == "zap.aeiou.pt/noticias/desporto"):
        return (aeiou_extractor(link,logger))
    elif (source == "www.noticiasaominuto.com/desporto"):
        return (noticiasminuto_extractor(link,logger))
    elif (source == "ojogo.pt"):
        return (ojogo_extractor(link,logger))
    elif (source == "record.pt"):
        return (record_extractor(link,logger))
    else:
        print("Extractor not found")
        return []

"""


t=abola_extractor("https://arquivo.pt/noFrame/replay/20230103175131/https://www.abola.pt/")
for i in t:
    print(i)






import json

for year in range(2023,2001,-1):
    # Reading a JSON file
    articles=list()
    print(year)
    with open(os.path.join("data","links","desportosapopt_"+str(year)+".json"), 'r') as file:
        data = json.load(file)
        for entry in data:
            t=desportosapo_extractor(entry["link"])
            if(t):
                articles=articles+t
    print(len(articles))

#desportosapo_extractor("https://arquivo.pt/noFrame/replay/20220204181450/https://desporto.sapo.pt/")

"""