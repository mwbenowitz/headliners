from flask import Flask, jsonify, request
import sqlite3
import json
from elasticsearch import Elasticsearch
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def main():
    jsonResponse = jsonify({
        "name": "Headlinr",
        "description": "This API returns headlines from major news sources so that differences in coverage can be discovered and analyzed"
    })
    return jsonResponse

@app.route("/articles")
def articles():
    conn = sqlite3.connect('test.db')
    cur = conn.cursor()
    headline = request.args.get('headline')
    es = Elasticsearch()
    articles = es.search(index='articles', body={'query':{'match': {'headline': headline}}})
    if articles['hits']['total'] == 0:
        nonResponse = jsonify({'message': 'No results found for your search'})
        return nonResponse
    snaps = []
    response = {"total": articles['hits']['total'], 'articles': {}}
    for article in articles['hits']['hits']:
        articleID = article['_source']['sqlID']
        title = article['_source']['headline']
        for instance in cur.execute("SELECT * FROM snap_articles INNER JOIN articles ON articles.id = snap_articles.article WHERE articles.id=?", (articleID,)):
	    print instance
            score = instance[3]
            snapUUID = instance[1]
            cur.execute("SELECT * FROM snapshots WHERE uuid=?", (snapUUID,))
            snapshot = cur.fetchone()
            snapTime = datetime.strptime(snapshot[1], "%Y-%m-%dT%H:%M:%S")
            snaps.append((snapTime, score))
        source = snapshot[3]
        snaps.sort(key=lambda tup:tup[0])
        if source not in response['articles']:
            response['articles'][source] = []
        response['articles'][source].append({"headline": title, "firstSeen": snaps[0], "lastSeen": snaps[-1]})

    return jsonify(response)

 
