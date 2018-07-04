from neo4j.v1 import GraphDatabase, basic_auth
import configparser
import os

class dbManager:

    def __init__(self):
        config = configparser.ConfigParser()
        config.read('./headliner.conf')
        self.driver = GraphDatabase.driver(config['DB']['db_url'], auth=basic_auth(config['DB']['db_usr'], config['DB']['db_psw']))
        self.db = self.driver.session()

    # Check if source exists, and if not create it
    # Returns source_id and snapshot_id in both cases, or error
    def storeSource(self, source_info, time):
        try:
            source_q = self.db.run("MATCH (s:Source) WHERE s.code = {code} RETURN ID(s) as source_id", {"code": source_info["shortName"]}).peek()

            if source_q:
                source_id = source_q['source_id']
            else:
                insert = {"name": source_info["name"], "code": source_info["shortName"], "url": source_info["homeURL"]}
                insert_str = "CREATE (s:Source " + self._cypherString(insert) + ") RETURN ID(s) as source_id"
                source_insert = self.db.run(insert_str, insert).peek()

                if source_insert:
                    source_id = source_insert['source_id']

            snapshot = {"run_time": time, "source_id": source_id}
            snapshot_str = "MATCH (s:Source) WHERE ID(s) = {source_id} CREATE (ss:SnapShot " + self._cypherString(snapshot) + ")-[:SITE]->(s) RETURN ID(ss) as snapshot_id"
            snap_insert = self.db.run(snapshot_str, snapshot).peek()
            snapshot_id = snap_insert['snapshot_id']

            return source_id, snapshot_id

        except Exception as e:
            print "Error raised in dbManager.storeSource"
            raise

    def storeArticle(self, headline, headLink, score, size, loc, site_id, snapshot_id):
        try:
            article_exist = self.db.run("MATCH (a:Article) WHERE a.link = {link} RETURN ID(a) as article_id", {"link": headLink}).peek()
            if article_exist:
                article_id = article_exist["article_id"]
                headline = {"headline": headline, "score": score, "width": size['width'], "height": size['height'], "loc_x": loc['x'], "loc_y": loc['y']}
                headline_str = '''
                    MATCH (ss:SnapShot) WHERE ID(ss) = {snapshot_id} MATCH (a:Article) WHERE ID(a) = {article_id}
                    CREATE (ss)-[:HAS]->(h:Headline ''' + self._cypherString(headline) + ''')-[:HEADLINE]->(a)
                    RETURN ID(h) as headline_id
                '''
                headline["snapshot_id"] = snapshot_id
                headline["article_id"] = article_id
                headline_insert = self.db.run(headline_str, headline).peek()
                headline_id = headline_insert['headline_id']
            else:
                article = {"link": headLink}
                headline = {"headline": headline, "score": score, "width": size['width'], "height": size['height'], "loc_x": loc['x'], "loc_y": loc['y']}
                article_headline = article.copy()
                article_headline.update(headline)
                article_str = '''
                    MATCH (ss:SnapShot) WHERE ID(ss) = {snapshot_id}
                    CREATE (ss)-[:HAS]->(h:Headline ''' + self._cypherString(headline) + ''')-[:HEADLINE]->
                    (a:Article ''' + self._cypherString(article) + ''')
                    RETURN ID(h) as headline_id, ID(a) as article_id
                '''
                article_headline["snapshot_id"] = snapshot_id
                article_insert = self.db.run(article_str, article_headline).peek()
                article_id = article_insert['article_id']
                headline_id = article_insert['headline_id']
            return article_id, headline_id
        except Exception as e:
            print "Error raised in dbManager.storeArticle"
            raise

    # Create dict string for cypher inserts/queries
    def _cypherString(self, data):
        q_list = []
        for n in data.keys():
            q_list.append(n + ':{' + n + '}')
        return "{" + ','.join(q_list) + "}"
