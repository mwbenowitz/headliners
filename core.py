#!/usr/bin/python
#
# This is the core Headline Scraper Tool
# that looks at new site homepages
# and collections information on what stories
# they've published and what prominence they're given
#
# Mike Benowitz (mike@mikebenowitz.com)

# Core utilities
import json
import time
import datetime
import numpy
import re
import math

from lib.dbManager import dbManager
from lib.seleniumManager import seleniumManager

def main():

    mainConfig = json.load(open("./config.json"))
    selenium = seleniumManager()
    db = dbManager()

    for site in mainConfig['sites']:

        # Store/get site_id and snap_id from neo4j
        currentTime = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        site_id, snapshot_id = db.storeSource(site, currentTime)

        attempts = 0
        while True:
            loadRes = selenium.loadPage(site['homeURL'])
            if loadRes or attempts > 2:
                break
            driver = selenium.resetConnection()
            time.sleep(1)
            attempts += 1

        if not loadRes:
            print "PAGE LOAD FAILED FOR " + site['name']
            continue

        timeout = selenium.timeoutChecker()
        if timeout:
            continue

        selenium.scrollPage()

        timeout = selenium.timeoutChecker()
        if timeout:
            continue

        selenium.closePopover(site['popUpCloseID'])

        body = selenium.driver.find_element_by_xpath("//body")
        bodySize = body.size
        totalHeight = bodySize['height']
        fullScreen = None

        # Get the articles from the page
        articles = selenium.getArticles(site['articleElements'], site['findArticlesBy'])

        multiplyBy = {}
        modifiers = site['modifiers']
        for modifier in modifiers:
            multiplyBy[modifier['class']] = modifier['weight']
        newArticles = []
        for article in articles:

            score = 1

            headline, headEl = selenium.getHeader(article, site['headlineClasses'])
            if not headline:
                print "======FAILED HEADLINE======"
                continue

            headline = re.sub(r'<.*>', '', headline)
            headSizeRaw = headEl.value_of_css_property("font-size")

            headLink = selenium.getLink(article, headline)
            if not headLink:
                print "======FAILED LINK======"
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
                if loc['x'] == 0.0 and loc['y'] > 0:
                    loc['x'] = 1.0
                calcLoc = math.sqrt(loc['x'] * loc['y']) / 100
                invLoc = 1/calcLoc
                score *= invLoc
            except ZeroDivisionError:
                print "Could not find a location for this article"
                continue

            # Store this headline/article
            db.storeArticle(headline, headLink, score, size, loc, site_id, snapshot_id)

        # TODO maybe?
        # Calculate standard dev of location and size
        # Use those to calculate the score

    selenium.exit()

if __name__ == '__main__':
    main()
