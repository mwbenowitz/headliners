#
# This is the core Headline Scraper Tool
# that looks at new site homepages
# and collections information on what stories
# they've published and what prominence they're given
#
# Mike Benowitz (mike@mikebenowitz.com)

# Core utilities
import requests
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
import argparse

def main():

    # Get any command line arguments passed
    # Currenly only supports screenshot agrument
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', action='store_true', help='Pass argument to include screenshots of each site during the snapshot process')
    args = parser.parse_args()

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
                        (uuid text PRIMARY KEY, runTime text, image text, site text, siteCode text)''')
        cur.execute('''CREATE TABLE articles
                        (id integer PRIMARY KEY, headline text, url text)''')
        cur.execute('''CREATE TABLE snap_articles
                        (relID integer PRIMARY KEY, snap text, article integer, score real, FOREIGN KEY(snap) REFERENCES snapshots(uuid), FOREIGN KEY(article) REFERENCES articles(id))''')
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

        body = driver.find_element_by_xpath("//body")
        bodySize = body.size
        totalHeight = bodySize['height']
        fullScreen = None
        currentTime = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # Take screenshots of the currently loaded page (if arg passed)

        if args.screenshots:
            driver.set_window_size(1280, totalHeight)
            fullScreen = site['shortName']+'_'+currentTime+'.png'
            screenRes = driver.save_screenshot('screens/'+fullScreen)
            if not screenRes:
                print "Failed to take/save screenshot!"
        snapValues = (runUUID, currentTime, fullScreen, site['name'], site['shortName'])
        cur.execute("INSERT INTO snapshots VALUES (?, ?, ?, ?, ?)", snapValues)

        # Get the articles from the page
        if site['findArticlesBy'] == 'xpath':
            articles = driver.find_elements_by_xpath("//"+site['articleElement'])
        elif site['findArticlesBy'] == 'class':
            articles = driver.find_elements_by_class_name(site['articleElement'])
        multiplyBy = {}
        modifiers = site['modifiers']
        for modifier in modifiers:
            multiplyBy[modifier['class']] = modifier['weight']
        newArticles = []
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
            articleValues = (None, headline, headLink)
            cur.execute('''SELECT * FROM articles
                            INNER JOIN snap_articles ON articles.id = snap_articles.article
                            INNER JOIN snapshots ON snap_articles.snap = snapshots.uuid
                            WHERE headline=? AND snapshots.siteCode=?''', (headline, site['shortName']))
            saved = cur.fetchone()
            if saved is None:
                cur.execute("INSERT INTO articles VALUES (?, ?, ?)", articleValues)
                articleID = cur.lastrowid
                newArticles.append(articleID)
            else:
                print article
                articleID = saved[0]
            cur.execute("INSERT INTO snap_articles VALUES (?, ?, ?, ?)", (None, runUUID, articleID, score))

        mainConn.commit()
        # TODO maybe?
        # Calculate standard dev of location and size
        # Use those to calculate the score

        # Index the results in elasticsearch
        es = Elasticsearch()
        snapDoc = {"uuid": runUUID, "dateTime": currentTime, "screenshot": fullScreen, "siteCode": site["shortName"], "site": site["name"]}
        snap = es.index(index="snapshots", doc_type="snapshot", body=snapDoc)
        if snap is False:
            print "Failed to Index snapshot"
        for articleID in newArticles:
            new = cur.execute("SELECT * FROM articles WHERE id=?", (articleID,))
            newArticle = new.fetchone()
            articleDoc = {'headline': newArticle[1], 'url': newArticle[2], 'sqlID': articleID}
            art = es.index(index="articles", doc_type="article", body=articleDoc)

    mainConn.commit()
    mainConn.close()
    driver.close()


if __name__ == '__main__':
    main()
