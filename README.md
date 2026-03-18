# SportGen
Gender in Sports in Portuguese News Mediums


## News Medium to Retrieve

 - A bola
 - Record
 - O Jogo
 - Correio da manha
 - Jornal de Notícias
 - Diário de Notícias
 - Público
 - Sapo Desporto (crawler done)
 - IOL Desporto
 - Notícias ao minuto (crawler done)
 - Zap/Aeiou (crawler done)
 - Flashscore (crawler done - muitas pagina com falha)

## Crawlers missing

 - A bola 2000-2003
 - A bola 2004 - 2007
 - A bola 2008 
 - A bola 2009-2014 done
 - A bola 2015-2016
 - O Jogo 1998 - 2000
 - O Jogo 2001 - 2006
 - O Jogo 2007 - 2011
 - O Jogo 2012 - 2014
 - O Record  2016 -2017
 - O Record 2011 - 2015 (newsslot)
 - O Record 2007 - 2010
 - O Record 2006
 - O Record 1998 - 2002
 - NAM 2017-2018
 - NAM 2015 - 2016
 - Sapo 2014-2018
 - Sapo 2010 - 2013
 - Sapo 2009 - 2002
 - Sapo 2001
 - EuroNews 2016 - 2019
 - Zap 2019 - 2020
 - Zap 2017- 2018
 - Zap 2013 - 2016

## Resources to use

- Arquivo.PT
- First Names Database [link](https://github.com/MatthiasWinkelmann/firstname-database)
- Spacy
- Wikipedia Package [link](https://pypi.org/project/wikipedia/)
- OpenCV for Gender Detection [link](https://www.geeksforgeeks.org/age-and-gender-detection-using-opencv-in-python/)
- Zero-shot for Gender Detection
## Tasks 

### NLP

1. Create the crawlers to extract the links of each sports news from the different sources
2. Extract the articles title, date, source and lead. Try to identify the sport as well
4. Use NER and extract all the persons from the title and lead
5. Save all names in a csv and try to identify the gender. In addition, due some entity linking  (e.g. wikipedia) to infer the athlete.
6. Use Arquivo Image Search to find an image to each person identified or get one from the entity linking process
7. Validate remaining persons by hand

### Image

1. Create the crawlers to extract the covers from all sports journals through time
2. Use a Male/Female Recognition Model to identify the persons in the cover as well as their size [maybe this ](https://www.geeksforgeeks.org/age-and-gender-detection-using-opencv-in-python/)
3. (optional) Try to assing the person in the image to an extracted entity



### Requirements

Python 3.8