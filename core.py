#!/usr/bin/python
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
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

def loadPage(driver, url):
    try:
        driver.get(url)
    except Exception as e:
        print "Could not load site! " + url
        print e
        return False
    return True

def resetConnection(driver, chromeOptions):
    driver.quit()
    driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=chromeOptions)
    return driver

def timeoutChecker(driver):
    try:
        driver.set_page_load_timeout(30)
    except common.exceptions.TimeoutException:
        print "Took to long to load!"
        return True
    return False

def main():

    # Get any command line arguments passed
    # Currenly only supports screenshot agrument
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', action='store_true', help='Pass argument to include screenshots of each site during the snapshot process')
    args = parser.parse_args()

    mainConfig = json.load(open("./config.json"))
    chromeOptions = webdriver.ChromeOptions()
    chromeOptions.add_argument("--headless")
    chromeOptions.add_argument("window-size=1920,1080")
    chromeOptions.add_argument("--no-sandbox")
    driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=chromeOptions)

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
        attempts = 0
        while True:
            loadRes = loadPage(driver, site['homeURL'])
            if loadRes or attempts > 2:
                break
            driver = resetConnection(driver, chromeOptions)
	    time.sleep(1)
            attempts += 1

        if not loadRes:
            print "PAGE LOAD FAILED FOR " + site['name']
            continue

        windowHeight = driver.execute_script("return document.body.scrollHeight")
        lastHeight = None

        timeout = timeoutChecker(driver)
        if timeout:
            continue

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            timeout = timeoutChecker(driver)
            if timeout:
                break

            newHeight = driver.execute_script("return document.body.scrollHeight")
            if newHeight == lastHeight:
                break
            lastHeight = newHeight

        timeout = timeoutChecker(driver)
        if timeout:
            continue


        # Generate a UUID for this instance
        runUUID = uuid.uuid4().hex

        # Close any popover (if one exists)
        try:
            popover = driver.find_element_by_id(site['popUpCloseID'])
            if popover:
                popover.click();
        except common.exceptions.ElementNotVisibleException:
            pass
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
        articles = []
        for articleEl in site['articleElements']:
            if site['findArticlesBy'] == 'xpath':
                fArticles = driver.find_elements_by_xpath("//"+articleEl)
            elif site['findArticlesBy'] == 'class':
                fArticles = driver.find_elements_by_class_name(articleEl)
            articles = articles + fArticles
        multiplyBy = {}
        modifiers = site['modifiers']
        for modifier in modifiers:
            multiplyBy[modifier['class']] = modifier['weight']
        newArticles = []
        for article in articles:

            score = 1
            foundHeader = False
            headEl = None
            headline = None
            # Get the raw data
            for headlineClass in site['headlineClasses']:
                try:
                    #possibleHeads = article.find_elements_by_xpath(".//*[@class='"+headlineClass+"']")
                    possibleHeads = article.find_elements_by_class_name(headlineClass)
                    for checkHead in possibleHeads:
                        headline = checkHead.text
                        if not headline or headline == ' ' or headline == '':
                            headline = checkHead.get_attribute('innerHTML')
                            if not headline or headline == ' ':
                                continue
                        headEl = checkHead
                        break
                except common.exceptions.NoSuchElementException:
                    continue
                if not headline or headline == ' ' or headline == '':
                    continue
                foundHeader = True
                break

            if foundHeader == False:
                for hTag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a']:
                    try:
                        possibleHeads = article.find_elements_by_tag_name(hTag)
                        for checkHead in possibleHeads:
                            headline = checkHead.text
                            if not headline or headline == ' ' or len(headline) < 13:
                                continue
                            headEl = checkHead
                            break
                    except common.exceptions.NoSuchElementException:
                        continue
                    if headline and headline != ' ':
                        foundHeader = True
                        break
                if foundHeader == False:
                    continue

            if not headEl:
                print "======FAILED======"
                continue

            headline = re.sub(r'<.*>', '', headline)
            headSizeRaw = headEl.value_of_css_property("font-size")
            headLinks = article.find_elements_by_link_text(headline)
            foundLink = False
            for link in headLinks:
                possibleLink = link.get_attribute("href")
                if possibleLink:
                    headLink = possibleLink
                    foundLink = True
                    break
            if foundLink == False:
                moreLinks = article.find_elements_by_xpath(".//a[@href]")
                if moreLinks:
                    for link in moreLinks:
                        headLink = link.get_attribute("href")
                        if headLink:
                            foundLink = True
                            break
                if foundLink == False:
                    headLink = article.get_attribute("href")
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
                if loc['x'] == 0.0 and loc['y'] > 0:
                    loc['x'] = 1.0
                calcLoc = math.sqrt(loc['x'] * loc['y']) / 100
                invLoc = 1/calcLoc
                score *= invLoc
            except ZeroDivisionError:
                print "Could not find a location for this article"
                continue

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
        snap = False
        if snap is False:
            print "Failed to Index snapshot"
        for articleID in newArticles:
            new = cur.execute("SELECT * FROM articles WHERE id=?", (articleID,))
            newArticle = new.fetchone()
            articleDoc = {'headline': newArticle[1], 'url': newArticle[2], 'sqlID': articleID}
            art = es.index(index="articles", doc_type="article", body=articleDoc)

    mainConn.commit()
    mainConn.close()
    time.sleep(5)
    driver.close()
    driver.quit()


if __name__ == '__main__':
    main()
