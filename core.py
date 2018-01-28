#
# This is the core Headline Scraper Tool
# that looks at new site homepages
# and collections information on what stories
# they've published and what prominence they're given
#
# Mike Benowitz (mike@mikebenowitz.com)

# Core utilities
import requests
from bs4 import BeautifulSoup
import sqlite3
from elasticsearch import Elasticsearch
from selenium import webdriver, common
import json
import sys
import os
import subprocess
import time
import datetime
import string
import logging
import numpy
import re
import math
from PIL import Image
import uuid

def main():
    mainConfig = json.load(open("config.json"))
    chromeOptions = webdriver.ChromeOptions()
    chromeOptions.add_argument("--headless")
    driver = webdriver.Chrome(chrome_options=chromeOptions)

    # for the initial loop we just store raw data, then we calculate scores
    # based on the entire run id

    # Open a connection to the sqlite db, create tables if necessary
    if not os.path.isfile('test.db'):
        mainConn = sqlite3.connect('test.db')
        cur = mainConn.cursor()
        cur.execute('''CREATE TABLE snapshots
                        (uuid text PRIMARY KEY, runTime text, image text, site text)''')
        cur.execute('''CREATE TABLE articles
                        (snapshot text, headline text, url text, score real, FOREIGN KEY(snapshot) REFERENCES snapshots(uuid))''')
        mainConn.commit()

    else:
        mainConn = sqlite3.connect('test.db')
        cur = mainConn.cursor()

    for site in mainConfig['sites']:
        # TODO
        # Add a UUID for each run of each site so we can pull them together
        # And caluclate scores together
        # Store time on page as well and use that to multiply scores
        driver.get(site['homeURL'])

        # Generate a UUID for this instance
        runUUID = uuid.uuid4().hex

        # Close any popover (if one exists)
        try:
            popover = driver.find_element_by_id(site['popUpCloseID'])
            if popover:
                popover.click();
        except common.exceptions.NoSuchElementException:
            pass

        # Take screenshots of the currently loaded page
        body = driver.find_element_by_xpath("//body")
        bodySize = body.size
        totalHeight = bodySize['height']
        currentTime = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")

        driver.set_window_size(1280, totalHeight)
        fullScreen = site['shortName']+'_'+currentTime+'.png'
        screenRes = driver.save_screenshot('screens/'+fullScreen)
        if not screenRes:
            print "Failed to take/save screenshot!"

        currentPos = 0
        screenCount = 1
        snapValues = (runUUID, currentTime, fullScreen, site['name'])
        mainConn.execute("INSERT INTO snapshots VALUES (?, ?, ?, ?)", snapValues)

        # Get the articles from the page
        if site['findArticlesBy'] == 'xpath':
            articles = driver.find_elements_by_xpath("//"+site['articleElement'])
        elif site['findArticlesBy'] == 'class':
            articles = driver.find_elements_by_class_name(site['articleElement'])
        multiplyBy = {}
        modifiers = site['modifiers']
        for modifier in modifiers:
            multiplyBy[modifier['class']] = modifier['weight']
        for article in articles:
            score = 1

            # Get the raw data
            try:
                headEl = article.find_element_by_class_name(site['headlineClass'])
                headline = headEl.text
                headSizeRaw = headEl.value_of_css_property("font-size")
                headLink = article.find_element_by_link_text(headline).get_attribute("href")
            except common.exceptions.NoSuchElementException:
                print "Could not find a headline!"
                continue
            size = article.size
            loc = article.location

            # Calculate special class modifier
            classes = article.get_attribute("class")
            classSplit = classes.split(' ')
            for className in classSplit:
                if className in multiplyBy:
                    score *= multiplyBy[className]

            # Calculate headline size modifier
            headSize = float(re.sub('[a-zA-Z]+', '', headSizeRaw))
            sizeMultiply = (headSize - (headSize % 10)) / 10
            score *= sizeMultiply

            # Calculate total area modifier
            calcSize = math.sqrt(size['width'] * size['height']) / 10
            score *= calcSize

            # Calculate position modifier
            try:
                calcLoc = math.sqrt(loc['x'] * loc['y']) / 100
                invLoc = 1/calcLoc
                score *= invLoc
            except ZeroDivisionError:
                print "Could not find a location for this article"
                print headline
                print loc
                continue

            print headline
            print score
            articleValues = (runUUID, headline, headLink, score)
            mainConn.execute("INSERT INTO articles VALUES (?, ?, ?, ?)", articleValues)

        # TODO maybe?
        # Calculate standard dev of location and size
        # Use those to calculate the score

        # Index the results in elasticsearch
        es = Elasticsearch()
        for article in cur.execute("SELECT * FROM articles WHERE snapshot=?", (runUUID,)):
            articleDoc = {'headline': article[1], 'url': article[2], 'score': article[3], 'snapshot': article[0], 'site':      site['shortName']}
            art = es.index(index="articles", doc_type="article", body=articleDoc)

    mainConn.commit()
    driver.close()


if __name__ == '__main__':
    main()
