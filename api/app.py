from flask import Flask, jsonify, request, escape
from neo4j.v1 import GraphDatabase, basic_auth
from flask_cors import CORS
import sqlite3
import configparser
import json
import re
import os
import hashlib
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q
from datetime import datetime


config = configparser.ConfigParser()
app = Flask(__name__)
cors = CORS(app)
config.read(os.path.join(app.root_path, '../headliner.conf'))

@app.route("/")
def main():
    jsonResponse = jsonify({
        "name": "Headlinr",
        "description": "This API returns headlines from major news sources so that differences in coverage can be discovered and analyzed"
    })
    return jsonResponse

@app.route("/articles")
def articles():
    headline = request.args.get('headline')

    client = Elasticsearch([{'host': config['ES']['host'], 'port': int(config['ES']['port'])}])

    es = Search(using=client, index=config['ES']['index'], doc_type='Headline').query(Q('query_string', query=headline))
    headlines = es.execute()

    if headlines['hits']['total'] == 0:
        nonResponse = jsonify({'message': 'No results found for your search'})
        return nonResponse
    response = {"total": 0, 'articles': {}}
    uuids = []
    for head in es.scan():
        headUUID = head.meta.id
        uuids.append(headUUID)
    articles, total = getArticles(uuids)
    response['total'] = total
    parsedArticles = parseArticlesForDisplay(articles)
    response['articles'] = parsedArticles
    return jsonify(response)

def getArticles(UUIDs):
    driver = GraphDatabase.driver(config['DB']['db_url'], auth=basic_auth(config['DB']['db_usr'], config['DB']['db_psw']))
    db = driver.session()
    art_ret = {}
    art_total = 0
    article_q = "MATCH (s:Source)--(ss:SnapShot)--(h:Headline)--(a:Article) WHERE h.uuid IN {UUIDs} RETURN a.link as link, a.uuid as art_uuid, ss.run_time as time, ss.uuid as snap_uuid, s.code as code, s.name as name, h.height as height, h.width as width, h.loc_x as pos_x, h.loc_y as pos_y, h.score as score, h.headline as headline, h.uuid as headline_uuid ORDER BY ss.run_time"
    matches = db.run(article_q, {"UUIDs": UUIDs})
    for match in matches:
        md5 = hashlib.md5()
        md5.update(match['headline'].encode('utf-8'))
        head_id = md5.hexdigest()
        if match['code'] not in art_ret:
            art_ret[match['code']] = {
                'name': match['name'],
                'articles': {}
            }
        if match['art_uuid'] not in art_ret[match['code']]['articles']:
            art_total += 1
            art_ret[match['code']]['articles'][match['art_uuid']] = {
                "link": match['link'],
                "uuid": match['art_uuid'],
                'snapshots': {}
            }
        if head_id not in art_ret[match['code']]['articles'][match['art_uuid']]['snapshots']:
            art_ret[match['code']]['articles'][match['art_uuid']]['snapshots'][head_id] = {
                "headline": match["headline"],
                "versions": []
            }

        sortTime = datetime.strptime(match['time'], "%Y-%m-%dT%H:%M:%S")
        snap = {
            'time': sortTime,
            'uuid': match['headline_uuid'],
            'score': round(match['score'], 3),
            'pos': {'x': match['pos_x'], 'y': match['pos_y']},
            'size': {'height': match['height'], 'width': match['width']}
        }
        art_ret[match['code']]['articles'][match['art_uuid']]['snapshots'][head_id]['versions'].append(snap)

    return art_ret, art_total

def parseArticlesForDisplay(art_ret):
    parsed_articles = {}
    for site in art_ret:
        parsed_articles[site] = {'name': art_ret[site]['name'], 'articles': []}
        articles = art_ret[site]['articles']
        for uuid in articles:
            article = articles[uuid]
            parsed_article = {'link': article['link'], 'uuid': uuid, 'headlines': [], 'firstSeen': None, 'lastSeen': None}
            snapshots = article['snapshots']
            totalScore = 0
            versionCount = 0
            for head_id in snapshots:
                headInfo = {"headline": snapshots[head_id]["headline"], "head_id": head_id, "versions": []}
                versions = snapshots[head_id]['versions']
                headInfo['firstSeen'] = versions[0]['time']
                if not parsed_article['firstSeen'] or parsed_article['firstSeen'] > headInfo['firstSeen']:
                    parsed_article['firstSeen'] = headInfo['firstSeen']
                headInfo['lastSeen'] = versions[-1]['time']
                if not parsed_article['lastSeen'] or parsed_article['lastSeen'] < headInfo['lastSeen']:
                    parsed_article['lastSeen'] = headInfo['lastSeen']
                for version in versions:
                    totalScore += version['score']
                    versionCount += 1
                    headInfo['versions'].append(version)
                parsed_article['headlines'].append(headInfo)
            avgScore = round(totalScore/versionCount, 3)
            parsed_article['avgScore'] = avgScore
            parsed_articles[site]['articles'].append(parsed_article)

    return parsed_articles



    return art_ret

if __name__ == "__main__":
    app.run()
