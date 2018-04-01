from selenium import webdriver, common
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

from helpers.parseHelpers import validateString

class seleniumManager:

    def __init__(self):
        self.chromeOptions = webdriver.ChromeOptions()
        self.chromeOptions.add_argument("--headless")
        self.chromeOptions.add_argument("window-size=1920,1080")
        self.chromeOptions.add_argument("--no-sandbox")
        self.driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=self.chromeOptions)

    def loadPage(self, url):
        try:
            self.driver.get(url)
        except Exception as e:
            print "Could not load site! " + url
            print e
            return False
        return True

    def resetConnection(self):
        self.driver.quit()
        self.driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=self.chromeOptions)

    def timeoutChecker(self):
        try:
            self.driver.set_page_load_timeout(30)
        except common.exceptions.TimeoutException:
            print "Took to long to load!"
            return True
        return False

    def scrollPage(self):

        windowHeight = self.driver.execute_script("return document.body.scrollHeight")
        lastHeight = None

        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            timeout = self.timeoutChecker()
            if timeout:
                break

            newHeight = self.driver.execute_script("return document.body.scrollHeight")
            if newHeight == lastHeight:
                break
            lastHeight = newHeight

    # Close any popover (if one exists)
    def closePopover(self, popup_id):
        try:
            popover = self.driver.find_element_by_id(popup_id)
            if popover:
                popover.click();
        except common.exceptions.ElementNotVisibleException:
            pass
        except common.exceptions.NoSuchElementException:
            pass

    def getArticles(self, articleElements, find_type):
        articles = []
        for articleEl in articleElements:
            if find_type == 'xpath':
                fArticles = self.driver.find_elements_by_xpath("//"+articleEl)
            elif find_type == 'class':
                fArticles = self.driver.find_elements_by_class_name(articleEl)
            articles = articles + fArticles
        return articles

    def getHeader(self, article, headlineClasses):
        for headlineClass in headlineClasses:
            try:
                possibleHeads = article.find_elements_by_class_name(headlineClass)
                for checkHead in possibleHeads:
                    headline = checkHead.text
                    if not validateString(headline):
                        headline = checkHead.get_attribute('innerHTML')
                        if not validateString(headline):
                            continue
                    return headline, checkHead
            except common.exceptions.NoSuchElementException:
                continue

        for hTag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a']:
            try:
                possibleHeads = article.find_elements_by_tag_name(hTag)
                for checkHead in possibleHeads:
                    headline = checkHead.text
                    if not validateString(headline):
                        continue
                    return headline, checkHead
            except common.exceptions.NoSuchElementException:
                continue

        return False, False

    def getLink(self, article, headline, linkClasses):
        headLinks = article.find_elements_by_link_text(headline)
        for link in headLinks:
            possibleLink = link.get_attribute("href")
            if possibleLink:
                return possibleLink

        for l_class in linkClasses:
            possibleLinks = article.find_elements_by_class_name(l_class)
            for possLink in possibleLinks:
                l_href = possLink.get_attribute("href")
                if l_href:
                    return l_href

        moreLinks = article.find_elements_by_xpath(".//a[@href]")
        if moreLinks:
            for link in moreLinks:
                headLink = link.get_attribute("href")
                if headLink:
                    return headLink


        headLink = article.get_attribute("href")
        if headLink:
            return headLink

        headLink = headline.replace(' ', '_').lower()
        return headLink

    def exit(self):
        time.sleep(5)
        self.driver.close()
        self.driver.quit()
